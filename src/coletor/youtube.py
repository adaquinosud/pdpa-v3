"""Coletor YouTube (vídeos por busca + comentários) — PDPA v3.

**2 atores Apify em sequência** (CP-C 2026-05-24):

1. ``streamers/youtube-scraper`` — descobre vídeos da busca.
2. ``streamers/youtube-comments-scraper`` — extrai comentários de
   cada vídeo descoberto.

Antes só o ator 1 era chamado e ``video.get("comments")`` ficava vazio
(o ator não retorna comments por default). Validação empírica da
fonte 84 confirmou: 3 vídeos retornados, 0 comments cada.

fonte.url = query de busca (ex: ``BH Airport``).

Adaptações: título e descrição do vídeo (voz do creator) skipados — só
comentários; sem CLI; incremental via ``incremental.py``; ``stats`` no
padrão google.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from src.coletor.apify import ApifyError, run_and_collect
from src.coletor.incremental import calcular_data_inicio_coleta
from src.coletor.pipeline import processar_verbatim_coletado
from src.models.fonte import Fonte


SEARCH_ACTOR = "streamers/youtube-scraper"
COMMENTS_ACTOR = "streamers/youtube-comments-scraper"
MAX_VIDEOS_DEFAULT = 20
MAX_COMMENTS_PER_VIDEO = 30
TOP_N_VIDEOS_COMMENTS = 20  # número de vídeos a coletar comments (Apify cobra)
APIFY_TIMEOUT_SECONDS = 900


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
    """Coleta comentários de vídeos YouTube via Apify (2 atores)."""
    fonte_id = fonte.id
    query = (fonte.url or "").strip()
    stats: Dict[str, Any] = {
        "coletados": 0,
        "novos": 0,
        "duplicados": 0,
        "erros": 0,
        "falhou_apify": False,
    }
    if not query:
        print(f"[youtube] fonte {fonte_id} sem url/query — abortando")
        stats["falhou_apify"] = True
        return stats

    data_inicio_iso = calcular_data_inicio_coleta(fonte_id)
    data_inicio = _parse_data(data_inicio_iso)

    # Passo 1: descobre vídeos da busca
    search_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    print(
        f"[youtube] fonte {fonte_id} query={query!r} passo 1/2: search "
        f"data_inicio={data_inicio_iso}, max_videos={MAX_VIDEOS_DEFAULT}"
    )
    try:
        videos = run_and_collect(
            SEARCH_ACTOR,
            {
                "startUrls": [{"url": search_url}],
                "maxResults": MAX_VIDEOS_DEFAULT,
                "maxResultsShorts": 0,
            },
            timeout=APIFY_TIMEOUT_SECONDS,
        )
    except ApifyError as exc:
        print(f"[youtube] search scraper falhou para fonte {fonte_id}: {exc}")
        stats["falhou_apify"] = True
        return stats

    # Filtra vídeos pela data e extrai URLs
    video_meta: List[Dict[str, Any]] = []
    for video in videos:
        url = video.get("url") or ""
        if not url:
            continue
        v_data = _parse_data(
            video.get("date")
            or video.get("uploadDate")
            or video.get("publishedAt")
            or video.get("uploadedAt")
        )
        if data_inicio is not None and v_data is not None and v_data.date() < data_inicio.date():
            continue
        video_meta.append({"url": url, "data": v_data})
    video_meta = video_meta[:TOP_N_VIDEOS_COMMENTS]
    if not video_meta:
        print(f"[youtube] fonte {fonte_id} sem vídeos elegíveis após filtro de data")
        return stats

    # Passo 2: comentários dos vídeos
    print(f"[youtube] fonte {fonte_id} passo 2/2: comments scraper ({len(video_meta)} vídeos)")
    try:
        comentarios = run_and_collect(
            COMMENTS_ACTOR,
            {
                "startUrls": [{"url": v["url"]} for v in video_meta],
                "maxComments": MAX_COMMENTS_PER_VIDEO,
                "sortCommentsBy": "NEWEST_FIRST",
            },
            timeout=APIFY_TIMEOUT_SECONDS,
        )
    except ApifyError as exc:
        print(f"[youtube] comments scraper falhou para fonte {fonte_id}: {exc}")
        stats["falhou_apify"] = True
        return stats

    for comentario in comentarios:
        texto = (comentario.get("text") or comentario.get("content") or "").strip()
        if not texto:
            continue
        stats["coletados"] += 1
        autor_raw = (
            comentario.get("author") or comentario.get("authorName") or comentario.get("user") or ""
        ).strip()
        autor: Optional[str] = autor_raw or None
        c_data = _parse_data(
            comentario.get("publishedAt")
            or comentario.get("date")
            or comentario.get("publishedTimeText")
        )
        if data_inicio is not None and c_data is not None and c_data.date() < data_inicio.date():
            continue
        # CP-E2: id estável do comentário no YouTube
        cid_raw = comentario.get("commentId") or comentario.get("id") or ""
        review_id_externo = str(cid_raw).strip() or None
        try:
            verbatim = processar_verbatim_coletado(
                texto=texto,
                fonte=fonte,
                data_original=c_data,
                autor=autor,
                review_id_externo=review_id_externo,
            )
            if verbatim is not None:
                stats["novos"] += 1
            else:
                stats["duplicados"] += 1
        except Exception as exc:
            stats["erros"] += 1
            print(
                f"[youtube] erro ao processar comentário da fonte {fonte_id}: "
                f"{type(exc).__name__}: {exc}"
            )

    print(
        f"[youtube] fonte {fonte_id} fim: coletados={stats['coletados']} "
        f"novos={stats['novos']} duplicados={stats['duplicados']} "
        f"erros={stats['erros']} falhou_apify={stats['falhou_apify']}"
    )
    return stats
