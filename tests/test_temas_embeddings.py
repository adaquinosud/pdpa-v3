"""Tests CP-7 do Caminho A: embeddings + cache."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import numpy as np

from src.models.temas import VerbatimEmbedding
from src.models.verbatim import Verbatim
from src.temas.embeddings import (
    _bytes_to_vetor,
    _vetor_to_bytes,
    carregar_embeddings,
    embed_verbatins_pendentes,
)


def _criar_verbatim(db_session, empresa_id, fonte_id, texto="t", local_id=None):
    v = Verbatim(
        empresa_id=empresa_id,
        fonte_id=fonte_id,
        local_id=local_id,
        texto=texto,
        data_criacao_original=datetime.utcnow() - timedelta(days=3),
        hash_dedup=f"h-{texto}-{datetime.utcnow().timestamp()}",
        subpilar="Pa1",
        tipo="promotor",
        tem_texto=True,
    )
    db_session.add(v)
    db_session.commit()
    return v


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"EEM-{sfx}"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais",
        json={"nome": "L", "agrupamento_id": a["id"]},
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ_em_{sfx}"},
    ).get_json()
    return e, a, loc, f


def test_vetor_serializacao_ida_e_volta():
    v = np.random.rand(1536).astype(np.float32)
    b = _vetor_to_bytes(v)
    v2 = _bytes_to_vetor(b)
    assert v.shape == v2.shape == (1536,)
    np.testing.assert_array_equal(v, v2)
    assert v2.dtype == np.float32


def test_embed_verbatins_pendentes_pula_com_embedding_existente(client_loyall, db_session):
    """Idempotência: rodar 2x não regenera."""
    e, _, loc, f = _ctx(client_loyall, "p1")
    v = _criar_verbatim(db_session, e["id"], f["id"], texto="t1", local_id=loc["id"])
    # pre-popula 1 embedding
    db_session.add(
        VerbatimEmbedding(
            verbatim_id=v.id, modelo="m-test", vetor=_vetor_to_bytes(np.zeros(4, dtype=np.float32))
        )
    )
    db_session.commit()

    # mock do OpenAI client — não deve ser chamado pois já existe
    with patch("src.temas.embeddings._get_openai_client") as mock_get:
        resumo = embed_verbatins_pendentes(e["id"], modelo="m-test")
        mock_get.assert_not_called()
    assert resumo["elegiveis"] == 1
    assert resumo["gerados"] == 0
    assert resumo["ja_existiam"] == 1


def test_embed_verbatins_pendentes_gera_via_mock_openai(client_loyall, db_session):
    """Gera embedding via mock; persiste; verifica blob salvo."""
    e, _, loc, f = _ctx(client_loyall, "g1")
    v1 = _criar_verbatim(db_session, e["id"], f["id"], texto="texto um", local_id=loc["id"])
    v2 = _criar_verbatim(db_session, e["id"], f["id"], texto="texto dois", local_id=loc["id"])

    # mock retorna 2 embeddings dummy
    fake_resp = MagicMock()
    fake_resp.data = [
        MagicMock(embedding=[0.1, 0.2, 0.3]),
        MagicMock(embedding=[0.4, 0.5, 0.6]),
    ]
    fake_client = MagicMock()
    fake_client.embeddings.create.return_value = fake_resp
    with patch("src.temas.embeddings._get_openai_client", return_value=fake_client):
        resumo = embed_verbatins_pendentes(e["id"], modelo="m-mocked")

    assert resumo["gerados"] == 2
    assert resumo["elegiveis"] == 2
    # Verifica persistência
    rows = (
        db_session.query(VerbatimEmbedding)
        .filter(VerbatimEmbedding.modelo == "m-mocked")
        .order_by(VerbatimEmbedding.verbatim_id.asc())
        .all()
    )
    assert len(rows) == 2
    vetor_v1 = _bytes_to_vetor(rows[0].vetor)
    assert vetor_v1.shape == (3,)
    np.testing.assert_allclose(vetor_v1, [0.1, 0.2, 0.3], rtol=1e-6)
    # Carrega via API
    loaded = carregar_embeddings([v1.id, v2.id], modelo="m-mocked")
    assert set(loaded.keys()) == {v1.id, v2.id}


def test_embed_verbatins_pendentes_filtra_sem_texto(client_loyall, db_session):
    """Verbatins sem texto não geram embedding."""
    e, _, loc, f = _ctx(client_loyall, "f1")
    v_com = _criar_verbatim(db_session, e["id"], f["id"], texto="ok", local_id=loc["id"])
    # Verbatim sem texto (texto="" + tem_texto=False) — verbatim só-rating, p.ex.
    v_sem = Verbatim(
        empresa_id=e["id"],
        fonte_id=f["id"],
        local_id=loc["id"],
        texto="",
        data_criacao_original=datetime.utcnow(),
        hash_dedup="h-sem-texto",
        subpilar="Pa1",
        tipo="promotor",
        tem_texto=False,
    )
    db_session.add(v_sem)
    db_session.commit()

    fake_resp = MagicMock()
    fake_resp.data = [MagicMock(embedding=[1.0, 2.0])]
    fake_client = MagicMock()
    fake_client.embeddings.create.return_value = fake_resp
    with patch("src.temas.embeddings._get_openai_client", return_value=fake_client):
        resumo = embed_verbatins_pendentes(e["id"], modelo="m-filter")
    assert resumo["elegiveis"] == 1
    assert resumo["gerados"] == 1
    assert v_com.id is not None  # silencia linter


def test_embed_verbatins_pendentes_respeita_limite(client_loyall, db_session):
    e, _, loc, f = _ctx(client_loyall, "l1")
    for i in range(5):
        _criar_verbatim(db_session, e["id"], f["id"], texto=f"t{i}", local_id=loc["id"])

    fake_resp = MagicMock()
    fake_resp.data = [MagicMock(embedding=[0.0]) for _ in range(3)]
    fake_client = MagicMock()
    fake_client.embeddings.create.return_value = fake_resp
    with patch("src.temas.embeddings._get_openai_client", return_value=fake_client):
        resumo = embed_verbatins_pendentes(e["id"], modelo="m-limite", limite=3)
    assert resumo["gerados"] == 3
    assert resumo["elegiveis"] == 5  # total elegíveis ignora limite


def test_carregar_embeddings_vazio():
    assert carregar_embeddings([]) == {}
