"""Limpeza one-off do acúmulo de temas (verbatim_temas aditivo entre rodadas).

O pipeline é aditivo: ``_upsert_tema_e_link`` nunca remove o vínculo da rodada
anterior. Quando o rotulador nomeia o mesmo cluster de formas diferentes ao longo
das rodadas/versões de prompt, cada verbatim acumula vínculos a vários ``Tema``
(slugs distintos do mesmo tema semântico), e a lista live do painel mostra todos.

``limpar_acumulo_temas`` corrige o estado ATUAL, por empresa:

1. **Poda**: por verbatim, mantém só o vínculo LLM da **rodada mais recente**
   (maior ``criado_em``; desempate por id) e remove os anteriores. Vínculos
   ``origem IN ('manual','merge')`` são SEMPRE preservados.
2. **Desativa** ``Tema`` que ficou sem nenhum vínculo vivo (``ativo=False``).
3. **Regenera** ``temas_cache`` a partir dos vínculos resultantes (link-based,
   sem re-clusterizar nem LLM) → o snapshot passa a bater com o live (badge
   deixa de acusar defasagem).

``--dry-run`` mede e reporta (1) e (2) sem gravar nada.

Isto é a contraparte one-off da correção de raiz no pipeline (tornar
``_upsert_tema_e_link`` não-aditivo); rodando os dois, o acúmulo some e não volta.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import and_, func

from src.models.local import Local
from src.models.temas import Tema, TemaCache, VerbatimTema
from src.models.verbatim import Verbatim
from src.utils.db import db_session

_CHUNK = 500


def limpar_acumulo_temas(empresa_id: int, dry_run: bool = False) -> Dict[str, Any]:
    """Poda vínculos acumulados, desativa temas órfãos e regenera o cache.

    Returns:
        ``{"verbatins_com_acumulo", "vinculos_removidos", "temas_desativados",
           "cache_rows"}``. Em ``dry_run`` os 3 primeiros são medidos e
        ``cache_rows`` é ``None`` (não regenera).
    """
    with db_session() as s:
        # 1) Carrega todos os vínculos da empresa (id, verbatim, tema, origem, data).
        rows = (
            s.query(
                VerbatimTema.id,
                VerbatimTema.verbatim_id,
                VerbatimTema.tema_id,
                VerbatimTema.origem,
                VerbatimTema.criado_em,
            )
            .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
            .filter(Verbatim.empresa_id == empresa_id)
            .all()
        )

        # Poda: por verbatim, manter só o vínculo LLM mais recente.
        llm_por_verb: Dict[int, list] = defaultdict(list)
        for r in rows:
            if r.origem == "llm":
                llm_por_verb[r.verbatim_id].append((r.criado_em or datetime.min, r.id))
        remover_ids: set[int] = set()
        verbatins_com_acumulo = 0
        for lst in llm_por_verb.values():
            if len(lst) > 1:
                verbatins_com_acumulo += 1
                lst.sort()  # asc por (criado_em, id) → o último é o mais recente
                for _, lid in lst[:-1]:
                    remover_ids.add(lid)

        # Temas que ficariam sem nenhum vínculo vivo após a poda.
        restantes_por_tema: Dict[int, int] = defaultdict(int)
        for r in rows:
            if r.id not in remover_ids:
                restantes_por_tema[r.tema_id] += 1
        temas_ativos = {t.id: t for t in s.query(Tema).filter_by(empresa_id=empresa_id, ativo=True)}
        desativar = [tid for tid in temas_ativos if restantes_por_tema.get(tid, 0) == 0]

        stats: Dict[str, Any] = {
            "verbatins_com_acumulo": verbatins_com_acumulo,
            "vinculos_removidos": len(remover_ids),
            "temas_desativados": len(desativar),
            "cache_rows": None,
        }
        if dry_run:
            return stats

        # 2) Aplica poda + desativação (mesma transação).
        ids = list(remover_ids)
        for i in range(0, len(ids), _CHUNK):
            chunk = ids[i : i + _CHUNK]  # noqa: E203 (black formata o slice assim)
            s.query(VerbatimTema).filter(VerbatimTema.id.in_(chunk)).delete(
                synchronize_session=False
            )
        for tid in desativar:
            temas_ativos[tid].ativo = False

    # 3) Regenera o cache a partir dos vínculos resultantes (nova sessão, lê o
    #    estado já commitado).
    stats["cache_rows"] = _regenerar_cache_por_vinculos(empresa_id)
    return stats


def _regenerar_cache_por_vinculos(empresa_id: int) -> int:
    """Reescreve ``temas_cache`` da empresa a partir dos vínculos a temas ATIVOS.

    Link-based (não re-clusteriza): volume = verbatins distintos por
    ``(agrupamento, subpilar, tipo, tema_label)``. Faz o snapshot bater com o live.
    """
    with db_session() as s:
        s.query(TemaCache).filter_by(empresa_id=empresa_id).delete(synchronize_session=False)

        rows = (
            s.query(
                Local.agrupamento_id.label("ag"),
                Verbatim.subpilar.label("sub"),
                Verbatim.tipo.label("tipo"),
                Tema.nome.label("nome"),
                Verbatim.id.label("vid"),
                Verbatim.data_criacao_original.label("data"),
            )
            .select_from(VerbatimTema)
            .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
            .join(Tema, and_(Tema.id == VerbatimTema.tema_id, Tema.ativo.is_(True)))
            .outerjoin(Local, Local.id == Verbatim.local_id)
            .filter(
                Verbatim.empresa_id == empresa_id,
                Verbatim.tem_texto.is_(True),
                Verbatim.subpilar.isnot(None),
                Verbatim.tipo.isnot(None),
            )
            .all()
        )

        # Total do bucket (verbatins COM TEXTO) por (ag, sub, tipo), p/ percentual.
        totais = {
            (t.ag, t.sub, t.tipo): t.n
            for t in (
                s.query(
                    Local.agrupamento_id.label("ag"),
                    Verbatim.subpilar.label("sub"),
                    Verbatim.tipo.label("tipo"),
                    func.count(func.distinct(Verbatim.id)).label("n"),
                )
                .select_from(Verbatim)
                .outerjoin(Local, Local.id == Verbatim.local_id)
                .filter(
                    Verbatim.empresa_id == empresa_id,
                    Verbatim.tem_texto.is_(True),
                    Verbatim.subpilar.isnot(None),
                    Verbatim.tipo.isnot(None),
                )
                .group_by(Local.agrupamento_id, Verbatim.subpilar, Verbatim.tipo)
                .all()
            )
        }

        agg: Dict[tuple, Dict[str, Any]] = defaultdict(
            lambda: {"vids": set(), "datas": [], "exemplos": []}
        )
        for r in rows:
            e = agg[(r.ag, r.sub, r.tipo, r.nome)]
            e["vids"].add(r.vid)
            if r.data:
                e["datas"].append(r.data)
            if len(e["exemplos"]) < 3 and r.vid not in e["exemplos"]:
                e["exemplos"].append(r.vid)

        criadas = 0
        for (ag, sub, tipo, nome), e in agg.items():
            volume = len(e["vids"])
            total = totais.get((ag, sub, tipo), 0)
            pct = round(100.0 * volume / total, 2) if total else 0.0
            datas = e["datas"]
            ini = min(datas).date() if datas else datetime.utcnow().date()
            fim = max(datas).date() if datas else datetime.utcnow().date()
            s.add(
                TemaCache(
                    empresa_id=empresa_id,
                    agrupamento_id=ag,
                    subpilar=sub,
                    tipo=tipo,
                    tema_label=nome,
                    volume=volume,
                    percentual=pct,
                    periodo_inicio=ini,
                    periodo_fim=fim,
                    exemplos_verbatim_ids=json.dumps(e["exemplos"]),
                    hash_escopo=f"relink-{empresa_id}-{ag}-{sub}-{tipo}-{nome}"[:120],
                )
            )
            criadas += 1
    return criadas
