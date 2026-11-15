"""Rodapé de período dos impressos (decisão de 15/11): cada impresso declara o período de cada
número que mostra. "Todo o histórico" soa como período escolhido e não é — é só o que a coleta
trouxe — por isso o rótulo é ``DESDE_PRIMEIRO``, com a faixa real dos registros ao lado.

Os períodos com janela própria saem das constantes que governam cada conta, nunca escritos aqui
(copy não reencoda limiar)."""

from __future__ import annotations

from typing import List, Optional, Tuple

DESDE_PRIMEIRO = "desde o primeiro registro coletado"


def faixa_registros(empresa_id: int) -> Optional[Tuple[str, str]]:
    """Primeiro e último mês dos registros da empresa (``MM/AAAA``), pela data em que o cliente
    escreveu, com a data de coleta quando ela falta. ``None`` sem registro datado."""
    from sqlalchemy import func

    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    dt = func.coalesce(Verbatim.data_criacao_original, Verbatim.data_coleta)
    with db_session() as s:
        mn, mx = s.query(func.min(dt), func.max(dt)).filter(Verbatim.empresa_id == empresa_id).one()
    if mn is None or mx is None:
        return None
    return mn.strftime("%m/%Y"), mx.strftime("%m/%Y")


def _faixa(f: Optional[Tuple[str, str]]) -> str:
    if f is None:
        return ""
    a, b = f
    return f" ({a})" if a == b else f" ({a}–{b})"


def _meses(dias: int) -> str:
    return f"{dias // 30} meses" if dias % 30 == 0 else f"{dias} dias"


def _trimestre(q: str) -> str:
    """``2025-Q3`` → ``T3/2025``."""
    return f"T{q[-1]}/{q[:4]}"


def rodape_periodo(
    empresa_id: int,
    tipo: str,
    *,
    quarters: Optional[List[str]] = None,
    ra: Optional[Tuple[Optional[str], Optional[str]]] = None,
) -> Optional[str]:
    """A linha de período do rodapé de cada impresso. ``quarters`` = os trimestres que o
    longitudinal de fato usou; ``ra`` = (início, fim) da coleta do Reclame Aqui já em ``MM/AAAA``.
    ``None`` para tipo sem número (em construção)."""
    from src.api.painel import JANELA_CONCENTRACAO_MESES, JANELA_PREVISIBILIDADE_MESES
    from src.governanca.leitura import TRAJETORIA_JANELA_MESES
    from src.temas.janela import get_janela_dias

    desde = DESDE_PRIMEIRO + _faixa(faixa_registros(empresa_id))
    if tipo in ("resumo_executivo", "diagnostico_pontual"):
        return f"Razão, índice e assuntos: {desde}"
    if tipo == "plano_executivo":
        return f"Razão, índice e assuntos: {desde} · Ações: últimos {_meses(get_janela_dias())}"
    if tipo == "diagnostico_longitudinal":
        tri = ""
        if quarters:
            tri = (
                f"{len(quarters)} trimestres: {_trimestre(quarters[0])} a "
                f"{_trimestre(quarters[-1])} · "
            )
        return f"{tri}Gargalo atual: {desde}"
    if tipo == "painel_governanca":
        k = TRAJETORIA_JANELA_MESES
        return (
            f"Trajetória: {k} contra {k} meses · Concentração: {JANELA_CONCENTRACAO_MESES} meses"
            f" · Previsibilidade: {JANELA_PREVISIBILIDADE_MESES} meses · Demais: {desde}"
        )
    if tipo == "parecer":
        linha = f"Razão e assuntos: {desde}"
        if ra and ra[0] and ra[1]:
            linha += f" · Reclame Aqui: {ra[0]}" + ("" if ra[0] == ra[1] else f"–{ra[1]}")
        return linha
    return None
