"""Engajamento — indicador básico (pré-condição operacional do PDPA).

NÃO é 5º pilar: sinaliza se há *volume/diversidade/regularidade* suficientes para
os demais indicadores não serem especulativos. Três usos (Bloco Engajamento):

1. **Índice de Engajamento** (0-100) — 4º indicador, ao lado de Índice Geral,
   Previsibilidade e Concentração.
2. **Selo de confiança** por volume (🟢 ≥30 / 🟡 10-30 / 🔴 <10) — anota
   confiabilidade nas telas; não muda fórmula.
3. **Modulação do Leaderboard** — score × (engajamento/100) + gate de volume.

Fórmula: ``(volume_norm × 0.5) + (diversidade × 0.3) + (consistencia × 0.2)`` ×100.
- volume_norm = log1p(volume) / log1p(volume_máx do escopo) — log1p evita log(0/1).
- diversidade = fontes ativas / fontes cadastradas (do próprio escopo: loja→fontes
  da loja; empresa→fontes da empresa). Cap 1.0.
- consistencia = meses com verbatim / total de meses na janela.
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

# Pesos da fórmula (Cap. 4 — Indicadores Quantitativos; pendência editorial).
PESO_VOLUME = 0.5
PESO_DIVERSIDADE = 0.3
PESO_CONSISTENCIA = 0.2

# Gate/selo de confiança estatística por volume.
VOLUME_CONFIANCA_ALTA = 30
VOLUME_CONFIANCA_MEDIA = 10  # 10-30 média; < 10 baixa


def indice_engajamento(
    volume: int,
    volume_max: int,
    fontes_ativas: int,
    fontes_cadastradas: int,
    meses_com_verbatim: int,
    meses_total: int,
) -> int:
    """Índice de Engajamento (0-100) do escopo. Componentes em [0,1], pesos
    0.5/0.3/0.2. Robusto a zero (log1p, denominadores defendidos)."""
    vol_norm = math.log1p(max(0, volume)) / math.log1p(volume_max) if volume_max > 0 else 0.0
    diversidade = min(1.0, fontes_ativas / fontes_cadastradas) if fontes_cadastradas > 0 else 0.0
    consistencia = (meses_com_verbatim / meses_total) if meses_total > 0 else 0.0
    bruto = (
        vol_norm * PESO_VOLUME + diversidade * PESO_DIVERSIDADE + consistencia * PESO_CONSISTENCIA
    )
    return round(min(1.0, max(0.0, bruto)) * 100)


def fator_confianca(indice_eng: int) -> float:
    """Fator de modulação do Leaderboard = engajamento normalizado (0-1)."""
    return max(0.0, min(100, indice_eng)) / 100.0


def selo_confianca(volume: int) -> Tuple[str, str, str]:
    """Selo de confiança estatística por volume → (nivel, emoji, classe Tailwind)."""
    if volume >= VOLUME_CONFIANCA_ALTA:
        return ("alta", "🟢", "text-emerald-600")
    if volume >= VOLUME_CONFIANCA_MEDIA:
        return ("media", "🟡", "text-amber-600")
    return ("baixa", "🔴", "text-rose-600")


def volume_suficiente_ranking(volume: int) -> bool:
    """Gate do ranking principal do Leaderboard: só entra quem tem confiança
    'alta' (≥30 verbatins, selo 🟢). 10-30 vai p/ 'em formação', <10 p/ 'volume
    insuficiente'. Calibração 2026-05-27 (Google News c/ 11 verbatins liderava)."""
    return volume >= VOLUME_CONFIANCA_ALTA


