"""Pipeline orquestrador de temas (Bloco 6 Caminho A CP-10).

Costura:
1. Lê verbatins de uma empresa (com texto + bucket).
2. Bucketiza por (agrupamento_id, subpilar, tipo).
3. Por bucket: carrega embeddings → clusteriza → escolhe representativos →
   rotula via LLM → persiste em (``temas``, ``verbatim_temas`` com
   ``bucket_chave``, ``temas_cache``).

Função pública: ``processar_empresa(empresa_id, ...)``. Idempotente: pode
re-rodar — vínculos com mesma (verbatim_id, tema_id) são pulados; cache
é zerado por bucket antes de regravar.

Kill switches: ``max_usd``, ``so_buckets`` (lista). Sem ``--apenas-novos``
porque o motor agora trabalha por cluster, não por verbatim.
"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from src.temas.clusterer import (
    HDBSCAN_MIN_CLUSTER_SIZE_MIN,
    bucketizar_verbatins,
    clusterizar_bucket,
    pick_representativos,
)
from src.temas.embeddings import MODELO_PADRAO, carregar_embeddings
from src.temas.rotulador import rotular_cluster
from src.temas.slug import slugify

# Custo Haiku por rotulagem (1 chamada por cluster): system+payload pequeno,
# saída <100 tokens. Estimativa: $0.0005/chamada (alinhado a CUSTO_USD_POR_VERBATIM
# de extrator legado, conservador pra cima).
CUSTO_USD_POR_ROTULAGEM = 0.0005


@dataclass
class ResumoPipeline:
    empresa_id: int
    empresa_nome: str
    buckets_processados: int = 0
    buckets_pulados: int = 0  # bucket pequeno < MIN
    buckets_sem_embeddings: int = 0  # esquecimento de rodar temas-embed
    clusters_rotulados: int = 0
    clusters_descartados: int = 0  # rotulador devolveu None
    temas_unicos_criados: int = 0  # novos rows em temas
    temas_reusados: int = 0  # slug já existia
    vinculos_criados: int = 0
    cache_rows_criadas: int = 0
    erros: int = 0
    custo_usd_acumulado: float = 0.0
    abortado_kill_switch: bool = False
    detalhes_buckets: List[Dict[str, Any]] = field(default_factory=list)


def _hash_escopo(empresa_id: int, ag_id: Optional[int], sub: str, tipo: str, label: str) -> str:
    s = f"{empresa_id}|{ag_id or 0}|{sub}|{tipo}|{label}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:32]


def _bucket_chave(ag_id: Optional[int], sub: str, tipo: str) -> str:
    return f"{ag_id if ag_id is not None else 'NULL'}:{sub}:{tipo}"


def _carregar_verbatins_empresa(empresa_id: int, so_com_texto: bool = True) -> List[dict]:
    """Lê verbatins + agrupamento_id (via Local) em dicts puros."""
    from src.models.agrupamento import Agrupamento
    from src.models.local import Local
    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    with db_session() as s:
        q = (
            s.query(
                Verbatim.id,
                Verbatim.texto,
                Verbatim.subpilar,
                Verbatim.tipo,
                Verbatim.local_id,
                Verbatim.data_criacao_original,
                Agrupamento.id.label("agrupamento_id"),
                Agrupamento.nome.label("agrupamento_nome"),
            )
            .outerjoin(Local, Local.id == Verbatim.local_id)
            .outerjoin(Agrupamento, Agrupamento.id == Local.agrupamento_id)
            .filter(Verbatim.empresa_id == empresa_id)
        )
        if so_com_texto:
            q = q.filter(Verbatim.tem_texto.is_(True))
        out = []
        for r in q.all():
            out.append(
                {
                    "id": r.id,
                    "texto": r.texto or "",
                    "subpilar": r.subpilar,
                    "tipo": r.tipo,
                    "agrupamento_id": r.agrupamento_id,
                    "agrupamento_nome": r.agrupamento_nome,
                    "data": r.data_criacao_original,
                }
            )
    return out


def _zerar_cache_bucket(empresa_id: int, ag_id: Optional[int], sub: str, tipo: str) -> None:
    """Remove rows de ``temas_cache`` deste bucket — re-run sobrescreve."""
    from src.models.temas import TemaCache
    from src.utils.db import db_session

    with db_session() as s:
        q = s.query(TemaCache).filter(
            TemaCache.empresa_id == empresa_id,
            TemaCache.subpilar == sub,
            TemaCache.tipo == tipo,
        )
        if ag_id is None:
            q = q.filter(TemaCache.agrupamento_id.is_(None))
        else:
            q = q.filter(TemaCache.agrupamento_id == ag_id)
        q.delete(synchronize_session=False)


def _upsert_tema_e_link(
    empresa_id: int,
    label: str,
    bucket_chave: str,
    membros_ids: List[int],
    representativos_ids: List[int],
    origem: str = "llm",
) -> Dict[str, int]:
    """Upsert do tema (por slug) + cria vínculos verbatim_temas idempotente.

    Returns:
        dict ``{"tema_id": int, "novo_tema": int(0|1), "vinculos_novos": int}``.
    """
    from src.models.temas import Tema, VerbatimTema
    from src.utils.db import db_session

    slug = slugify(label)
    rep_set = set(representativos_ids)

    with db_session() as s:
        existente = s.query(Tema).filter_by(empresa_id=empresa_id, slug=slug).first()
        if existente:
            tema_id = existente.id
            novo_tema = 0
            # Se estava inativo (merged antigo), reativar? Não — preserva auditoria.
        else:
            t = Tema(empresa_id=empresa_id, nome=label, slug=slug, ativo=True)
            s.add(t)
            s.flush()
            tema_id = t.id
            novo_tema = 1

        # Vínculos: idempotente via UNIQUE(verbatim_id, tema_id). Verificamos
        # antes pra contar corretamente novos vínculos.
        ja = (
            s.query(VerbatimTema.verbatim_id)
            .filter(VerbatimTema.tema_id == tema_id, VerbatimTema.verbatim_id.in_(membros_ids))
            .all()
        )
        ja_ids = {row[0] for row in ja}
        novos = [vid for vid in membros_ids if vid not in ja_ids]
        for vid in novos:
            # Confiança: 0.9 pra representativos, 0.7 pros demais do cluster.
            # Reflete que reps são centrais; outros são membros do mesmo cluster.
            conf = 0.9 if vid in rep_set else 0.7
            s.add(
                VerbatimTema(
                    verbatim_id=vid,
                    tema_id=tema_id,
                    confianca=conf,
                    origem=origem,
                    bucket_chave=bucket_chave,
                )
            )
    return {"tema_id": tema_id, "novo_tema": novo_tema, "vinculos_novos": len(novos)}


def _agregar_cache_por_label(
    rotulados: List[Dict[str, Any]],
) -> "OrderedDict[str, Dict[str, Any]]":
    """Agrega clusters que resolvem pro mesmo label (Achado 2 / CP-11).

    Vários clusters de um bucket podem receber o mesmo label (ex.: 13
    clusters → "atendimento personalizado"). Em vez de 1 row de cache por
    cluster — que repetiria o nome no painel — soma os volumes e mantém
    os ``exemplos_ids`` do **maior** cluster contribuinte (mais ilustrativo).

    Args:
        rotulados: lista de dicts ``{"label", "volume", "exemplos_ids"}`` na
            ordem em que os clusters foram rotulados.

    Returns:
        ``OrderedDict`` label → ``{"volume": int, "exemplos_ids": [...]}``,
        preservando a ordem da 1ª aparição de cada label.
    """
    agg: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    for c in rotulados:
        label = c["label"]
        vol = c["volume"]
        cur = agg.get(label)
        if cur is None:
            agg[label] = {
                "volume": vol,
                "exemplos_ids": list(c["exemplos_ids"]),
                "_top_vol": vol,
            }
        else:
            cur["volume"] += vol
            if vol > cur["_top_vol"]:
                cur["exemplos_ids"] = list(c["exemplos_ids"])
                cur["_top_vol"] = vol
    for v in agg.values():
        v.pop("_top_vol", None)
    return agg


def _gravar_cache(
    empresa_id: int,
    ag_id: Optional[int],
    sub: str,
    tipo: str,
    label: str,
    volume: int,
    bucket_total: int,
    exemplos_ids: List[int],
    periodo_ini,
    periodo_fim,
) -> None:
    from src.models.temas import TemaCache
    from src.utils.db import db_session

    pct = round(100.0 * volume / bucket_total, 2) if bucket_total else 0.0
    with db_session() as s:
        s.add(
            TemaCache(
                empresa_id=empresa_id,
                agrupamento_id=ag_id,
                subpilar=sub,
                tipo=tipo,
                tema_label=label,
                volume=volume,
                percentual=pct,
                tendencia_pct=None,  # tendência: bloco futuro (delta período)
                periodo_inicio=periodo_ini,
                periodo_fim=periodo_fim,
                exemplos_verbatim_ids=json.dumps(exemplos_ids),
                hash_escopo=_hash_escopo(empresa_id, ag_id, sub, tipo, label),
            )
        )


def _processar_bucket(
    *,
    empresa_id: int,
    setor: Optional[str],
    chave_bucket: str,
    membros: List[dict],
    embeddings: Dict[int, np.ndarray],
    callback_progresso: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Processa 1 bucket. Devolve dict com contadores e custo."""
    ag_id_raw, sub, tipo = chave_bucket.split(":")
    ag_id = None if ag_id_raw == "NULL" else int(ag_id_raw)
    ag_nome = next((m.get("agrupamento_nome") for m in membros if m.get("agrupamento_nome")), None)

    stats = {
        "chave": chave_bucket,
        "total_membros": len(membros),
        "membros_com_embedding": 0,
        "clusters_total": 0,
        "clusters_rotulados": 0,
        "clusters_descartados": 0,
        "vinculos_criados": 0,
        "temas_novos": 0,
        "temas_reusados": 0,
        "cache_rows": 0,
        "custo_usd": 0.0,
        "skip_motivo": None,
    }

    # Filtra só membros que têm embedding (consistência embedding × cluster)
    membros_com_emb = [m for m in membros if m["id"] in embeddings]
    stats["membros_com_embedding"] = len(membros_com_emb)
    if len(membros_com_emb) < HDBSCAN_MIN_CLUSTER_SIZE_MIN:
        stats["skip_motivo"] = f"bucket_pequeno_membros_com_embedding={len(membros_com_emb)}"
        return stats

    # Monta matriz vetores na ordem de membros_com_emb
    vetores = np.stack([embeddings[m["id"]] for m in membros_com_emb])

    # Clusteriza
    res = clusterizar_bucket(vetores)
    stats["clusters_total"] = res.n_clusters
    stats["noise"] = res.n_noise
    stats["algoritmo"] = res.algoritmo

    # Período (mín/máx das datas) — fallback today se vazio
    datas = [m["data"] for m in membros_com_emb if m.get("data")]
    periodo_ini = min(datas).date() if datas else datetime.utcnow().date()
    periodo_fim = max(datas).date() if datas else datetime.utcnow().date()
    bucket_total = len(membros_com_emb)

    # Zera cache do bucket pra escrita idempotente
    _zerar_cache_bucket(empresa_id, ag_id, sub, tipo)

    rotulados: List[Dict[str, Any]] = []
    for cluster_id in sorted(set(res.labels) - {-1}):
        rep_pos = pick_representativos(vetores, res.labels, cluster_id, k=3)
        membros_pos = np.where(res.labels == cluster_id)[0]
        membros_ids = [membros_com_emb[i]["id"] for i in membros_pos]
        rep_ids = [membros_com_emb[i]["id"] for i in rep_pos]
        reps_dados = [
            {"texto": membros_com_emb[i]["texto"], "verbatim_id": membros_com_emb[i]["id"]}
            for i in rep_pos
        ]

        label = rotular_cluster(
            {
                "subpilar": sub,
                "tipo": tipo,
                "setor": setor,
                "agrupamento": ag_nome,
            },
            reps_dados,
        )
        stats["custo_usd"] = round(stats["custo_usd"] + CUSTO_USD_POR_ROTULAGEM, 6)
        if not label:
            stats["clusters_descartados"] += 1
            continue
        upsert = _upsert_tema_e_link(
            empresa_id=empresa_id,
            label=label,
            bucket_chave=chave_bucket,
            membros_ids=membros_ids,
            representativos_ids=rep_ids,
        )
        stats["clusters_rotulados"] += 1
        stats["temas_novos"] += upsert["novo_tema"]
        stats["temas_reusados"] += 1 - upsert["novo_tema"]
        stats["vinculos_criados"] += upsert["vinculos_novos"]
        rotulados.append({"label": label, "volume": len(membros_ids), "exemplos_ids": rep_ids})

        if callback_progresso:
            callback_progresso(chave_bucket, label, len(membros_ids))

    # Achado 2 (CP-11): agrega cache por label — vários clusters do mesmo
    # bucket podem resolver pro mesmo label (ex.: 13 clusters →
    # "atendimento personalizado"). Grava 1 row por label, volume somado.
    agregados = _agregar_cache_por_label(rotulados)
    for label, ag in agregados.items():
        _gravar_cache(
            empresa_id=empresa_id,
            ag_id=ag_id,
            sub=sub,
            tipo=tipo,
            label=label,
            volume=ag["volume"],
            bucket_total=bucket_total,
            exemplos_ids=ag["exemplos_ids"],
            periodo_ini=periodo_ini,
            periodo_fim=periodo_fim,
        )
    stats["cache_rows"] = len(agregados)

    return stats


