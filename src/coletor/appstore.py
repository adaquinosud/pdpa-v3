"""Coletor App Store (Google Play + Apple) — PDPA v3.

Reaproveitado de ``pdpa-v2/coletor/appstore.py``. **2 atores Apify** — um
para Android (``agents/googleplay-reviews``), um para iOS
(``agents/appstore-reviews``).

**Histórico de atores** (CP-C / Grupo C — 2026-05-24):

Os atores originais ``apify/google-play-scraper`` e ``apify/app-store-scraper``
foram **descontinuados** sem substituto oficial pela Apify. As coletas
disparadas retornavam ``Apify falhou (record-not-found)`` em <1s. Trocados
por atores ``agents/*``, da mesma organização para iOS+Android, com
modelo PAY_PER_EVENT (cobra por review coletado, sem assinatura mensal).

**Convenção fonte.url:**

- Se começa com ``id`` ou é só dígitos → **iOS** (ex: ``id1234567890`` ou ``1234567890``).
- Caso contrário → **Android** (package name, ex: ``com.nespresso.app``).

Adaptações: rating ignorado (decisão A); título+texto concatenados quando
ambos presentes (iOS); sem CLI; incremental via ``incremental.py``;
``stats`` no padrão google.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from src.coletor.apify import ApifyError, run_and_collect
from src.coletor.incremental import calcular_data_inicio_coleta
from src.coletor.pipeline import processar_verbatim_coletado
from src.models.fonte import Fonte


PLAY_ACTOR = "agents/googleplay-reviews"
IOS_ACTOR = "agents/appstore-reviews"
MAX_REVIEWS_DEFAULT = 500
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


def _eh_ios(url: str) -> bool:
    """Detecta plataforma a partir de ``fonte.url`` (decisão CP5: Onda 2)."""
    s = url.strip()
    if not s:
        return False
    return s.startswith("id") or s.isdigit()


def _extrair_review_android(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    texto = (item.get("text") or item.get("content") or "").strip()
    if not texto:
        return None
    autor_raw = (item.get("userName") or item.get("author") or "").strip()
    # CP-E2: id estável do review no Google Play (agents/googleplay-reviews)
    rid_raw = item.get("reviewId") or item.get("id") or ""
    return {
        "texto": texto,
        "autor": autor_raw or None,
        "data_original": _parse_data(item.get("date") or item.get("at")),
        "review_id_externo": str(rid_raw).strip() or None,
    }


def _extrair_review_ios(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    texto = (
        item.get("review") or item.get("text") or item.get("body") or item.get("content") or ""
    ).strip()
    if not texto:
        return None
    titulo = (item.get("title") or "").strip()
    if titulo:
        texto = f"{titulo}. {texto}"
    autor_raw = (item.get("userName") or item.get("author") or item.get("name") or "").strip()
    # CP-E2: id estável do review no App Store (agents/appstore-reviews)
    rid_raw = item.get("id") or item.get("reviewId") or ""
    return {
        "texto": texto,
        "autor": autor_raw or None,
        "data_original": _parse_data(item.get("date") or item.get("updated")),
        "review_id_externo": str(rid_raw).strip() or None,
    }


def coletar(fonte: Fonte) -> Dict[str, Any]:
    """Coleta reviews de app store (Android ou iOS) para uma Fonte via Apify."""
    fonte_id = fonte.id
    app_id = (fonte.url or "").strip()
    stats: Dict[str, Any] = {
        "coletados": 0,
        "novos": 0,
        "duplicados": 0,
        "erros": 0,
        "falhou_apify": False,
    }
    if not app_id:
        print(f"[appstore] fonte {fonte_id} sem url/app_id — abortando")
        stats["falhou_apify"] = True
        return stats

    data_inicio_iso = calcular_data_inicio_coleta(fonte_id)
    data_inicio = _parse_data(data_inicio_iso)

    # CP-C Grupo C: input schema dos atores agents/* — usam `appIds`
    # (array) + `country` + `maxItems` + `until` (data limite).
    until_iso = data_inicio_iso[:10] if data_inicio_iso else None

    if _eh_ios(app_id):
        numeric_id = app_id.lstrip("id")
        ator = IOS_ACTOR
        run_input = {
            "appIds": [numeric_id],
            "country": "BR",
            "maxItems": MAX_REVIEWS_DEFAULT,
        }
        if until_iso:
            run_input["until"] = until_iso
        extrator = _extrair_review_ios
        plataforma = "ios"
    else:
        ator = PLAY_ACTOR
        run_input = {
            "appIds": [app_id],
            "country": "BR",
            "language": "pt",
            "sort": "NEWEST",
            "maxItems": MAX_REVIEWS_DEFAULT,
        }
        if until_iso:
            run_input["until"] = until_iso
        extrator = _extrair_review_android
        plataforma = "android"

    print(
        f"[appstore] fonte {fonte_id} ({plataforma}: {app_id}) data_inicio={data_inicio_iso} "
        f"(filtro pós-coleta), max_reviews={MAX_REVIEWS_DEFAULT}"
    )

    try:
        items = run_and_collect(ator, run_input, timeout=APIFY_TIMEOUT_SECONDS)
    except ApifyError as exc:
        print(f"[appstore/{plataforma}] Apify falhou para fonte {fonte_id}: {exc}")
        stats["falhou_apify"] = True
        return stats

    for item in items:
        stats["coletados"] += 1
        review = extrator(item)
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
                f"[appstore/{plataforma}] erro ao processar review da fonte {fonte_id}: "
                f"{type(exc).__name__}: {exc}"
            )

    print(
        f"[appstore/{plataforma}] fonte {fonte_id} fim: coletados={stats['coletados']} "
        f"novos={stats['novos']} duplicados={stats['duplicados']} "
        f"erros={stats['erros']} falhou_apify={stats['falhou_apify']}"
    )
    return stats
