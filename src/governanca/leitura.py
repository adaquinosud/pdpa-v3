"""Camada de leitura da Lente de Governança (CP-LG-4).

Read-only: lê de ``proximity_calculations`` / ``previsibilidade_calculations``,
com **guarda de frescor lazy** (popula no 1º acesso se a tabela estiver vazia —
espelha a guarda de ``ratios_mensais`` em ``ui._explorar_evolucao``). Em produção
o passo 7.5 do pós-coleta mantém os dados frescos.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def garantir_governanca(empresa_id: int) -> None:
    """Popula a governança se Proximity OU Gini estiverem vazios p/ a empresa
    (recalcular_governanca pula o que já está fresco via hash)."""
    from src.governanca.metricas import recalcular_governanca
    from src.models.governanca import GiniConcentracao, ProximityCalculation
    from src.utils.db import db_session

    with db_session() as s:
        tem_prox = (
            s.query(ProximityCalculation.id)
            .filter(ProximityCalculation.empresa_id == empresa_id)
            .first()
        )
        tem_gini = (
            s.query(GiniConcentracao.id).filter(GiniConcentracao.empresa_id == empresa_id).first()
        )
    if tem_prox is None or tem_gini is None:
        recalcular_governanca(empresa_id)


def escopo_de_filtros(agrupamento_id, local_id) -> Tuple[str, Optional[int]]:
    """(escopo_tipo, escopo_id) a partir dos filtros do painel. local > ag > empresa."""
    if local_id:
        return "loja", int(local_id)
    if agrupamento_id:
        return "agrupamento", int(agrupamento_id)
    return "empresa", None


def proximity_escopo(
    s, empresa_id: int, escopo_tipo: str, escopo_id: Optional[int]
) -> Dict[str, Any]:
    """Linha agregada (subpilar e pilar NULL) de Proximity do escopo.
    ``{valor, faixa}`` — None/None se sem dado suficiente ou sem linha."""
    from src.models.governanca import ProximityCalculation as PC

    cond_id = PC.escopo_id.is_(None) if escopo_id is None else (PC.escopo_id == escopo_id)
    row = (
        s.query(PC.proximity_0_100, PC.faixa)
        .filter(
            PC.empresa_id == empresa_id,
            PC.escopo_tipo == escopo_tipo,
            cond_id,
            PC.subpilar.is_(None),
            PC.pilar.is_(None),
        )
        .first()
    )
    return {"valor": row[0], "faixa": row[1]} if row else {"valor": None, "faixa": None}


def proximity_por_loja(s, empresa_id: int) -> Dict[int, Dict[str, Any]]:
    """Proximity agregada de cada loja → ``{local_id: {valor, faixa, n_pilares}}``.

    ``n_pilares`` = nº de pilares COM lastro (pilar-level com proximity não-NULL)
    que embasam o agregado — sinaliza confiança parcial no Leaderboard
    (mono/bi-pilar). Usado pelo Leaderboard (2 queries, sem N+1)."""
    from sqlalchemy import func

    from src.models.governanca import ProximityCalculation as PC

    rows = (
        s.query(PC.escopo_id, PC.proximity_0_100, PC.faixa)
        .filter(
            PC.empresa_id == empresa_id,
            PC.escopo_tipo == "loja",
            PC.subpilar.is_(None),
            PC.pilar.is_(None),
        )
        .all()
    )
    n_pilares = dict(
        s.query(PC.escopo_id, func.count(PC.id))
        .filter(
            PC.empresa_id == empresa_id,
            PC.escopo_tipo == "loja",
            PC.pilar.isnot(None),
            PC.proximity_0_100.isnot(None),
        )
        .group_by(PC.escopo_id)
        .all()
    )
    return {
        lid: {"valor": v, "faixa": f, "n_pilares": int(n_pilares.get(lid, 0))} for lid, v, f in rows
    }


def proximity_subpilares_escopo(
    s, empresa_id: int, escopo_tipo: str, escopo_id: Optional[int]
) -> Dict[str, Dict[str, Any]]:
    """Linhas subpilar-level de Proximity do escopo → ``{subpilar: {valor, faixa}}``.
    Usado pela coluna Proximity do Confronto Visual."""
    from src.models.governanca import ProximityCalculation as PC

    cond_id = PC.escopo_id.is_(None) if escopo_id is None else (PC.escopo_id == escopo_id)
    rows = (
        s.query(PC.subpilar, PC.proximity_0_100, PC.faixa)
        .filter(
            PC.empresa_id == empresa_id,
            PC.escopo_tipo == escopo_tipo,
            cond_id,
            PC.subpilar.isnot(None),
        )
        .all()
    )
    return {sub: {"valor": v, "faixa": f} for sub, v, f in rows}


def gini_escopo(
    s, empresa_id: int, escopo_tipo: str, escopo_id: Optional[int]
) -> Optional[Dict[str, Any]]:
    """Lê a linha de ``gini_concentracao`` do escopo → dict pronto p/ a UI
    (gini bruto + corrigido + faixa + bolsão + lojas). None se não há linha."""
    import json

    from src.models.governanca import GiniConcentracao as GC

    cond = GC.escopo_id.is_(None) if escopo_id is None else (GC.escopo_id == escopo_id)
    row = (
        s.query(GC.gini, GC.top_n_lojas, GC.distribuicao_json)
        .filter(GC.empresa_id == empresa_id, GC.escopo_tipo == escopo_tipo, cond)
        .first()
    )
    if row is None:
        return None
    dj = json.loads(row[2]) if row[2] else {}
    return {
        "gini_bruto": row[0],
        "gini_corrigido": dj.get("gini_corrigido"),
        "faixa": dj.get("faixa"),
        "top_n": dj.get("top_n"),
        "share": dj.get("share"),
        "total_lojas": dj.get("total_lojas"),
        "total_detratores": dj.get("total_detratores"),
        "lojas": dj.get("lojas", []),
        "insuficiente": dj.get("insuficiente", False),
        "motivo": dj.get("motivo"),
    }


def leitura_concentracao(d: Optional[Dict[str, Any]]) -> str:
    """Leitura editorial determinística ($0 LLM) da concentração."""
    if d is None or d.get("insuficiente"):
        if d and d.get("motivo") == "sem_detratores":
            return "Sem detratores registrados neste escopo — nada a concentrar."
        return "Concentração indisponível — menos de 5 lojas medidas neste escopo."
    share_pct = round((d.get("share") or 0) * 100)
    base_pct = round(100 * d["top_n"] / d["total_lojas"]) if d.get("total_lojas") else 0
    nome = {"baixa": "baixa (distribuída)", "media": "média", "alta": "alta (concentrada)"}.get(
        d.get("faixa"), d.get("faixa")
    )
    return (
        f"{share_pct}% dos detratores concentram-se em {d['top_n']} de "
        f"{d['total_lojas']} lojas ({base_pct}% da base) → concentração {nome}."
    )


def previsibilidade_loja(s, empresa_id: int, local_id: int) -> Dict[str, Any]:
    """Previsibilidade LG-2 (CV temporal puro) de uma loja.
    ``{valor, faixa, n_meses, cv}`` — None se sem linha/dado."""
    from src.models.governanca import PrevisibilidadeCalculation as PV

    row = (
        s.query(PV.previsibilidade_0_100, PV.faixa, PV.n_meses, PV.cv)
        .filter(PV.empresa_id == empresa_id, PV.escopo_tipo == "loja", PV.escopo_id == local_id)
        .first()
    )
    if row is None:
        return {"valor": None, "faixa": None, "n_meses": None, "cv": None}
    return {"valor": row[0], "faixa": row[1], "n_meses": row[2], "cv": row[3]}
