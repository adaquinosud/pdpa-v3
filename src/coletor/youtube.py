"""Coletor YouTube (comentários por busca) — PDPA v3.

Reaproveitado de ``pdpa-v2/coletor/youtube.py``. Ator: ``streamers/youtube-scraper``.
fonte.url = query de busca (ex: ``Nespresso Brasil``).

Adaptações: título e descrição do vídeo (voz do creator) skipados — só
comentários do público; sem CLI; incremental via ``incremental.py``;
``stats`` no padrão google.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import quote_plus

from src.coletor.apify import ApifyError, run_and_collect
from src.coletor.incremental import calcular_data_inicio_coleta
from src.coletor.pipeline import processar_verbatim_coletado
from src.models.fonte import Fonte


ATOR_APIFY = "streamers/youtube-scraper"
MAX_VIDEOS_DEFAULT = 20
MAX_COMMENTS_PER_VIDEO = 30
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
    """Coleta comentários de vídeos YouTube de uma busca via Apify."""
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

    search_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    run_input = {
        "startUrls": [{"url": search_url}],
        "maxResults": MAX_VIDEOS_DEFAULT,
        "maxResultsShorts": 0,
    }
    print(
        f"[youtube] fonte {fonte_id} query={query!r} data_inicio={data_inicio_iso} "
        f"(filtro pós-coleta), max_videos={MAX_VIDEOS_DEFAULT}"
    )

    try:
        videos = run_and_collect(ATOR_APIFY, run_input, timeout=APIFY_TIMEOUT_SECONDS)
    except ApifyError as exc:
        print(f"[youtube] Apify falhou para fonte {fonte_id}: {exc}")
        stats["falhou_apify"] = True
        return stats

    for video in videos:
        v_data = _parse_data(
            video.get("date")
            or video.get("uploadDate")
            or video.get("publishedAt")
            or video.get("uploadedAt")
        )
        # Pula vídeo inteiro se a data dele já é anterior — comentários nesse
        # vídeo provavelmente também são velhos demais.
        if data_inicio is not None and v_data is not None and v_data.date() < data_inicio.date():
            continue

        for comentario in (video.get("comments") or [])[:MAX_COMMENTS_PER_VIDEO]:
            texto = (comentario.get("text") or comentario.get("content") or "").strip()
            if not texto:
                continue
            stats["coletados"] += 1
            autor_raw = (comentario.get("author") or comentario.get("authorName") or "").strip()
            autor: Optional[str] = autor_raw or None
            c_data = _parse_data(comentario.get("publishedAt") or comentario.get("date")) or v_data
            if (
                data_inicio is not None
                and c_data is not None
                and c_data.date() < data_inicio.date()
            ):
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
                    f"[youtube] erro ao processar comentário da fonte {fonte_id}: "
                    f"{type(exc).__name__}: {exc}"
                )

    print(
        f"[youtube] fonte {fonte_id} fim: coletados={stats['coletados']} "
        f"novos={stats['novos']} duplicados={stats['duplicados']} "
        f"erros={stats['erros']} falhou_apify={stats['falhou_apify']}"
    )
    return stats
