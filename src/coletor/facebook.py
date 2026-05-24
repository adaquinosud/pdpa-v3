"""Coletor Facebook — PDPA v3.

Reaproveitado de ``pdpa-v2/coletor/facebook.py``. Adaptações vs v2:

- Único caminho: Apify (ator ``apify/facebook-posts-scraper``).
- **Só coleta comentários** dos posts (mesma decisão da Onda 1.2 / Instagram:
  captions de post = voz institucional, descartadas).
- Coleta incremental via
  ``src.coletor.incremental.calcular_data_inicio_coleta``. O ator do FB
  **não** aceita parâmetro de data no input — filtragem é feita em
  Python pós-coleta (igual o v2 fazia).
- Sem filtros locais de tamanho — pipeline já filtra <3 chars +
  Cirurgia 4 (``sem_lastro``) trata textos sem ancoragem.
- ``fonte.url`` tolera handle (``nubank``) ou URL completa
  (``https://facebook.com/nubank``) — prefixa com ``https://www.facebook.com/``
  se não começar com ``http``.
- Sem ThreadPoolExecutor, sem CLI standalone.
- ``stats`` no padrão google.py:
  ``{coletados, novos, duplicados, erros, falhou_apify}``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterator, Optional

from src.coletor.apify import ApifyError, run_and_collect
from src.coletor.incremental import calcular_data_inicio_coleta
from src.coletor.pipeline import processar_verbatim_coletado
from src.models.fonte import Fonte


ATOR_APIFY = "apify/facebook-posts-scraper"
MAX_POSTS_DEFAULT = 50
APIFY_TIMEOUT_SECONDS = 900


def _parse_data(value: Any) -> Optional[datetime]:
    """Tenta parsear data do Facebook (ISO string ou Unix int/str)."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value))
        except (ValueError, OSError, OverflowError):
            return None
    s = str(value).strip()
    if s.isdigit() and len(s) >= 10:
        try:
            return datetime.fromtimestamp(int(s[:10]))
        except (ValueError, OSError, OverflowError):
            return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(s[:10])
    except ValueError:
        return None


def _normalizar_url(url: str) -> str:
    """Aceita handle puro ou URL completa; devolve URL `https://...` para o ator.

    Args:
        url: Pode vir como ``nubank``, ``/nubank`` ou ``https://facebook.com/nubank``.

    Returns:
        URL completa ``https://www.facebook.com/<handle>``.
    """
    s = (url or "").strip()
    if not s:
        return ""
    if s.startswith("http"):
        return s
    return f"https://www.facebook.com/{s.lstrip('/')}"


def _extrair_comentarios(
    post: Dict[str, Any], data_inicio: Optional[datetime]
) -> Iterator[Dict[str, Any]]:
    """Itera os comentários de um post, extraindo (texto, autor, data_original).

    Skipa comentários sem texto. Filtra por ``data_inicio`` (se fornecida) —
    o ator do FB não filtra no input.

    Args:
        post: Item de post do Apify.
        data_inicio: Datas anteriores a esta são puladas. Se ``None``, pega tudo.

    Yields:
        Dict ``{texto, autor, data_original}`` por comentário válido.
    """
    post_data = _parse_data(
        post.get("time") or post.get("publishedTime") or post.get("timestamp") or post.get("date")
    )

    comentarios = post.get("latestComments") or post.get("comments") or []
    if not isinstance(comentarios, list):
        comentarios = []

    for comentario in comentarios:
        texto = (comentario.get("text") or comentario.get("message") or "").strip()
        if not texto:
            continue
        autor_raw = (
            comentario.get("name")
            or comentario.get("profileName")
            or comentario.get("authorName")
            or ""
        ).strip()
        autor: Optional[str] = autor_raw or None

        c_data = _parse_data(comentario.get("date") or comentario.get("timestamp")) or post_data
        if data_inicio is not None and c_data is not None and c_data.date() < data_inicio.date():
            continue

        # CP-E2: id estável do comentário no Facebook (Apify retorna id/commentId)
        cid_raw = comentario.get("id") or comentario.get("commentId") or ""
        review_id_externo = str(cid_raw).strip() or None

        yield {
            "texto": texto,
            "autor": autor,
            "data_original": c_data,
            "review_id_externo": review_id_externo,
        }


def coletar(fonte: Fonte) -> Dict[str, Any]:
    """Coleta comentários de posts Facebook para uma Fonte via Apify.

    Args:
        fonte: Fonte com ``conector_tipo='facebook'``. ``fonte.url`` pode ser
            handle (``nubank``) ou URL completa.

    Returns:
        Dict ``{coletados, novos, duplicados, erros, falhou_apify}``.
    """
    fonte_id = fonte.id
    url_normalizada = _normalizar_url(fonte.url)

    stats: Dict[str, Any] = {
        "coletados": 0,
        "novos": 0,
        "duplicados": 0,
        "erros": 0,
        "falhou_apify": False,
    }

    if not url_normalizada:
        print(f"[facebook] fonte {fonte_id} sem url — abortando")
        stats["falhou_apify"] = True
        return stats

    data_inicio_iso = calcular_data_inicio_coleta(fonte_id)
    data_inicio = _parse_data(data_inicio_iso)

    run_input = {
        "startUrls": [{"url": url_normalizada}],
        "resultsLimit": MAX_POSTS_DEFAULT,
    }
    print(
        f"[facebook] fonte {fonte_id} ({url_normalizada}) "
        f"data_inicio={data_inicio_iso} (filtro pós-coleta), max_posts={MAX_POSTS_DEFAULT}"
    )

    try:
        posts = run_and_collect(ATOR_APIFY, run_input, timeout=APIFY_TIMEOUT_SECONDS)
    except ApifyError as exc:
        print(f"[facebook] Apify falhou para fonte {fonte_id}: {exc}")
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
                    f"[facebook] erro ao processar comentário da fonte {fonte_id}: "
                    f"{type(exc).__name__}: {exc}"
                )

    print(
        f"[facebook] fonte {fonte_id} fim: coletados={stats['coletados']} "
        f"novos={stats['novos']} duplicados={stats['duplicados']} "
        f"erros={stats['erros']} falhou_apify={stats['falhou_apify']}"
    )
    return stats
