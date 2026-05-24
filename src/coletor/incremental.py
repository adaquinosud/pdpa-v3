"""Cálculo da data inicial de coleta — compartilhado entre coletores.

Função única ``calcular_data_inicio_coleta(fonte_id)`` que resolve a data
inicial de coleta via 3 níveis de precedência. Usada por todos os coletores
(google, instagram, facebook, ...) para garantir consistência:

- Mesma lógica de coleta incremental em toda fonte.
- Mesma resposta a override de env (testes/diagnóstico).
- Mesmo fallback global.

A função devolve uma string ISO ``YYYY-MM-DD`` pronta para passar a
parâmetros Apify como ``reviewsStartDate``, ``onlyPostsNewerThan``,
``startDate``, etc.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta

from sqlalchemy import func

from src.models.verbatim import Verbatim
from src.utils.db import db_session


INCREMENTAL_BUFFER_DAYS = 7  # sobreposição para pegar reviews editados/republicados


def _janela_meses() -> int:
    """Janela padrão de coleta em meses, lida de env (fallback 15)."""
    try:
        return int(os.environ.get("PDPA_COLETA_JANELA_MESES", "15"))
    except (TypeError, ValueError):
        return 15


# Alias compatível com código que importava DEFAULT_DESDE_MESES como constante.
# Avaliação preguiçosa via property em módulo não é trivial; mantemos o
# fallback de 15 acessível para imports legacy.
DEFAULT_DESDE_MESES = 15


def calcular_data_inicio_coleta(fonte_id: int) -> str:
    """Resolve a data inicial de coleta para uma Fonte (3 níveis de precedência).

    Precedência:

    1. ``PDPA_COLETA_DESDE_OVERRIDE`` em env — bypassa incremental,
       força a data informada. Útil para testes e recoletas forçadas.
    2. ``MAX(Verbatim.data_criacao_original) WHERE fonte_id=?`` −
       ``INCREMENTAL_BUFFER_DAYS`` — incremental por fonte usando o
       schema v3 (sem JOIN, mais simples que o v2).
    3. ``PDPA_COLETA_DESDE`` em env, ou fallback ``hoje − 15 meses``.

    Args:
        fonte_id: ID da Fonte para query incremental.

    Returns:
        Data ISO (``YYYY-MM-DD``) compatível com parâmetros Apify
        (``reviewsStartDate``, ``onlyPostsNewerThan``, etc.).
    """
    override = os.environ.get("PDPA_COLETA_DESDE_OVERRIDE")
    if override:
        return override

    with db_session() as session:
        max_data = (
            session.query(func.max(Verbatim.data_criacao_original))
            .filter(Verbatim.fonte_id == fonte_id)
            .scalar()
        )
    if max_data is not None:
        try:
            if isinstance(max_data, datetime):
                d = max_data.date()
            elif isinstance(max_data, date):
                d = max_data
            else:
                d = date.fromisoformat(str(max_data)[:10])
            return (d - timedelta(days=INCREMENTAL_BUFFER_DAYS)).isoformat()
        except (ValueError, TypeError):
            pass

    default_env = os.environ.get("PDPA_COLETA_DESDE")
    if default_env:
        return default_env
    return (date.today() - timedelta(days=_janela_meses() * 30)).isoformat()
