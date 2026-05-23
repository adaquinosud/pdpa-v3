"""Coletor Mercado Livre — PDPA v3.

Reaproveitado de ``pdpa-v2/coletor/mercadolivre.py``. **2 atores Apify**:

1. ``viralanalyzer/mercadolivre-scraper`` — lista produtos do seller.
2. ``saswave/mercadolibre-reviews-scraper`` — busca reviews dos SKUs.

fonte.url = ``seller_id`` (ex: ``MAGALU``, ``AMARO``).

Adaptações: rating ignorado (decisão A); sem CLI; incremental via
``incremental.py``; ``stats`` no padrão google.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from src.coletor.apify import ApifyError, run_and_collect
from src.coletor.incremental import calcular_data_inicio_coleta
from src.coletor.pipeline import processar_verbatim_coletado
from src.models.fonte import Fonte


STORE_ACTOR = "viralanalyzer/mercadolivre-scraper"
REVIEWS_ACTOR = "saswave/mercadolibre-reviews-scraper"
MAX_REVIEWS_DEFAULT = 200
MAX_SKUS = 30
APIFY_TIMEOUT_SECONDS = 600


def _parse_data(value: Any) -> Optional[datetime]:
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


def coletar(fonte: Fonte) -> Dict[str, Any]:
    """Coleta reviews de produtos do seller no Mercado Livre via Apify (2 atores)."""
    fonte_id = fonte.id
    seller_id = (fonte.url or "").strip()
    stats: Dict[str, Any] = {
        "coletados": 0,
        "novos": 0,
        "duplicados": 0,
        "erros": 0,
        "falhou_apify": False,
    }
    if not seller_id:
        print(f"[mercadolivre] fonte {fonte_id} sem url/seller_id — abortando")
        stats["falhou_apify"] = True
        return stats

    data_inicio_iso = calcular_data_inicio_coleta(fonte_id)
    data_inicio = _parse_data(data_inicio_iso)

    # Passo 1: descobre SKUs do seller
    print(f"[mercadolivre] fonte {fonte_id} ({seller_id}) passo 1/2: store scraper")
    try:
        products = run_and_collect(
            STORE_ACTOR,
            {"searchQuery": seller_id, "maxItems": 50, "domain": "mercadolivre.com.br"},
            timeout=APIFY_TIMEOUT_SECONDS,
        )
    except ApifyError as exc:
        print(f"[mercadolivre] store scraper falhou para fonte {fonte_id}: {exc}")
        stats["falhou_apify"] = True
        return stats

    skus: List[str] = []
    for product in products:
        sku = product.get("id") or product.get("itemId") or ""
        if sku:
            skus.append(str(sku))
    skus = list(set(skus))[:MAX_SKUS]
    if not skus:
        skus = [seller_id]  # fallback: tenta usar seller_id como SKU genérico
    print(f"[mercadolivre] fonte {fonte_id} encontrou {len(skus)} SKUs")

    # Passo 2: busca reviews dos SKUs
    print(f"[mercadolivre] fonte {fonte_id} passo 2/2: reviews scraper")
    try:
        reviews_data = run_and_collect(
            REVIEWS_ACTOR,
            {
                "domain": "mercadolivre.com.br",
                "skus": skus,
                "max_reviews_per_product": MAX_REVIEWS_DEFAULT // max(len(skus), 1),
                "order": "recent",
            },
            timeout=APIFY_TIMEOUT_SECONDS,
        )
    except ApifyError as exc:
        print(f"[mercadolivre] reviews scraper falhou para fonte {fonte_id}: {exc}")
        stats["falhou_apify"] = True
        return stats

    for review in reviews_data:
        texto = (review.get("content") or review.get("text") or review.get("review") or "").strip()
        if not texto:
            continue
        stats["coletados"] += 1
        autor_raw = (
            review.get("author") or review.get("user") or review.get("nickname") or ""
        ).strip()
        autor: Optional[str] = autor_raw or None
        c_data = _parse_data(
            review.get("date") or review.get("date_created") or review.get("dateCreated")
        )
        if data_inicio is not None and c_data is not None and c_data.date() < data_inicio.date():
            continue
        try:
            verbatim = processar_verbatim_coletado(
                texto=texto, fonte=fonte, data_original=c_data, autor=autor
            )
            if verbatim is not None:
                stats["novos"] += 1
            else:
                stats["duplicados"] += 1
        except Exception as exc:
            stats["erros"] += 1
            print(
                f"[mercadolivre] erro ao processar review da fonte {fonte_id}: "
                f"{type(exc).__name__}: {exc}"
            )

    print(
        f"[mercadolivre] fonte {fonte_id} fim: coletados={stats['coletados']} "
        f"novos={stats['novos']} duplicados={stats['duplicados']} "
        f"erros={stats['erros']} falhou_apify={stats['falhou_apify']}"
    )
    return stats