def processar_empresa(
    empresa_id: int,
    *,
    so_buckets: Optional[List[str]] = None,
    max_usd: Optional[float] = None,
    callback_progresso: Optional[Callable] = None,
    dry_run: bool = False,
) -> ResumoPipeline:
    """Pipeline ponta-a-ponta — apenas buckets com ≥ MIN_BUCKET_HDBSCAN membros.

    Args:
        empresa_id: pk.
        so_buckets: se fornecido (lista de chaves ``"agrup:sub:tipo"``), só
            processa esses buckets. Útil pro smoke do CP-11.
        max_usd: kill switch — aborta antes do próximo bucket quando excede.
        callback_progresso: ``fn(chave, label, volume) -> None`` por cluster
            rotulado.
        dry_run: lista buckets elegíveis + custo, sem chamar LLM nem escrever DB.

    Returns:
        ``ResumoPipeline``.
    """
    from src.models.empresa import Empresa
    from src.utils.db import db_session

    with db_session() as s:
        emp = s.get(Empresa, empresa_id)
        if emp is None:
            raise ValueError(f"empresa_id={empresa_id} não encontrada")
        empresa_nome = emp.nome
        setor = emp.setor

    resumo = ResumoPipeline(empresa_id=empresa_id, empresa_nome=empresa_nome)

    verbatins = _carregar_verbatins_empresa(empresa_id)
    buckets = bucketizar_verbatins(verbatins)

    if so_buckets:
        buckets = {k: v for k, v in buckets.items() if k in set(so_buckets)}

    buckets_elegiveis = {k: v for k, v in buckets.items() if len(v) >= HDBSCAN_MIN_CLUSTER_SIZE_MIN}
    resumo.buckets_pulados = len(buckets) - len(buckets_elegiveis)

    if dry_run:
        # Estima custo: ~3 clusters por bucket × CUSTO_USD_POR_ROTULAGEM (conservador).
        # Mais preciso só rodando real.
        clusters_estimados = sum(max(2, int(np.sqrt(len(v)))) for v in buckets_elegiveis.values())
        resumo.custo_usd_acumulado = round(clusters_estimados * CUSTO_USD_POR_ROTULAGEM, 4)
        resumo.detalhes_buckets = [
            {"chave": k, "membros": len(v)} for k, v in sorted(buckets_elegiveis.items())
        ]
        return resumo

    # Pré-carrega TODOS os embeddings necessários (1 query única, 6kb por vetor)
    todos_ids = [v["id"] for v in verbatins]
    embeddings = carregar_embeddings(todos_ids, modelo=MODELO_PADRAO)

    for chave, membros in sorted(buckets_elegiveis.items(), key=lambda kv: -len(kv[1])):
        if max_usd is not None and resumo.custo_usd_acumulado >= max_usd:
            resumo.abortado_kill_switch = True
            break
        # Conta buckets sem embedding (operador esqueceu de rodar temas-embed)
        ids_sem_emb = [m["id"] for m in membros if m["id"] not in embeddings]
        if not embeddings or len(ids_sem_emb) == len(membros):
            resumo.buckets_sem_embeddings += 1
            continue

        try:
            stats = _processar_bucket(
                empresa_id=empresa_id,
                setor=setor,
                chave_bucket=chave,
                membros=membros,
                embeddings=embeddings,
                callback_progresso=callback_progresso,
            )
            resumo.detalhes_buckets.append(stats)
            resumo.clusters_rotulados += stats["clusters_rotulados"]
            resumo.clusters_descartados += stats["clusters_descartados"]
            resumo.temas_unicos_criados += stats["temas_novos"]
            resumo.temas_reusados += stats["temas_reusados"]
            resumo.vinculos_criados += stats["vinculos_criados"]
            resumo.cache_rows_criadas += stats["cache_rows"]
            resumo.custo_usd_acumulado = round(resumo.custo_usd_acumulado + stats["custo_usd"], 6)
            resumo.buckets_processados += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[temas/pipeline] bucket {chave}: {type(exc).__name__}: {exc}")
            resumo.erros += 1

    return resumo
