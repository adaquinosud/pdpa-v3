"""Detecção de cruzamentos de temas — Nível 4 (Bloco 7).

Um **cruzamento** é um tema que atravessa ≥2 buckets ``subpilar:tipo``
distintos — sinaliza questão sistêmica (não de um pilar isolado).

Fase 1 (este módulo, CP-2): **match literal** — mesmo ``tema_label`` em
buckets diferentes. Determinístico, sem LLM, sem custo. A Fase 2 (CP-3a)
adicionará famílias semânticas via embeddings, gravando ``membros_json``.

Peso (decisão B7, revisado): ``ln(volume_total + 1) × n_subpilares × n_tipos``.
O ``log`` amortece o domínio de temas de altíssimo volume; multiplicar por
n_subpilares **e** n_tipos premia a **sistemicidade** (atravessar pilares e
tipos) — exatamente o que o Manual valoriza como diagnóstico de causa raiz.

Função pública: ``detectar_e_persistir_literais(empresa_id) -> ResumoCruzamento``.
Idempotente: zera os cruzamentos literais (``membros_json IS NULL``) da
empresa antes de regravar; não toca nos semânticos da Fase 2.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

# ── Fase 2 (semântica) ────────────────────────────────────────────────
SEMANTIC_THRESHOLD = 0.90
"""Cosine mínimo entre centróides de temas para virar par candidato."""

HAIKU_MODEL = "claude-haiku-4-5-20251001"
CURADORIA_PROMPT_PATH = Path(__file__).parent / "prompts" / "curadoria_cruzamento_v1.md"
CUSTO_USD_POR_CURADORIA = 0.0003  # estimativa: 1 chamada Haiku pequena


def _subpilar_tipo(bucket_chave: str) -> Optional[str]:
    """``"10:Pa1:promotor"`` → ``"Pa1:promotor"``. None se malformado."""
    partes = bucket_chave.split(":")
    if len(partes) != 3:
        return None
    return f"{partes[1]}:{partes[2]}"


def _hash_escopo(empresa_id: int, label: str, buckets: List[str]) -> str:
    s = f"{empresa_id}|{label}|{'|'.join(sorted(buckets))}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:32]


def calcular_peso(volume_total: int, n_subpilares: int, n_tipos: int) -> float:
    """``ln(volume_total + 1) × n_subpilares × n_tipos`` (decisão B7 revisada).

    O ``log`` amortece fortemente o volume bruto (um tema 100× maior não pesa
    100×), de modo que ``n_subpilares × n_tipos`` (sistemicidade — atravessar
    pilares e tipos) domine o ranking, em vez do volume mono-subpilar. Alinha
    ao Manual: cruzamento cross-pilar é o diagnóstico de causa raiz.
    """
    return round(math.log(max(0, volume_total) + 1) * n_subpilares * n_tipos, 2)


@dataclass
class ResumoCruzamento:
    empresa_id: int
    temas_analisados: int = 0
    cruzamentos_criados: int = 0
    detalhes: List[Dict[str, Any]] = field(default_factory=list)


def _carregar_label_buckets(empresa_id: int) -> Dict[str, Dict[str, Any]]:
    """Para cada ``tema_label`` (tema ativo), agrega seus vínculos Caminho A.

    Returns:
        ``{label: {"buckets": {subpilar:tipo: volume}, "tipos": set,
        "datas": [..], "volume": int}}``.
    """
    from src.models.temas import Tema, VerbatimTema
    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    agg: Dict[str, Dict[str, Any]] = {}
    with db_session() as s:
        rows = (
            s.query(
                Tema.nome,
                VerbatimTema.bucket_chave,
                Verbatim.data_criacao_original,
            )
            .join(VerbatimTema, VerbatimTema.tema_id == Tema.id)
            .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
            .filter(
                Tema.empresa_id == empresa_id,
                Tema.ativo.is_(True),
                VerbatimTema.bucket_chave.isnot(None),
            )
        )
        for nome, bucket_chave, data in rows.all():
            st = _subpilar_tipo(bucket_chave or "")
            if st is None:
                continue
            entry = agg.setdefault(
                nome, {"buckets": defaultdict(int), "tipos": set(), "datas": [], "volume": 0}
            )
            entry["buckets"][st] += 1
            entry["tipos"].add(st.split(":")[1])
            entry["volume"] += 1
            if data is not None:
                entry["datas"].append(data)
    return agg


def _zerar_literais(empresa_id: int) -> None:
    """Remove cruzamentos literais (``membros_json IS NULL``) da empresa."""
    from src.models.temas import TemaCruzamento
    from src.utils.db import db_session

    with db_session() as s:
        s.query(TemaCruzamento).filter(
            TemaCruzamento.empresa_id == empresa_id,
            TemaCruzamento.membros_json.is_(None),
        ).delete(synchronize_session=False)


def detectar_literais(empresa_id: int) -> List[Dict[str, Any]]:
    """Detecta cruzamentos literais (sem persistir). Útil para testes/dry-run.

    Um cruzamento = ``tema_label`` presente em ≥2 buckets ``subpilar:tipo``.
    """
    agg = _carregar_label_buckets(empresa_id)
    cruzamentos: List[Dict[str, Any]] = []
    for label, info in agg.items():
        buckets = sorted(info["buckets"].keys())
        if len(buckets) < 2:
            continue
        tipos = sorted(info["tipos"])
        n_subpilares = len({b.split(":")[0] for b in buckets})
        datas = info["datas"]
        cruzamentos.append(
            {
                "tema_label": label,
                "buckets_envolvidos": buckets,
                "tipos_envolvidos": tipos,
                "n_subpilares_distintos": n_subpilares,
                "volume_total": info["volume"],
                "peso": calcular_peso(info["volume"], n_subpilares, len(tipos)),
                "periodo_inicio": (min(datas).date() if datas else datetime.utcnow().date()),
                "periodo_fim": (max(datas).date() if datas else datetime.utcnow().date()),
            }
        )
    # Ordena por peso desc — mais transversais primeiro.
    cruzamentos.sort(key=lambda c: -c["peso"])
    return cruzamentos


def detectar_e_persistir_literais(empresa_id: int) -> ResumoCruzamento:
    """Detecta e grava cruzamentos literais. Idempotente (zera literais antes)."""
    from src.models.temas import TemaCruzamento
    from src.utils.db import db_session

    agg = _carregar_label_buckets(empresa_id)
    cruzamentos = detectar_literais(empresa_id)

    resumo = ResumoCruzamento(empresa_id=empresa_id, temas_analisados=len(agg))
    _zerar_literais(empresa_id)
    with db_session() as s:
        for c in cruzamentos:
            s.add(
                TemaCruzamento(
                    empresa_id=empresa_id,
                    agrupamento_id=None,  # company-wide (cross-pilar)
                    tema_label=c["tema_label"],
                    buckets_envolvidos_json=json.dumps(c["buckets_envolvidos"]),
                    tipos_envolvidos_json=json.dumps(c["tipos_envolvidos"]),
                    n_subpilares_distintos=c["n_subpilares_distintos"],
                    membros_json=None,  # literal — Fase 2 preenche família semântica
                    peso=c["peso"],
                    periodo_inicio=c["periodo_inicio"],
                    periodo_fim=c["periodo_fim"],
                    hash_escopo=_hash_escopo(empresa_id, c["tema_label"], c["buckets_envolvidos"]),
                )
            )
            resumo.cruzamentos_criados += 1
    resumo.detalhes = cruzamentos
    return resumo


# ── Fase 2: cruzamentos semânticos (centróides + curadoria Haiku) ─────


@dataclass
class ResumoSemantico:
    empresa_id: int
    pares_candidatos: int = 0
    confirmados: int = 0
    filtrados: int = 0
    cruzamentos_criados: int = 0
    chamadas_llm: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    detalhes: List[Dict[str, Any]] = field(default_factory=list)
    filtrados_detalhe: List[Dict[str, Any]] = field(default_factory=list)


def _carregar_temas_centroides(empresa_id: int) -> Dict[int, Dict[str, Any]]:
    """Para cada tema ativo: centróide (média normalizada dos embeddings dos
    membros), buckets ``subpilar:tipo``, tipos, volume, datas e 2 exemplos."""
    from src.models.temas import Tema, VerbatimTema
    from src.models.verbatim import Verbatim
    from src.temas.embeddings import MODELO_PADRAO, carregar_embeddings
    from src.utils.db import db_session

    info: Dict[int, Dict[str, Any]] = {}
    with db_session() as s:
        rows = (
            s.query(
                Tema.id,
                Tema.nome,
                VerbatimTema.verbatim_id,
                VerbatimTema.bucket_chave,
                Verbatim.texto,
                Verbatim.data_criacao_original,
            )
            .join(VerbatimTema, VerbatimTema.tema_id == Tema.id)
            .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
            .filter(
                Tema.empresa_id == empresa_id,
                Tema.ativo.is_(True),
                VerbatimTema.bucket_chave.isnot(None),
            )
            .all()
        )
    for tid, nome, vid, bc, texto, data in rows:
        st = _subpilar_tipo(bc or "")
        if st is None:
            continue
        e = info.setdefault(
            tid,
            {
                "nome": nome,
                "buckets": set(),
                "tipos": set(),
                "volume": 0,
                "datas": [],
                "vids": [],
                "reps": [],
            },
        )
        e["buckets"].add(st)
        e["tipos"].add(st.split(":")[1])
        e["volume"] += 1
        e["vids"].append(vid)
        if data is not None:
            e["datas"].append(data)
        if len(e["reps"]) < 2 and texto:
            e["reps"].append(texto[:200])

    todos = [v for e in info.values() for v in e["vids"]]
    embeddings = carregar_embeddings(todos, modelo=MODELO_PADRAO)
    for tid in list(info.keys()):
        vetores = [embeddings[v] for v in info[tid]["vids"] if v in embeddings]
        if not vetores:
            del info[tid]
            continue
        c = np.mean(vetores, axis=0)
        norma = float(np.linalg.norm(c))
        info[tid]["centroide"] = c / norma if norma else c
    return info


def _pares_candidatos(
    info: Dict[int, Dict[str, Any]], threshold: float = SEMANTIC_THRESHOLD
) -> List[Tuple[float, int, int]]:
    """Pares de temas com buckets DISJUNTOS e cosine ≥ threshold, desc por cosine."""
    tids = [t for t in info if "centroide" in info[t]]
    pares: List[Tuple[float, int, int]] = []
    for i in range(len(tids)):
        for j in range(i + 1, len(tids)):
            a, b = tids[i], tids[j]
            if info[a]["buckets"].isdisjoint(info[b]["buckets"]):
                cos = float(info[a]["centroide"] @ info[b]["centroide"])
                if cos >= threshold:
                    pares.append((round(cos, 4), a, b))
    pares.sort(reverse=True)
    return pares


def _familias(pares: List[Tuple[int, int]]) -> List[set]:
    """Componentes conexas (union-find) dos pares confirmados."""
    parent: Dict[int, int] = {}

    def find(x: int) -> int:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pares:
        parent[find(a)] = find(b)
    comp: Dict[int, set] = defaultdict(set)
    for x in list(parent.keys()):
        comp[find(x)].add(x)
    return list(comp.values())


def _montar_cruzamento_familia(familia: set, info: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
    """Monta o dict de cruzamento a partir de uma família de tema_ids."""
    membros = sorted(info[t]["nome"] for t in familia)
    buckets = sorted(set().union(*[info[t]["buckets"] for t in familia]))
    tipos = sorted(set().union(*[info[t]["tipos"] for t in familia]))
    n_sub = len({b.split(":")[0] for b in buckets})
    volume = sum(info[t]["volume"] for t in familia)
    datas = [d for t in familia for d in info[t]["datas"]]
    rep = max(familia, key=lambda t: info[t]["volume"])
    return {
        "tema_label": info[rep]["nome"],
        "membros": membros,
        "buckets_envolvidos": buckets,
        "tipos_envolvidos": tipos,
        "n_subpilares_distintos": n_sub,
        "volume_total": volume,
        "peso": calcular_peso(volume, n_sub, len(tipos)),
        "periodo_inicio": (min(datas).date() if datas else datetime.utcnow().date()),
        "periodo_fim": (max(datas).date() if datas else datetime.utcnow().date()),
    }


def _confirmar_mesmo_conceito(
    tema_a: Dict[str, Any], tema_b: Dict[str, Any], prompt_path: Optional[Path] = None
) -> Tuple[bool, int, int]:
    """Curadoria via Haiku: os dois temas são o mesmo conceito de fundo?

    Returns ``(mesmo_conceito, input_tokens, output_tokens)``. Em falha de
    rede/JSON devolve ``(False, 0, 0)`` — preferimos precisão.
    """
    from src.classifier.classifier_v3 import _get_client
    from src.temas.rotulador import _parse_label_json

    system_prompt = Path(prompt_path or CURADORIA_PROMPT_PATH).read_text(encoding="utf-8")
    payload = {
        "tema_a": {
            "label": tema_a["nome"],
            "bucket": sorted(tema_a["buckets"]),
            "exemplos": tema_a["reps"],
        },
        "tema_b": {
            "label": tema_b["nome"],
            "bucket": sorted(tema_b["buckets"]),
            "exemplos": tema_b["reps"],
        },
    }
    try:
        client = _get_client()
        resposta = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=50,
            system=system_prompt,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
        raw = "".join(b.text for b in resposta.content if getattr(b, "type", None) == "text")
        usage = getattr(resposta, "usage", None)
        it = int(getattr(usage, "input_tokens", 0) or 0)
        ot = int(getattr(usage, "output_tokens", 0) or 0)
        data = _parse_label_json(raw)
        return bool(data.get("mesmo_conceito")) if isinstance(data, dict) else False, it, ot
    except Exception as exc:  # noqa: BLE001
        print(f"[temas/cruzamento] curadoria falhou: {type(exc).__name__}: {exc}")
        return False, 0, 0


def detectar_semanticos(
    empresa_id: int,
    *,
    threshold: float = SEMANTIC_THRESHOLD,
    confirmar_fn: Optional[Callable] = None,
) -> ResumoSemantico:
    """Detecta cruzamentos semânticos (sem persistir). ``confirmar_fn`` é
    injetável para testes (default = curadoria Haiku)."""
    confirmar = confirmar_fn or _confirmar_mesmo_conceito
    info = _carregar_temas_centroides(empresa_id)
    pares = _pares_candidatos(info, threshold)

    resumo = ResumoSemantico(empresa_id=empresa_id, pares_candidatos=len(pares))
    confirmados: List[Tuple[int, int]] = []
    for cos, a, b in pares:
        ok, it, ot = confirmar(info[a], info[b])
        resumo.chamadas_llm += 1
        resumo.input_tokens += it
        resumo.output_tokens += ot
        if ok:
            confirmados.append((a, b))
            resumo.confirmados += 1
        else:
            resumo.filtrados += 1
            resumo.filtrados_detalhe.append(
                {"cosine": cos, "tema_a": info[a]["nome"], "tema_b": info[b]["nome"]}
            )

    cruzamentos: List[Dict[str, Any]] = []
    for fam in _familias(confirmados):
        if len(fam) < 2:
            continue
        c = _montar_cruzamento_familia(fam, info)
        if len(c["buckets_envolvidos"]) >= 2:
            cruzamentos.append(c)
    cruzamentos.sort(key=lambda c: -c["peso"])
    resumo.detalhes = cruzamentos
    resumo.cruzamentos_criados = len(cruzamentos)
    return resumo


def _zerar_semanticos(empresa_id: int) -> None:
    from src.models.temas import TemaCruzamento
    from src.utils.db import db_session

    with db_session() as s:
        s.query(TemaCruzamento).filter(
            TemaCruzamento.empresa_id == empresa_id,
            TemaCruzamento.membros_json.isnot(None),
        ).delete(synchronize_session=False)


def detectar_e_persistir_semanticos(
    empresa_id: int,
    *,
    threshold: float = SEMANTIC_THRESHOLD,
    confirmar_fn: Optional[Callable] = None,
) -> ResumoSemantico:
    """Detecta e grava cruzamentos semânticos (membros_json setado).
    Idempotente: zera os semânticos antes; não toca nos literais."""
    from src.models.temas import TemaCruzamento
    from src.utils.db import db_session

    resumo = detectar_semanticos(empresa_id, threshold=threshold, confirmar_fn=confirmar_fn)
    _zerar_semanticos(empresa_id)
    with db_session() as s:
        for c in resumo.detalhes:
            s.add(
                TemaCruzamento(
                    empresa_id=empresa_id,
                    agrupamento_id=None,
                    tema_label=c["tema_label"],
                    buckets_envolvidos_json=json.dumps(c["buckets_envolvidos"]),
                    tipos_envolvidos_json=json.dumps(c["tipos_envolvidos"]),
                    n_subpilares_distintos=c["n_subpilares_distintos"],
                    membros_json=json.dumps(c["membros"]),
                    peso=c["peso"],
                    periodo_inicio=c["periodo_inicio"],
                    periodo_fim=c["periodo_fim"],
                    hash_escopo=_hash_escopo(empresa_id, c["tema_label"], c["buckets_envolvidos"]),
                )
            )
    return resumo
