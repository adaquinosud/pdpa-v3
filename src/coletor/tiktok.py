"""Coletor TikTok (comentários por hashtag) — PDPA v3.

Reaproveitado de ``pdpa-v2/coletor/tiktok.py``. **2 atores Apify em
sequência**:

1. ``clockworks/tiktok-hashtag-scraper`` — descobre vídeos da hashtag.
2. ``clockworks/tiktok-comments-scraper`` — busca comentários dos vídeos.

fonte.url = hashtag (sem ``#``).

Adaptações: captions de vídeo skipadas (decisão padrão CP5); só comentários;
sem CLI; incremental via ``incremental.py`` (aplicado ao filtro de data dos
vídeos, não dos comentários); ``stats`` no padrão google.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from src.coletor.apify import ApifyError, run_and_collect
from src.coletor.incremental import calcular_data_inicio_coleta
from src.coletor.pipeline import processar_verbatim_coletado
from src.models.fonte import Fonte


HASHTAG_ACTOR = "clockworks/tiktok-hashtag-scraper"
COMMENTS_ACTOR = "clockworks/tiktok-comments-scraper"
MAX_VIDEOS_DEFAULT = 50
MAX_COMMENTS_PER_VIDEO = 30
TOP_N_VIDEOS_COMMENTS = 20  # número de vídeos top a coletar comentários (Apify cobra)
APIFY_TIMEOUT_SECONDS = 600


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


def coletar(fonte: Fonte) -> Dict[str, Any]:
    """Coleta comentários de vídeos TikTok de uma hashtag via Apify (2 atores)."""
    fonte_id = fonte.id
    hashtag = (fonte.url or "").strip().lstrip("#")
    stats: Dict[str, Any] = {
        "coletados": 0,
        "novos": 0,
        "duplicados": 0,
        "erros": 0,
        "falhou_apify": False,
    }
    if not hashtag:
        print(f"[tiktok] fonte {fonte_id} sem url/hashtag — abortando")
        stats["falhou_apify"] = True
        return stats

    data_inicio_iso = calcular_data_inicio_coleta(fonte_id)
    data_inicio = _parse_data(data_inicio_iso)

    # Passo 1: descobre vídeos da hashtag
    print(f"[tiktok] fonte {fonte_id} (#{hashtag}) passo 1/2: hashtag scraper")
    try:
        videos = run_and_collect(
            HASHTAG_ACTOR,
            {
                "hashtags": [hashtag],
                "resultsPerPage": MAX_VIDEOS_DEFAULT,
                "shouldDownloadVideos": False,
                "shouldDownloadCovers": False,
            },
            timeout=APIFY_TIMEOUT_SECONDS,
        )
    except ApifyError as exc:
        print(f"[tiktok] hashtag scraper falhou para fonte {fonte_id}: {exc}")
        stats["falhou_apify"] = True
        return stats

    # Filtra vídeos pela data_inicio (post-coleta) e extrai URLs
    video_urls: List[str] = []
    for video in videos:
        url = video.get("webVideoUrl") or video.get("url") or ""
        if not url:
            continue
        v_data = _parse_data(video.get("createTimeISO") or video.get("createTime"))
        if data_inicio is not None and v_data is not None and v_data.date() < data_inicio.date():
            continue
        video_urls.append(url)
    video_urls = video_urls[:TOP_N_VIDEOS_COMMENTS]
    if not video_urls:
        print(f"[tiktok] fonte {fonte_id} sem vídeos elegíveis após filtro de data")
        return stats

    # Passo 2: comentários
    print(f"[tiktok] fonte {fonte_id} passo 2/2: comments scraper ({len(video_urls)} vídeos)")
    try:
        comentarios = run_and_collect(
            COMMENTS_ACTOR,
            {
                "postURLs": video_urls,
                "commentsPerPost": MAX_COMMENTS_PER_VIDEO,
                "maxRepliesPerComment": 5,
            },
            timeout=APIFY_TIMEOUT_SECONDS,
        )
    except ApifyError as exc:
        print(f"[tiktok] comments scraper falhou para fonte {fonte_id}: {exc}")
        stats["falhou_apify"] = True
        return stats

    for comentario in comentarios:
        texto = (comentario.get("text") or "").strip()
        if not texto:
            continue
        stats["coletados"] += 1
        autor_raw = (comentario.get("uniqueId") or comentario.get("nickname") or "").strip()
        autor: Optional[str] = autor_raw or None
        c_data = _parse_data(comentario.get("createTimeISO") or comentario.get("createTime"))
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
                f"[tiktok] erro ao processar comentário da fonte {fonte_id}: "
                f"{type(exc).__name__}: {exc}"
            )

    print(
        f"[tiktok] fonte {fonte_id} fim: coletados={stats['coletados']} "
        f"novos={stats['novos']} duplicados={stats['duplicados']} "
        f"erros={stats['erros']} falhou_apify={stats['falhou_apify']}"
    )
    return stats
