"""Coletor LinkedIn (comentários de posts de empresa) — PDPA v3.

**Histórico** (CP-C / Grupo C — 2026-05-24):

O ator original ``curious_coder/linkedin-company-scraper`` é pago
(FLAT_PRICE_PER_MONTH USD 10). Trocado por ``harvestapi/linkedin-company-posts``,
modelo PAY_PER_EVENT (~$0.002/post + $0.002/comment) — paga só pelo que
coleta. Mantém o mesmo objetivo: comentários de posts de empresa (posts
em si = voz institucional, descartados).

fonte.url = slug (ex: ``bh-airport``) ou URL completa da empresa.

Adaptações: 1 chamada Apify (``scrapeComments=True`` já inline); sem
cloudscraper fallback; sem CLI; incremental via ``incremental.py``;
``stats`` no padrão google.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterator, Optional

from src.coletor.apify import ApifyError, run_and_collect
from src.coletor.incremental import calcular_data_inicio_coleta
from src.coletor.pipeline import processar_verbatim_coletado
from src.models.fonte import Fonte


ATOR_APIFY = "harvestapi/linkedin-company-posts"
MAX_POSTS_DEFAULT = 50
MAX_COMMENTS_PER_POST = 30
APIFY_TIMEOUT_SECONDS = 900


def _parse_data(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value))
        except (ValueError, OSError, OverflowError):
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


def _normalizar_url(slug_or_url: str) -> str:
    s = (slug_or_url or "").strip()
    if not s:
        return ""
    if s.startswith("http"):
        return s
    return f"https://www.linkedin.com/company/{s.lstrip('/')}"


def _extrair_autor(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        nome = value.get("name") or value.get("authorName") or value.get("fullName") or ""
    else:
        nome = value or ""
    nome = str(nome).strip()
    return nome or None


def _extrair_comentarios(
    post: Dict[str, Any], data_inicio: Optional[datetime]
) -> Iterator[Dict[str, Any]]:
    """Itera comentários aninhados de um post (postNestedComments=True)."""
    post_data = _parse_data(
        post.get("postedDate") or post.get("publishedAt") or post.get("postedAtTimestamp")
    )

    comentarios = post.get("comments") or []
    if not isinstance(comentarios, list):
        comentarios = []
    for comentario in comentarios:
        texto = (
            comentario.get("text")
            or comentario.get("commentary")
            or comentario.get("content")
            or ""
        ).strip()
        if not texto:
            continue
        autor = _extrair_autor(
            comentario.get("author") or comentario.get("authorName") or comentario.get("commenter")
        )
        c_data = (
            _parse_data(
                comentario.get("postedDate")
                or comentario.get("date")
                or comentario.get("timestamp")
            )
            or post_data
        )
        if data_inicio is not None and c_data is not None and c_data.date() < data_inicio.date():
            continue
        # CP-E2: id estável do comentário (urn ou id no harvestapi)
        cid_raw = comentario.get("urn") or comentario.get("id") or comentario.get("commentId") or ""
        review_id_externo = str(cid_raw).strip() or None
        yield {
            "texto": texto,
            "autor": autor,
            "data_original": c_data,
            "review_id_externo": review_id_externo,
        }


def coletar(fonte: Fonte) -> Dict[str, Any]:
    """Coleta comentários de posts de empresa no LinkedIn via Apify.

    Args:
        fonte: Fonte com ``conector_tipo='linkedin'``. ``fonte.url`` pode
            ser slug (``bh-airport``) ou URL completa.

    Returns:
        Dict ``{coletados, novos, duplicados, erros, falhou_apify}``.
    """
    fonte_id = fonte.id
    url = _normalizar_url(fonte.url)
    stats: Dict[str, Any] = {
        "coletados": 0,
        "novos": 0,
        "duplicados": 0,
        "erros": 0,
        "falhou_apify": False,
    }
    if not url:
        print(f"[linkedin] fonte {fonte_id} sem url — abortando")
        stats["falhou_apify"] = True
        return stats

    data_inicio_iso = calcular_data_inicio_coleta(fonte_id)
    data_inicio = _parse_data(data_inicio_iso)

    run_input: Dict[str, Any] = {
        "targetUrls": [url],
        "maxPosts": MAX_POSTS_DEFAULT,
        "scrapeComments": True,
        "maxComments": MAX_COMMENTS_PER_POST,
        "postNestedComments": True,
    }
    if data_inicio_iso:
        # harvestapi aceita ISO 8601 — usa data como limite inferior
        run_input["postedLimitDate"] = data_inicio_iso[:10]
    print(
        f"[linkedin] fonte {fonte_id} ({url}) data_inicio={data_inicio_iso}, "
        f"max_posts={MAX_POSTS_DEFAULT}, max_comments_per_post={MAX_COMMENTS_PER_POST}"
    )

    try:
        posts = run_and_collect(ATOR_APIFY, run_input, timeout=APIFY_TIMEOUT_SECONDS)
    except ApifyError as exc:
        print(f"[linkedin] Apify falhou para fonte {fonte_id}: {exc}")
        stats["falhou_apify"] = True
        return stats

    for post in posts:
        for comentario in _extrair_comentarios(post, data_inicio):
            stats["coletados"] += 1
            try:
                verbatim = processar_verbatim_coletado(
                    texto=comentario["texto"],
                    fonte=fonte,
                    data_original=comentario["data_original"],
                    autor=comentario["autor"],
                    review_id_externo=comentario["review_id_externo"],
                )
                if verbatim is not None:
                    stats["novos"] += 1
                else:
                    stats["duplicados"] += 1
            except Exception as exc:
                stats["erros"] += 1
                print(
                    f"[linkedin] erro ao processar comentário da fonte {fonte_id}: "
                    f"{type(exc).__name__}: {exc}"
                )

    print(
        f"[linkedin] fonte {fonte_id} fim: coletados={stats['coletados']} "
        f"novos={stats['novos']} duplicados={stats['duplicados']} "
        f"erros={stats['erros']} falhou_apify={stats['falhou_apify']}"
    )
    return stats
