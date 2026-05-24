"""Testes do CP-D3 — ratings-only + dedup por review_id_externo."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.coletor.google import _extrair_review
from src.coletor.pipeline import (
    RATING_PARA_CLASSIFICACAO,
    processar_verbatim_coletado,
)
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim


# ── _extrair_review ─────────────────────────────────────────────────────


def test_extrair_review_com_texto_e_rating():
    item = {
        "text": "Atendimento ótimo",
        "stars": 5,
        "name": "João",
        "publishedAtDate": "2025-08-10T10:00:00Z",
        "reviewId": "rev_abc123",
    }
    out = _extrair_review(item)
    assert out["texto"] == "Atendimento ótimo"
    assert out["rating"] == 5
    assert out["autor"] == "João"
    assert out["review_id_externo"] == "rev_abc123"
    assert isinstance(out["data_original"], datetime)


def test_extrair_review_ratings_only_aceito():
    """Sem texto, só com rating → aceito (texto='')."""
    item = {"stars": 4, "reviewId": "rev_only_rating_1"}
    out = _extrair_review(item)
    assert out is not None
    assert out["texto"] == ""
    assert out["rating"] == 4
    assert out["review_id_externo"] == "rev_only_rating_1"


def test_extrair_review_sem_texto_sem_rating_descartado():
    """Item sem texto E sem rating → None (lixo do scraper)."""
    item = {"name": "Anônimo"}
    assert _extrair_review(item) is None


def test_extrair_review_rating_float_normalizado():
    """Apify às vezes devolve rating como float (4.5 → ignora, fora de range)."""
    item = {"text": "ok", "stars": 4.0}
    assert _extrair_review(item)["rating"] == 4


def test_extrair_review_rating_invalido_ignorado():
    item = {"text": "ok", "stars": "lixo"}
    assert _extrair_review(item)["rating"] is None


def test_extrair_review_rating_fora_de_range():
    """Rating 0 ou 6 é tratado como None."""
    item_zero = {"text": "ok", "stars": 0}
    item_seis = {"text": "ok", "stars": 6}
    assert _extrair_review(item_zero)["rating"] is None
    assert _extrair_review(item_seis)["rating"] is None


def test_extrair_review_usa_textTranslated_como_fallback():
    item = {"text": "", "textTranslated": "Traduzido"}
    assert _extrair_review(item)["texto"] == "Traduzido"


def test_extrair_review_usa_reviewerId_como_fallback_de_id():
    item = {"text": "ok", "reviewerId": "user_xyz"}
    assert _extrair_review(item)["review_id_externo"] == "user_xyz"


# ── pipeline: ratings-only ──────────────────────────────────────────────


def _fonte_de_teste(client_loyall):
    import uuid

    sfx = uuid.uuid4().hex[:6]
    e = client_loyall.post("/api/empresas/", json={"nome": f"Erat-{sfx}"}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ-rat-{sfx}"},
    ).get_json()
    return e["id"], loc["id"], f["id"]


def _carregar_fonte(db_session, fonte_id):
    f = db_session.get(Fonte, fonte_id)
    db_session.expunge(f)
    return f


@pytest.fixture
def fonte_t(client_loyall, db_session):
    _e, _loc, fonte_id = _fonte_de_teste(client_loyall)
    return _carregar_fonte(db_session, fonte_id)


def test_ratings_only_persiste_sem_chamar_classifier(fonte_t, db_session, monkeypatch):
    """Review sem texto + rating=5 → persiste sem chamar Anthropic."""
    # Mock para garantir que classifier NÃO é chamado em ratings-only.
    chamadas = []

    def fake_classify(**kwargs):  # pragma: no cover
        chamadas.append(kwargs)
        raise AssertionError("classifier não deveria ser chamado em ratings-only")

    monkeypatch.setattr("src.coletor.pipeline.classificar", fake_classify)

    v = processar_verbatim_coletado(
        texto="",
        fonte=fonte_t,
        rating=5,
        review_id_externo="rev_ro_5",
    )
    assert v is not None
    assert v.tem_texto is False
    assert v.rating == 5
    assert v.subpilar == "Pa1"
    assert v.tipo == "promotor"
    assert v.confianca == 0.4
    assert v.justificativa == "Avaliação 5 estrelas sem texto"
    assert v.prompt_versao == "rating-heuristica-v1"
    assert chamadas == []  # classifier nunca foi chamado


@pytest.mark.parametrize(
    "rating,sp,tp",
    [
        (5, "Pa1", "promotor"),
        (4, "Pa1", "conversivel"),
        (3, "sem_lastro", "inativo"),
        (2, "Pa1", "detrator"),
        (1, "Pa1", "detrator"),
    ],
)
def test_ratings_only_classificacao_por_rating(rating, sp, tp, fonte_t, db_session, monkeypatch):
    monkeypatch.setattr(
        "src.coletor.pipeline.classificar",
        lambda **k: (_ for _ in ()).throw(AssertionError("nao chamar")),
    )
    v = processar_verbatim_coletado(
        texto="",
        fonte=fonte_t,
        rating=rating,
        review_id_externo=f"rev_only_{rating}",
    )
    assert v.subpilar == sp
    assert v.tipo == tp


def test_sem_texto_sem_rating_descartado(fonte_t):
    assert processar_verbatim_coletado(texto="", fonte=fonte_t, rating=None) is None


def test_sem_texto_rating_invalido_descartado(fonte_t):
    """Rating fora do dicionário (ex: 0) → não persiste."""
    v = processar_verbatim_coletado(texto="", fonte=fonte_t, rating=99)
    # Aceita porque rating não é None, mas sem subpilar (não está no dict)
    assert v is not None
    assert v.subpilar is None
    assert v.tipo is None


# ── pipeline: dedup por review_id_externo ───────────────────────────────


def test_dedup_por_review_id_externo(fonte_t, db_session, monkeypatch):
    monkeypatch.setattr(
        "src.coletor.pipeline.classificar",
        lambda **k: type(
            "R",
            (),
            {
                "subpilar": "Pa1",
                "tipo": "promotor",
                "confianca": 0.9,
                "justificativa": "ok",
                "prompt_versao": "v3.0",
            },
        )(),
    )
    v1 = processar_verbatim_coletado(
        texto="Texto 1",
        fonte=fonte_t,
        autor="A",
        review_id_externo="rev_dup_1",
    )
    assert v1 is not None
    # 2ª chamada com mesmo review_id_externo (texto diferente) → dedup
    v2 = processar_verbatim_coletado(
        texto="Texto totalmente diferente",
        fonte=fonte_t,
        autor="B",
        review_id_externo="rev_dup_1",
    )
    assert v2 is None
    db_session.expire_all()
    assert db_session.query(Verbatim).filter_by(review_id_externo="rev_dup_1").count() == 1


def test_dedup_legacy_hash_quando_sem_review_id(fonte_t, db_session, monkeypatch):
    """Sem review_id_externo, dedup cai no hash legacy (texto[:200] + autor)."""
    monkeypatch.setattr(
        "src.coletor.pipeline.classificar",
        lambda **k: type(
            "R",
            (),
            {
                "subpilar": "Pa1",
                "tipo": "promotor",
                "confianca": 0.9,
                "justificativa": "ok",
                "prompt_versao": "v3.0",
            },
        )(),
    )
    v1 = processar_verbatim_coletado(texto="MESMO TEXTO", fonte=fonte_t, autor=None)
    assert v1 is not None
    v2 = processar_verbatim_coletado(texto="MESMO TEXTO", fonte=fonte_t, autor=None)
    assert v2 is None  # dedup por hash


def test_ratings_only_multiplos_autores_none_nao_colide_hash(fonte_t, db_session, monkeypatch):
    """REGRESSÃO: 2 ratings-only com autor=None mas review_id diferente devem
    persistir (não colidir na UNIQUE constraint empresa_id+hash_dedup).

    Era o bug que rejeitava 1097 dos 1099 sem-texto do Confins."""
    monkeypatch.setattr(
        "src.coletor.pipeline.classificar",
        lambda **k: (_ for _ in ()).throw(AssertionError("nao chamar")),
    )
    v1 = processar_verbatim_coletado(
        texto="",
        fonte=fonte_t,
        autor=None,
        rating=5,
        review_id_externo="rev_id_A",
    )
    v2 = processar_verbatim_coletado(
        texto="",
        fonte=fonte_t,
        autor=None,
        rating=5,
        review_id_externo="rev_id_B",
    )
    assert v1 is not None
    assert v2 is not None
    assert v1.hash_dedup != v2.hash_dedup  # hashes únicos


def test_ratings_only_dedup_por_review_id_quando_repetido(fonte_t, db_session, monkeypatch):
    """Ratings-only com mesmo review_id_externo → dedup."""
    monkeypatch.setattr(
        "src.coletor.pipeline.classificar",
        lambda **k: (_ for _ in ()).throw(AssertionError("nao chamar")),
    )
    v1 = processar_verbatim_coletado(
        texto="", fonte=fonte_t, rating=5, review_id_externo="rev_ro_dup"
    )
    assert v1 is not None
    v2 = processar_verbatim_coletado(
        texto="", fonte=fonte_t, rating=5, review_id_externo="rev_ro_dup"
    )
    assert v2 is None


# ── API: filtros novos ──────────────────────────────────────────────────


def _criar_v_diretamente(db_session, fonte_id, empresa_id, **kwargs):
    v = Verbatim(
        empresa_id=empresa_id,
        fonte_id=fonte_id,
        data_criacao_original=datetime.utcnow(),
        **kwargs,
    )
    db_session.add(v)
    db_session.commit()
    return v


def test_api_filtro_esconder_rating_only(client_loyall, db_session):
    e_id, _loc, f_id = _fonte_de_teste(client_loyall)
    _criar_v_diretamente(
        db_session,
        f_id,
        e_id,
        texto="com texto",
        subpilar="Pa1",
        tipo="promotor",
        tem_texto=True,
        hash_dedup="h1",
    )
    _criar_v_diretamente(
        db_session,
        f_id,
        e_id,
        texto="",
        subpilar="Pa1",
        tipo="promotor",
        tem_texto=False,
        rating=5,
        hash_dedup="h2",
        review_id_externo="ext_2",
    )
    todos = client_loyall.get(f"/api/empresas/{e_id}/verbatins").get_json()
    assert todos["total"] == 2
    so_texto = client_loyall.get(
        f"/api/empresas/{e_id}/verbatins?esconder_rating_only=1"
    ).get_json()
    assert so_texto["total"] == 1
    assert so_texto["verbatins"][0]["texto"] == "com texto"


def test_api_filtro_rating(client_loyall, db_session):
    e_id, _loc, f_id = _fonte_de_teste(client_loyall)
    for r in (1, 2, 5, 5):
        _criar_v_diretamente(
            db_session,
            f_id,
            e_id,
            texto="",
            rating=r,
            tem_texto=False,
            hash_dedup=f"h_{r}_{datetime.utcnow().timestamp()}",
            review_id_externo=f"ext_{r}_{datetime.utcnow().timestamp()}",
        )
    cinco = client_loyall.get(f"/api/empresas/{e_id}/verbatins?rating=5").get_json()
    assert cinco["total"] == 2


def test_api_serializer_inclui_rating_e_tem_texto(client_loyall, db_session):
    e_id, _loc, f_id = _fonte_de_teste(client_loyall)
    _criar_v_diretamente(
        db_session,
        f_id,
        e_id,
        texto="",
        rating=3,
        tem_texto=False,
        hash_dedup="h_ser",
        review_id_externo="ext_ser",
    )
    body = client_loyall.get(f"/api/empresas/{e_id}/verbatins").get_json()
    v = body["verbatins"][0]
    assert v["tem_texto"] is False
    assert v["rating"] == 3
    assert v["review_id_externo"] == "ext_ser"


# ── UI: badge "só rating" + estrelas ────────────────────────────────────


def test_ui_badge_so_rating_renderiza(client_loyall, db_session):
    e_id, _loc, f_id = _fonte_de_teste(client_loyall)
    _criar_v_diretamente(
        db_session,
        f_id,
        e_id,
        texto="",
        rating=5,
        subpilar="Pa1",
        tipo="promotor",
        tem_texto=False,
        hash_dedup="h_ui",
        review_id_externo="ext_ui",
    )
    r = client_loyall.get(f"/empresas/{e_id}/verbatins")
    html = r.get_data(as_text=True)
    assert "só rating" in html
    assert "★★★★★" in html
    assert "review sem texto" in html


def test_ui_badge_rating_em_verbatim_com_texto(client_loyall, db_session):
    """Verbatim com texto E rating mostra estrelas + texto, sem badge 'só rating'."""
    e_id, _loc, f_id = _fonte_de_teste(client_loyall)
    _criar_v_diretamente(
        db_session,
        f_id,
        e_id,
        texto="Comida excelente",
        rating=5,
        subpilar="P2",
        tipo="promotor",
        tem_texto=True,
        hash_dedup="h_uitxt",
    )
    r = client_loyall.get(f"/empresas/{e_id}/verbatins")
    html = r.get_data(as_text=True)
    assert "Comida excelente" in html
    assert "★★★★★" in html
    assert "só rating" not in html


# ── Sanidade do dicionário de classificação ──────────────────────────────


def test_rating_para_classificacao_tem_5_chaves():
    assert set(RATING_PARA_CLASSIFICACAO.keys()) == {1, 2, 3, 4, 5}


def test_rating_3_eh_sem_lastro_inativo():
    """rating=3 vai pra sem_lastro/inativo (restrição rígida do classifier)."""
    sp, tp, _cf, _jf = RATING_PARA_CLASSIFICACAO[3]
    assert sp == "sem_lastro"
    assert tp == "inativo"
