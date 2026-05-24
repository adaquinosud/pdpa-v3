"""Coletor TripAdvisor — PDPA v3.

Reaproveitado de ``pdpa-v2/coletor/tripadvisor.py``. Ator:
``maxcopell/tripadvisor-reviews`` (renomeado em 2026; antes era
``maxcopell/tripadvisor`` mas foi descontinuado).
fonte.url = URL completa do place no TripAdvisor.

Adaptações: sem cloudscraper/Oxylabs fallback; sem CLI; incremental via
``incremental.py``; rating ignorado (decisão A); título+texto concatenados;
``stats`` no padrão google.py.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional

from src.coletor.apify import ApifyError, run_and_collect
from src.coletor.incremental import calcular_data_inicio_coleta
from src.coletor.pipeline import processar_verbatim_coletado
from src.models.fonte import Fonte


ATOR_APIFY = "maxcopell/tripadvisor-reviews"
MAX_REVIEWS_DEFAULT = 500
APIFY_TIMEOUT_SECONDS = 900


def _parse_data(value: Any) -> Optional[datetime]:
    """ISO string ou ISO date; retorna None se não parsear."""
    if not value:
        return None
    s = str(value).strip()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(s[:10])
    except ValueError:
        return None


def _extrair_review(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extrai (texto, autor, data). Concatena título+texto quando disponíveis."""
    texto = (item.get("text") or item.get("review") or item.get("reviewBody") or "").strip()
    if not texto:
        return None
    titulo = (item.get("title") or item.get("reviewTitle") or "").strip()
    if titulo:
        texto = f"{titulo}. {texto}"

    user_field = item.get("user")
    if isinstance(user_field, dict):
        autor_raw = user_field.get("username", "") or ""
    else:
        autor_raw = item.get("userName") or item.get("author") or ""
    autor_raw = str(autor_raw).strip()
    autor: Optional[str] = autor_raw or None

    data_original = _parse_data(
        item.get("publishedDate") or item.get("date") or item.get("createdDate")
    )
    # CP-E2: id estável do review no TripAdvisor
    rid_raw = item.get("id") or item.get("reviewId") or item.get("tripAdvisorReviewId") or ""
    review_id_externo: Optional[str] = str(rid_raw).strip() or None
    return {
        "texto": texto,
        "autor": autor,
        "data_original": data_original,
        "review_id_externo": review_id_externo,
    }


def coletar(fonte: Fonte) -> Dict[str, Any]:
    """Coleta reviews do TripAdvisor para uma Fonte via Apify.

    Args:
        fonte: Fonte com ``conector_tipo='tripadvisor'``. ``fonte.url``
            deve ser a URL do place no TripAdvisor.

    Returns:
        Dict ``{coletados, novos, duplicados, erros, falhou_apify}``.
    """
    fonte_id = fonte.id
    url = (fonte.url or "").strip()
    stats: Dict[str, Any] = {
        "coletados": 0,
        "novos": 0,
        "duplicados": 0,
        "erros": 0,
        "falhou_apify": False,
    }

    if not url:
        print(f"[tripadvisor] fonte {fonte_id} sem url — abortando")
        stats["falhou_apify"] = True
        return stats

    data_inicio_iso = calcular_data_inicio_coleta(fonte_id)
    data_inicio = _parse_data(data_inicio_iso)
    run_input = {"startUrls": [{"url": url}], "maxReviews": MAX_REVIEWS_DEFAULT, "language": "pt"}
    print(
        f"[tripadvisor] fonte {fonte_id} ({url}) data_inicio={data_inicio_iso} "
        f"(filtro pós-coleta), max_reviews={MAX_REVIEWS_DEFAULT}"
    )

    try:
        items = run_and_collect(ATOR_APIFY, run_input, timeout=APIFY_TIMEOUT_SECONDS)
    except ApifyError as exc:
        print(f"[tripadvisor] Apify falhou para fonte {fonte_id}: {exc}")
        stats["falhou_apify"] = True
        return stats

    for item in items:
        stats["coletados"] += 1
        review = _extrair_review(item)
        if review is None:
            continue
        if (
            data_inicio is not None
            and review["data_original"] is not None
            and review["data_original"].date() < data_inicio.date()
        ):
            continue
        try:
            verbatim = processar_verbatim_coletado(
                texto=review["texto"],
                fonte=fonte,
                data_original=review["data_original"],
                autor=review["autor"],
                review_id_externo=review["review_id_externo"],
            )
            if verbatim is not None:
                stats["novos"] += 1
            else:
                stats["duplicados"] += 1
        except Exception as exc:
            stats["erros"] += 1
            print(
                f"[tripadvisor] erro ao processar review da fonte {fonte_id}: "
                f"{type(exc).__name__}: {exc}"
            )

    # Ignorado: rating (string 'X of 5 bubbles' ou int). Pendência item 40.
    _ = re  # silenciar import não usado em runtime; mantido para parser de rating se voltar

    print(
        f"[tripadvisor] fonte {fonte_id} fim: coletados={stats['coletados']} "
        f"novos={stats['novos']} duplicados={stats['duplicados']} "
        f"erros={stats['erros']} falhou_apify={stats['falhou_apify']}"
    )
    return stats
