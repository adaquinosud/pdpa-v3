"""Coletor Google Maps Reviews — PDPA v3.

Reaproveitado de ``pdpa-v2/coletor/google.py``. Adaptações vs v2:

- Único caminho: Apify (ator ``compass/google-maps-reviews-scraper``).
  **Sem fallback Places API** (decisão do CP5: v3 exige ``APIFY_TOKEN``,
  cap de 5 reviews da Places API é inútil em volume).
- **Sem Text Search resolver**. v3 adota a convenção de que ``fonte.url``
  já contém um ``place_id`` válido (``ChIJ...`` ou ``places/...``). Quem
  cadastra é responsável — falha rápida no Apify se a URL não for válida.
- **Sem ThreadPoolExecutor.** ``coletar(fonte)`` recebe UMA fonte por
  chamada; paralelização sobe para o endpoint de disparo (futuro).
- **Sem CLI standalone.**
- ``rating`` (1-5 estrelas) **não é capturado** (decisão A do CP5).
  Pendência documentada em ``docs/PENDENCIAS_TECNICAS.md`` item 40
  (Painel Executivo — métrica de divergência).
- Coleta incremental com 3 níveis de precedência:

  1. env ``PDPA_COLETA_DESDE_OVERRIDE`` (teste/diagnóstico).
  2. ``MAX(verbatins.data_criacao_original) WHERE fonte_id=?`` − 7 dias
     (incremental por fonte, query do schema v3).
  3. env ``PDPA_COLETA_DESDE`` ou fallback ``hoje − 15 meses``.

- Para cada review do Apify, delega ao
  ``src.coletor.pipeline.processar_verbatim_coletado``: pipeline
  determinístico cuida de dedup + classificação + persistência íntegra.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from src.coletor.apify import ApifyError, run_and_collect
from src.coletor.incremental import calcular_data_inicio_coleta
from src.coletor.pipeline import processar_verbatim_coletado
from src.models.fonte import Fonte


# ── Constantes ───────────────────────────────────────────────────────────

ATOR_APIFY = "compass/google-maps-reviews-scraper"
MAX_REVIEWS_PER_PLACE = 2000  # cap por fonte/place (orçamento Apify)
LANGUAGE = "pt-BR"  # pendência: futuro vem de empresa.idioma_padrao
APIFY_TIMEOUT_SECONDS = 1800  # 30 min — coleta pode ser longa em places grandes


# ── Extração de campos do item Apify ─────────────────────────────────────


def _extrair_review(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extrai campos relevantes de um item retornado pelo Apify.

    O ator ``compass/google-maps-reviews-scraper`` pode retornar campos
    com nomes variáveis dependendo da versão; aplicamos fallbacks.

    Args:
        item: Item do dataset Apify.

    Returns:
        Dict com chaves ``texto``, ``autor``, ``data_original`` se válido.
        ``None`` se o item não tem texto utilizável (pula sem somar).
    """
    texto = (item.get("text") or item.get("textTranslated") or "").strip()
    if not texto:
        return None

    autor_raw = (item.get("name") or item.get("reviewerName") or "").strip()
    autor: Optional[str] = autor_raw or None

    published = item.get("publishedAtDate") or item.get("publishAt") or ""
    data_original: Optional[datetime] = None
    if published:
        try:
            # Trata ISO com Z (UTC) ou sem timezone
            data_original = datetime.fromisoformat(str(published).replace("Z", "+00:00"))
        except ValueError:
            try:
                data_original = datetime.fromisoformat(str(published)[:10])
            except ValueError:
                data_original = None

    return {"texto": texto, "autor": autor, "data_original": data_original}


# ── API pública ──────────────────────────────────────────────────────────


def coletar(fonte: Fonte) -> Dict[str, Any]:
    """Coleta reviews do Google Maps para uma Fonte via Apify.

    Cada review coletado é passado para
    ``processar_verbatim_coletado()`` — o pipeline cuida de dedup +
    classificação + persistência (texto íntegro).

    Args:
        fonte: Fonte com ``conector_tipo='google'`` (ou compatível). Espera
            que ``fonte.url`` contenha o place_id (``ChIJ...`` ou
            ``places/...``). Quem cadastrou é responsável por isso.

    Returns:
        Dict com 5 chaves:

        - ``coletados`` (int): total de itens recebidos do Apify.
        - ``novos`` (int): verbatins inseridos pela pipeline.
        - ``duplicados`` (int): verbatins rejeitados por dedup.
        - ``erros`` (int): erros em itens individuais durante uma coleta
          que **rodou com sucesso** (ex: pipeline lança exceção em 1 item
          de 500).
        - ``falhou_apify`` (bool): ``True`` se a coleta inteira não rodou
          (Apify lançou exceção, ou ``fonte.url`` vazio). Quando ``True``,
          as outras chaves ficam zeradas.
    """
    # Cache dos atributos da fonte ANTES de qualquer DB session (defensivo
    # caso a fonte venha detached do session do caller).
    fonte_id = fonte.id
    place_id = (fonte.url or "").strip()

    stats: Dict[str, Any] = {
        "coletados": 0,
        "novos": 0,
        "duplicados": 0,
        "erros": 0,
        "falhou_apify": False,
    }

    if not place_id:
        print(f"[google] fonte {fonte_id} sem url/place_id — abortando")
        stats["falhou_apify"] = True
        return stats

    reviews_start_date = calcular_data_inicio_coleta(fonte_id)
    run_input = {
        "placeIds": [place_id],
        "maxReviews": MAX_REVIEWS_PER_PLACE,
        "language": LANGUAGE,
        "reviewsSort": "newest",
        "personalData": False,
        "reviewsStartDate": reviews_start_date,
    }
    print(
        f"[google] fonte {fonte_id} ({place_id}) reviewsStartDate={reviews_start_date}, "
        f"cap={MAX_REVIEWS_PER_PLACE}"
    )

    try:
        items = run_and_collect(ATOR_APIFY, run_input, timeout=APIFY_TIMEOUT_SECONDS)
    except ApifyError as exc:
        print(f"[google] Apify falhou para fonte {fonte_id}: {exc}")
        stats["falhou_apify"] = True
        return stats

    for item in items:
        stats["coletados"] += 1
        review = _extrair_review(item)
        if review is None:
            continue
        try:
            verbatim = processar_verbatim_coletado(
                texto=review["texto"],
                fonte=fonte,
                data_original=review["data_original"],
                autor=review["autor"],
            )
            if verbatim is not None:
                stats["novos"] += 1
            else:
                stats["duplicados"] += 1
        except Exception as exc:
            stats["erros"] += 1
            print(
                f"[google] erro ao processar item da fonte {fonte_id}: "
                f"{type(exc).__name__}: {exc}"
            )

    print(
        f"[google] fonte {fonte_id} fim: coletados={stats['coletados']} "
        f"novos={stats['novos']} duplicados={stats['duplicados']} "
        f"erros={stats['erros']} falhou_apify={stats['falhou_apify']}"
    )
    return stats
