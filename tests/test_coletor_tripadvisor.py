"""Coletor TripAdvisor — formato do run_input enviado ao ator Apify.

Regressão do CP-fix-starturls: o ator ``agents/tripadvisor-reviews`` espera
``startUrls`` como array de STRINGS. Com o formato-objeto ``[{"url": ...}]`` ele
ignorava a entrada e rodava o exemplo prefixado (hotéis em NY) → 0 verbatins.
"""

from __future__ import annotations

from types import SimpleNamespace

import src.coletor.tripadvisor as ta


def test_starturls_e_lista_de_strings_com_a_url_da_fonte(monkeypatch):
    """run_input.startUrls deve ser [url] (string), não [{'url': url}]."""
    capturado = {}

    def _fake_run_and_collect(ator, run_input, timeout=None):
        capturado["ator"] = ator
        capturado["run_input"] = run_input
        return []  # sem itens → o loop de extração não roda

    # sem histórico → sem filtro `since`, mantém o input mínimo
    monkeypatch.setattr(ta, "calcular_data_inicio_coleta", lambda fonte_id: None)
    monkeypatch.setattr(ta, "run_and_collect", _fake_run_and_collect)

    url = (
        "https://www.tripadvisor.com/Hotel_Review-g303279-d668304-Reviews-"
        "Club_Med_Trancoso-Trancoso_Porto_Seguro_State_of_Bahia.html"
    )
    fonte = SimpleNamespace(id=315, url=url)
    ta.coletar(fonte)

    ri = capturado["run_input"]
    assert ri["startUrls"] == [url]  # STRING, não {"url": url}
    assert all(isinstance(x, str) for x in ri["startUrls"])
    assert ri["maxItems"] == ta.MAX_REVIEWS_DEFAULT
    assert ri["languages"] == ["pt"]


def test_url_passa_verbatim_sem_processamento(monkeypatch):
    """A fonte.url entra no startUrls exatamente como está (só strip)."""
    capturado = {}

    def _fake(ator, run_input, timeout=None):
        capturado["ri"] = run_input
        return []

    monkeypatch.setattr(ta, "calcular_data_inicio_coleta", lambda fonte_id: None)
    monkeypatch.setattr(ta, "run_and_collect", _fake)
    fonte = SimpleNamespace(id=1, url="  https://www.tripadvisor.com/X.html  ")
    ta.coletar(fonte)
    assert capturado["ri"]["startUrls"] == ["https://www.tripadvisor.com/X.html"]
