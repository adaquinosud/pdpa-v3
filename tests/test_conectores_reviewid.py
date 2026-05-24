"""Smoke tests Grupo C: confirma que TODOS os conectores passam
``review_id_externo`` para o pipeline quando o ator Apify entrega um id.

Os atores Apify são **mockados** — nenhum teste chama API real. O
``processar_verbatim_coletado`` é monkeypatched para capturar os kwargs
e validar que ``review_id_externo`` foi propagado.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest
from sqlalchemy.orm import Session

from src.models.empresa import Empresa
from src.models.fonte import Fonte


@pytest.fixture
def fonte_factory(db_session: Session):
    """Cria fonte com conector_tipo + url customizáveis."""
    contador = {"i": 0}

    def _fonte(conector_tipo: str, url: str) -> Fonte:
        contador["i"] += 1
        emp = Empresa(nome=f"E-{conector_tipo}-{contador['i']}", setor="varejo")
        db_session.add(emp)
        db_session.commit()
        f = Fonte(
            empresa_id=emp.id,
            entidade_tipo="empresa",
            entidade_id=emp.id,
            conector_tipo=conector_tipo,
            url=url,
        )
        db_session.add(f)
        db_session.commit()
        db_session.refresh(f)
        return f

    return _fonte


@pytest.fixture
def capturar_chamadas(monkeypatch):
    """Substitui processar_verbatim_coletado em todos os módulos por captura."""
    chamadas: List[Dict[str, Any]] = []

    def fake(**kwargs):
        chamadas.append(kwargs)

        class V:
            id = len(chamadas)

        return V()

    for modulo in [
        "src.coletor.facebook",
        "src.coletor.instagram",
        "src.coletor.youtube",
        "src.coletor.tiktok",
        "src.coletor.mercadolivre",
        "src.coletor.tripadvisor",
        "src.coletor.appstore",
        "src.coletor.linkedin",
        "src.coletor.google_news",
    ]:
        monkeypatch.setattr(f"{modulo}.processar_verbatim_coletado", fake)

    return chamadas


def test_facebook_passa_review_id_externo(fonte_factory, capturar_chamadas, monkeypatch):
    f = fonte_factory("facebook", "nubank")
    from src.coletor import facebook

    fake_dataset = [
        {
            "time": "2026-04-01T10:00:00Z",
            "comments": [
                {"id": "fb_comment_001", "text": "Adorei", "name": "João"},
                {"id": "fb_comment_002", "text": "Top", "name": "Maria"},
            ],
        }
    ]
    monkeypatch.setattr("src.coletor.facebook.run_and_collect", lambda *a, **k: fake_dataset)
    facebook.coletar(f)
    rids = [c["review_id_externo"] for c in capturar_chamadas]
    assert "fb_comment_001" in rids
    assert "fb_comment_002" in rids


def test_instagram_passa_review_id_externo_e_searchtype_user(
    fonte_factory, capturar_chamadas, monkeypatch
):
    f = fonte_factory("instagram", "bhairport")
    from src.coletor import instagram

    inputs_capturados: List[Dict[str, Any]] = []

    def fake_run(actor, run_input, **kw):
        inputs_capturados.append(run_input)
        return [
            {
                "timestamp": "2026-04-01T10:00:00Z",
                "latestComments": [
                    {"id": "ig_c_1", "text": "ótimo", "ownerUsername": "user1"},
                ],
            }
        ]

    monkeypatch.setattr("src.coletor.instagram.run_and_collect", fake_run)
    instagram.coletar(f)
    assert inputs_capturados[0].get("searchType") == "user"  # fix Grupo C
    assert capturar_chamadas[0]["review_id_externo"] == "ig_c_1"


def test_youtube_passa_review_id_externo(fonte_factory, capturar_chamadas, monkeypatch):
    f = fonte_factory("youtube", "BH Airport")
    from src.coletor import youtube

    fake_videos = [
        {
            "uploadDate": "2026-04-01T10:00:00Z",
            "comments": [
                {"commentId": "yt_c_1", "text": "bom video", "author": "user"},
            ],
        }
    ]
    monkeypatch.setattr("src.coletor.youtube.run_and_collect", lambda *a, **k: fake_videos)
    youtube.coletar(f)
    assert capturar_chamadas[0]["review_id_externo"] == "yt_c_1"


def test_tiktok_passa_review_id_externo(fonte_factory, capturar_chamadas, monkeypatch):
    f = fonte_factory("tiktok", "bhairport")
    from src.coletor import tiktok

    calls = {"n": 0}

    def fake_run(actor, run_input, **kw):
        calls["n"] += 1
        if "hashtag" in actor:
            return [{"webVideoUrl": "https://tt.com/v/1", "createTimeISO": "2026-04-01T10:00:00Z"}]
        return [
            {
                "cid": "tt_c_1",
                "text": "loved",
                "uniqueId": "user",
                "createTimeISO": "2026-04-01T11:00:00Z",
            }
        ]

    monkeypatch.setattr("src.coletor.tiktok.run_and_collect", fake_run)
    tiktok.coletar(f)
    assert calls["n"] == 2
    assert capturar_chamadas[0]["review_id_externo"] == "tt_c_1"


def test_mercadolivre_passa_review_id_externo(fonte_factory, capturar_chamadas, monkeypatch):
    f = fonte_factory("mercadolivre", "MAGALU")
    from src.coletor import mercadolivre

    def fake_run(actor, run_input, **kw):
        if "store" in actor or "viralanalyzer" in actor:
            return [{"id": "MLB-001"}]
        return [
            {
                "id": "ml_review_001",
                "content": "produto bom",
                "author": "user",
                "date": "2026-04-01T10:00:00Z",
            }
        ]

    monkeypatch.setattr("src.coletor.mercadolivre.run_and_collect", fake_run)
    mercadolivre.coletar(f)
    assert capturar_chamadas[0]["review_id_externo"] == "ml_review_001"


def test_tripadvisor_passa_review_id_externo_e_usa_ator_novo(
    fonte_factory, capturar_chamadas, monkeypatch
):
    f = fonte_factory("tripadvisor", "https://tripadvisor.com/x")
    from src.coletor import tripadvisor

    assert tripadvisor.ATOR_APIFY == "maxcopell/tripadvisor-reviews"
    fake_items = [
        {
            "id": "ta_rev_1",
            "text": "Hotel bom",
            "userName": "joão",
            "publishedDate": "2026-04-01T10:00:00Z",
        }
    ]
    monkeypatch.setattr("src.coletor.tripadvisor.run_and_collect", lambda *a, **k: fake_items)
    tripadvisor.coletar(f)
    assert capturar_chamadas[0]["review_id_externo"] == "ta_rev_1"


def test_appstore_usa_atores_novos_agents(fonte_factory, capturar_chamadas, monkeypatch):
    from src.coletor import appstore

    assert appstore.PLAY_ACTOR == "agents/googleplay-reviews"
    assert appstore.IOS_ACTOR == "agents/appstore-reviews"

    # Android
    f_android = fonte_factory("appstore", "com.bhairport.app")
    fake_items_android = [
        {
            "reviewId": "gp_r_1",
            "text": "App ótimo",
            "userName": "anon",
            "date": "2026-04-01T10:00:00Z",
        }
    ]
    monkeypatch.setattr("src.coletor.appstore.run_and_collect", lambda *a, **k: fake_items_android)
    appstore.coletar(f_android)
    assert capturar_chamadas[-1]["review_id_externo"] == "gp_r_1"

    # iOS
    f_ios = fonte_factory("appstore", "id123456")
    fake_items_ios = [
        {
            "id": "ios_r_1",
            "review": "App bom",
            "title": "Top",
            "userName": "anon",
            "date": "2026-04-01T10:00:00Z",
        }
    ]
    monkeypatch.setattr("src.coletor.appstore.run_and_collect", lambda *a, **k: fake_items_ios)
    appstore.coletar(f_ios)
    assert capturar_chamadas[-1]["review_id_externo"] == "ios_r_1"


def test_linkedin_usa_harvestapi_e_passa_review_id_externo(
    fonte_factory, capturar_chamadas, monkeypatch
):
    from src.coletor import linkedin

    assert linkedin.ATOR_APIFY == "harvestapi/linkedin-company-posts"
    f = fonte_factory("linkedin", "bh-airport")
    fake_posts = [
        {
            "postedDate": "2026-04-01T10:00:00Z",
            "comments": [
                {
                    "urn": "urn:li:comment:1",
                    "text": "Excelente!",
                    "author": {"name": "user X"},
                    "postedDate": "2026-04-01T11:00:00Z",
                }
            ],
        }
    ]
    inputs: List[Dict[str, Any]] = []

    def fake(actor, run_input, **kw):
        inputs.append(run_input)
        return fake_posts

    monkeypatch.setattr("src.coletor.linkedin.run_and_collect", fake)
    linkedin.coletar(f)
    assert inputs[0].get("scrapeComments") is True
    assert capturar_chamadas[0]["review_id_externo"] == "urn:li:comment:1"


def test_google_news_passa_url_como_review_id_externo(
    fonte_factory, capturar_chamadas, monkeypatch
):
    f = fonte_factory("google_news", "BH Airport")
    from src.coletor import google_news

    fake = [
        {
            "organicResults": [
                {
                    "title": "Notícia 1",
                    "snippet": "Sumário",
                    "link": "https://example.com/n1",
                    "source": "Example",
                }
            ]
        }
    ]
    monkeypatch.setattr("src.coletor.google_news.run_and_collect", lambda *a, **k: fake)
    google_news.coletar(f)
    assert capturar_chamadas[0]["review_id_externo"] == "https://example.com/n1"
