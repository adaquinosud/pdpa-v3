"""Janela temporal dos temas (Bloco 6.6 CP-2).

A análise de temas é ancorada nos últimos N dias **a partir da última coleta**
da empresa (não de "hoje") — assim o horizonte acompanha o ritmo de coleta.

- ``ULTIMA_COLETA`` = ``MAX(verbatins.data_coleta)`` da empresa.
- ``DATA_CORTE`` = ``ULTIMA_COLETA − N dias``.
- ``N`` = env ``PDPA_TEMAS_JANELA_DIAS`` (default 180).

Pipeline, cruzamento e ação filtram verbatins com
``data_criacao_original >= DATA_CORTE`` (verbatins sem data entram — não
dá pra datar a recência, melhor não descartar).

Razão (decisão): 180 dias é o horizonte acionável; além disso vira paisagem
histórica.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

JANELA_DIAS_DEFAULT = 180


def get_janela_dias() -> int:
    """Lê ``PDPA_TEMAS_JANELA_DIAS`` (fallback 180)."""
    try:
        v = int(os.environ.get("PDPA_TEMAS_JANELA_DIAS", JANELA_DIAS_DEFAULT))
        return v if v > 0 else JANELA_DIAS_DEFAULT
    except (TypeError, ValueError):
        return JANELA_DIAS_DEFAULT


def data_corte(empresa_id: int, session=None) -> Optional[datetime]:
    """``MAX(data_coleta) − janela`` da empresa. ``None`` se não há coleta.

    ``None`` significa "sem corte" — o caller não aplica filtro temporal.
    """
    from sqlalchemy import func

    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    def _calc(s) -> Optional[datetime]:
        ultima = (
            s.query(func.max(Verbatim.data_coleta))
            .filter(Verbatim.empresa_id == empresa_id)
            .scalar()
        )
        if ultima is None:
            return None
        return ultima - timedelta(days=get_janela_dias())

    if session is not None:
        return _calc(session)
    with db_session() as s:
        return _calc(s)


def filtro_janela(corte: Optional[datetime]):
    """Cláusula SQLAlchemy p/ ``Verbatim`` dentro da janela (inclui sem data).

    Devolve ``None`` quando ``corte`` é ``None`` (sem filtro).
    """
    if corte is None:
        return None
    from sqlalchemy import or_

    from src.models.verbatim import Verbatim

    return or_(
        Verbatim.data_criacao_original >= corte,
        Verbatim.data_criacao_original.is_(None),
    )
