"""Camada de leitura da Lente de Governança (CP-LG-4).

Read-only: lê de ``proximity_calculations`` / ``previsibilidade_calculations``,
com **guarda de frescor lazy** (popula no 1º acesso se a tabela estiver vazia —
espelha a guarda de ``ratios_mensais`` em ``ui._explorar_evolucao``). Em produção
o passo 7.5 do pós-coleta mantém os dados frescos.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def garantir_governanca(empresa_id: int) -> None:
    """Popula a governança se ``proximity_calculations`` estiver vazia p/ a empresa."""
    from src.governanca.metricas import recalcular_governanca
    from src.models.governanca import ProximityCalculation
    from src.utils.db import db_session

    with db_session() as s:
        existe = (
            s.query(ProximityCalculation.id)
            .filter(ProximityCalculation.empresa_id == empresa_id)
            .first()
        )
    if existe is None:
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
    """Linha agregada de Proximity de cada loja → ``{local_id: {valor, faixa}}``.
    Usado pelo Leaderboard (1 query)."""
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
    return {lid: {"valor": v, "faixa": f} for lid, v, f in rows}


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
