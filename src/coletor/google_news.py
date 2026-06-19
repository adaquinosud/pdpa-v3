"""Coletor Google News (menções na imprensa) — PDPA v3.

Reaproveitado de ``pdpa-v2/coletor/google_news.py``. Ator:
``apify/google-search-scraper`` com ``tbm=nws``. fonte.url = query de busca.

**SURPRESA importante (não migra a decisão do v3 de 'só voz do cliente'):**
o conteúdo coletado é **imprensa**, não cliente. v2 marcava ``fonte='imprensa'``
e (com o campo ``origem='institucional'``) atribuía peso 0 no ratio P/D.
v3 eliminou o campo ``origem``, então esses verbatins entram no ratio normal.

**Decisão CP5 Onda 2:** mantém a coleta (é menção a marca, valor analítico
real), mas registra em ``docs/PENDENCIAS_TECNICAS.md`` que ratio P/D pode
ser distorcido por essa fonte. Reavaliar quando o Painel Executivo (Bloco
5+) precisar de pesos por fonte.

Adaptações: sem CLI; incremental via ``incremental.py`` (mapeia para
parâmetro Google ``tbs cdr``); ``stats`` no padrão google.py.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from src.coletor.apify import ApifyError, run_and_collect
from src.coletor.incremental import calcular_data_inicio_coleta
from src.coletor.pipeline import processar_verbatim_coletado
from src.models.fonte import Fonte


ATOR_APIFY = "apify/google-search-scraper"
MAX_RESULTS_DEFAULT = 100
APIFY_TIMEOUT_SECONDS = 600


def _parse_data(value: Any) -> Optional[datetime]:
    """Parser tolerante: ISO, ou textos relativos do Google ('há 2 dias')."""
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
        pass
    # Tenta padrões relativos do Google em PT-BR
    s_lower = s.lower()
    today = date.today()
    if "hora" in s_lower or "minuto" in s_lower or "agora" in s_lower:
        return datetime.combine(today, datetime.min.time())
    if "ontem" in s_lower:
        return datetime.combine(today - timedelta(days=1), datetime.min.time())
    # Não reconhecido — devolve None (pipeline usa now() como fallback)
    return None


def _formatar_data_google(data: datetime) -> str:
    """Google's ``tbs cdr`` espera ``mm/dd/yyyy``."""
    return data.strftime("%m/%d/%Y")


def coletar(fonte: Fonte) -> Dict[str, Any]:
    """Coleta notícias mencionando uma query via Apify Google Search Scraper."""
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
        print(f"[google_news] fonte {fonte_id} sem url/query — abortando")
        stats["falhou_apify"] = True
        return stats

    data_inicio_iso = calcular_data_inicio_coleta(fonte_id)
    tbs = None
    data_inicio_dt = None
    if data_inicio_iso:  # guard defensivo: calcular_data_inicio_coleta sempre devolve data
        try:
            data_inicio_dt = datetime.fromisoformat(data_inicio_iso[:10])
            tbs = f"cdr:1,cd_min:{_formatar_data_google(data_inicio_dt)}"
        except ValueError:
            tbs = None
            data_inicio_dt = None

    run_input: Dict[str, Any] = {
        "queries": query,
        "tbm": "nws",
        "resultsPerPage": 100,
        "maxPagesPerQuery": max(1, MAX_RESULTS_DEFAULT // 100),
        "languageCode": "pt-BR",
        "countryCode": "br",
        "saveHtml": False,
    }
    if tbs:
        run_input["tbs"] = tbs
    print(
        f"[google_news] fonte {fonte_id} query={query!r} data_inicio={data_inicio_iso} "
        f"(via tbs), max_results={MAX_RESULTS_DEFAULT}"
    )

    try:
        items = run_and_collect(ATOR_APIFY, run_input, timeout=APIFY_TIMEOUT_SECONDS)
    except ApifyError as exc:
        print(f"[google_news] Apify falhou para fonte {fonte_id}: {exc}")
        stats["falhou_apify"] = True
        return stats

    for item in items:
        news_list: List[Dict[str, Any]] = (
            item.get("newsResults") or item.get("organicResults") or []
        )
        for noticia in news_list:
            titulo = (noticia.get("title") or "").strip()
            snippet = (noticia.get("snippet") or noticia.get("description") or "").strip()
            texto = (f"{titulo} — {snippet}").strip(" —")
            if not texto:
                continue
            stats["coletados"] += 1
            autor_raw = (noticia.get("source") or noticia.get("displayedUrl") or "").strip()
            autor: Optional[str] = autor_raw or None
            data_original = _parse_data(noticia.get("date"))
            # CP-E2: URL da notícia é o id natural — único e estável por notícia.
            # Dá rastreabilidade e habilita cleanup retroativo quando re-coletado.
            link_raw = (noticia.get("link") or noticia.get("url") or "").strip()
            review_id_externo: Optional[str] = link_raw or None
            try:
                verbatim = processar_verbatim_coletado(
                    texto=texto,
                    fonte=fonte,
                    data_original=data_original,
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
                    f"[google_news] erro ao processar notícia da fonte {fonte_id}: "
                    f"{type(exc).__name__}: {exc}"
                )

    print(
        f"[google_news] fonte {fonte_id} fim: coletados={stats['coletados']} "
        f"novos={stats['novos']} duplicados={stats['duplicados']} "
        f"erros={stats['erros']} falhou_apify={stats['falhou_apify']}"
    )
    return stats