def engajamento_escopo(empresa_id: int, s, base_query_args: Dict) -> Dict:
    """Índice de Engajamento de um escopo (empresa/agrupamento/local) — camada de
    dados. No nível empresa o volume_norm satura (volume_max=volume → 1.0): o
    índice fica em [50,100] e diferencia por diversidade+consistência; o selo
    (volume absoluto) carrega o sinal de volume insuficiente. Mesmos filtros do
    painel (agrupamento/local/fonte/período)."""
    from sqlalchemy import func

    from src.models.fonte import Fonte
    from src.models.local import Local
    from src.models.verbatim import Verbatim

    q = s.query(Verbatim).filter(Verbatim.empresa_id == empresa_id)
    ag = base_query_args.get("agrupamento_id")
    if ag:
        try:
            locais_ag = [
                lid
                for (lid,) in s.query(Local.id)
                .filter_by(empresa_id=empresa_id, agrupamento_id=int(ag))
                .all()
            ]
            q = q.filter(Verbatim.local_id.in_(locais_ag or [-1]))
        except (ValueError, TypeError):
            pass
    if base_query_args.get("local_id"):
        try:
            q = q.filter(Verbatim.local_id == int(base_query_args["local_id"]))
        except (ValueError, TypeError):
            pass
    if base_query_args.get("fonte_id"):
        try:
            q = q.filter(Verbatim.fonte_id == int(base_query_args["fonte_id"]))
        except (ValueError, TypeError):
            pass
    if base_query_args.get("data_inicio_periodo"):
        q = q.filter(Verbatim.data_criacao_original >= base_query_args["data_inicio_periodo"])

    volume = q.count()
    fontes_ativas = q.with_entities(func.count(func.distinct(Verbatim.fonte_id))).scalar() or 0
    fontes_cad = s.query(func.count(Fonte.id)).filter(Fonte.empresa_id == empresa_id).scalar() or 0
    mes = func.strftime("%Y-%m", Verbatim.data_criacao_original)
    meses_com = (
        q.with_entities(func.count(func.distinct(mes)))
        .filter(Verbatim.data_criacao_original.isnot(None))
        .scalar()
        or 0
    )
    meses_total = (
        s.query(func.count(func.distinct(mes)))
        .filter(Verbatim.empresa_id == empresa_id, Verbatim.data_criacao_original.isnot(None))
        .scalar()
        or 0
    )
    # volume_max = volume → vol_norm satura em 1.0 no agregado (ver docstring).
    idx = indice_engajamento(volume, volume, fontes_ativas, fontes_cad, meses_com, meses_total)
    comp = componentes_engajamento(
        volume, volume, fontes_ativas, fontes_cad, meses_com, meses_total
    )
    nivel, emoji, _ = selo_confianca(volume)
    return {
        "indice": idx,
        "componentes": comp,
        "volume": volume,
        "fontes_ativas": fontes_ativas,
        "fontes_cadastradas": fontes_cad,
        "selo": nivel,
        "selo_emoji": emoji,
    }


def engajamento_por_loja(empresa_id: int, s, ag_id=None, corte=None) -> Dict[int, Dict]:
    """Índice de Engajamento por loja (CP-E3) — normalização **relativa**:
    volume_max = maior volume entre as lojas do escopo (loja comparada às pares).
    Reutilizado pela modulação do Leaderboard. Retorna dict[loja_id] -> {engajamento,
    volume, selo, selo_emoji}."""
    from sqlalchemy import func

    from src.models.fonte import Fonte
    from src.models.local import Local
    from src.models.verbatim import Verbatim

    base = s.query(Verbatim).filter(
        Verbatim.empresa_id == empresa_id, Verbatim.local_id.isnot(None)
    )
    if ag_id is not None:
        locais_ag = [
            lid
            for (lid,) in s.query(Local.id)
            .filter_by(empresa_id=empresa_id, agrupamento_id=ag_id)
            .all()
        ]
        base = base.filter(Verbatim.local_id.in_(locais_ag or [-1]))
    if corte is not None:
        base = base.filter(Verbatim.data_criacao_original >= corte)

    mes = func.strftime("%Y-%m", Verbatim.data_criacao_original)
    rows = (
        base.with_entities(
            Verbatim.local_id,
            func.count(Verbatim.id),
            func.count(func.distinct(Verbatim.fonte_id)),
            func.count(func.distinct(mes)),
        )
        .group_by(Verbatim.local_id)
        .all()
    )
    vol = {lid: v for lid, v, _fa, _mc in rows}
    fativas = {lid: fa for lid, _v, fa, _mc in rows}
    mcom = {lid: mc for lid, _v, _fa, mc in rows}

    fcad_rows = (
        s.query(Fonte.entidade_id, func.count(Fonte.id))
        .filter(Fonte.empresa_id == empresa_id, Fonte.entidade_tipo == "local")
        .group_by(Fonte.entidade_id)
        .all()
    )
    fcad = {eid: c for eid, c in fcad_rows}
    meses_total = (
        base.with_entities(func.count(func.distinct(mes)))
        .filter(Verbatim.data_criacao_original.isnot(None))
        .scalar()
        or 0
    )
    vol_max = max(vol.values()) if vol else 0

    out = {}
    for lid, v in vol.items():
        eng = indice_engajamento(
            v, vol_max, fativas.get(lid, 0), fcad.get(lid, 0), mcom.get(lid, 0), meses_total
        )
        nivel, emoji, _ = selo_confianca(v)
        out[lid] = {"engajamento": eng, "volume": v, "selo": nivel, "selo_emoji": emoji}
    return out


def componentes_engajamento(
    volume: int,
    volume_max: int,
    fontes_ativas: int,
    fontes_cadastradas: int,
    meses_com_verbatim: int,
    meses_total: int,
) -> Dict[str, float]:
    """Componentes normalizados (0-1) — p/ exibir o detalhe do índice no card."""
    return {
        "volume_norm": round(
            math.log1p(max(0, volume)) / math.log1p(volume_max) if volume_max > 0 else 0.0, 3
        ),
        "diversidade": round(
            min(1.0, fontes_ativas / fontes_cadastradas) if fontes_cadastradas > 0 else 0.0, 3
        ),
        "consistencia": round((meses_com_verbatim / meses_total) if meses_total > 0 else 0.0, 3),
    }
