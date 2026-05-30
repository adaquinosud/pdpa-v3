"""Testes do endpoint ``POST /api/coleta/disparar/<fonte_id>``.

Os coletores são **mockados** via ``monkeypatch`` — não chamam Apify real.
A função ``_roteamento_coletores`` é reconstruída a cada request, então o
monkeypatch de ``src.coletor.<modulo>.coletar`` é visível.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from src.models.empresa import Empresa
from src.models.fonte import Fonte


def _stats_sucesso() -> Dict[str, Any]:
    return {"coletados": 5, "novos": 3, "duplicados": 1, "erros": 1, "falhou_apify": False}


def _stats_falhou() -> Dict[str, Any]:
    return {"coletados": 0, "novos": 0, "duplicados": 0, "erros": 0, "falhou_apify": True}


@pytest.fixture
def fonte_google(db_session: Session) -> Fonte:
    empresa = Empresa(nome="X", setor="varejo")
    db_session.add(empresa)
    db_session.commit()
    fonte = Fonte(
        empresa_id=empresa.id,
        entidade_tipo="empresa",
        entidade_id=empresa.id,
        conector_tipo="google",
        url="ChIJ123",
    )
    db_session.add(fonte)
    db_session.commit()
    return fonte


def test_disparar_404_fonte_inexistente(client_loyall: FlaskClient) -> None:
    response = client_loyall.post("/api/coleta/disparar/99999")
    assert response.status_code == 404
    assert response.json["erro"] == "Fonte não encontrada"


def test_disparar_400_conector_nao_suportado(
    client_loyall: FlaskClient, db_session: Session
) -> None:
    empresa = Empresa(nome="Y")
    db_session.add(empresa)
    db_session.commit()
    fonte = Fonte(
        empresa_id=empresa.id,
        entidade_tipo="empresa",
        entidade_id=empresa.id,
        conector_tipo="conector_inventado",
        url="x",
    )
    db_session.add(fonte)
    db_session.commit()

    response = client_loyall.post(f"/api/coleta/disparar/{fonte.id}")
    assert response.status_code == 400
    assert "Conector não suportado" in response.json["erro"]
    assert "google" in response.json["conectores_suportados"]


def test_disparar_sucesso_roteia_para_google(
    client_loyall: FlaskClient, fonte_google: Fonte, monkeypatch
) -> None:
    """Endpoint dispara coletor correto, devolve stats."""
    capturado: Dict[str, Any] = {}

    def fake_coletar(fonte: Fonte) -> Dict[str, Any]:
        capturado["fonte_id"] = fonte.id
        capturado["conector"] = fonte.conector_tipo
        return _stats_sucesso()

    monkeypatch.setattr("src.coletor.google.coletar", fake_coletar)

    response = client_loyall.post(f"/api/coleta/disparar/{fonte_google.id}")
    assert response.status_code == 200
    assert response.json == _stats_sucesso()
    assert capturado["fonte_id"] == fonte_google.id
    assert capturado["conector"] == "google"


def test_disparar_atualiza_ultima_coleta_em_sucesso(
    client_loyall: FlaskClient, fonte_google: Fonte, db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr("src.coletor.google.coletar", lambda f: _stats_sucesso())

    assert fonte_google.ultima_coleta is None  # antes
    response = client_loyall.post(f"/api/coleta/disparar/{fonte_google.id}")
    assert response.status_code == 200

    db_session.expire_all()
    fonte_db = db_session.get(Fonte, fonte_google.id)
    assert fonte_db is not None
    assert fonte_db.ultima_coleta is not None  # depois


def test_disparar_nao_atualiza_ultima_coleta_se_falhou_apify(
    client_loyall: FlaskClient, fonte_google: Fonte, db_session: Session, monkeypatch
) -> None:
    """Quando ``falhou_apify=True``, ``ultima_coleta`` permanece None."""
    monkeypatch.setattr("src.coletor.google.coletar", lambda f: _stats_falhou())

    response = client_loyall.post(f"/api/coleta/disparar/{fonte_google.id}")
    assert response.status_code == 200
    assert response.json["falhou_apify"] is True

    db_session.expire_all()
    fonte_db = db_session.get(Fonte, fonte_google.id)
    assert fonte_db is not None
    assert fonte_db.ultima_coleta is None


def test_disparar_roteia_para_todos_conectores(
    client_loyall: FlaskClient, db_session: Session, monkeypatch
) -> None:
    """Os 10 conectores Apify estão mapeados e respondem 200."""
    conectores = [
        "google",
        "instagram",
        "facebook",
        "tripadvisor",
        "linkedin",
        "tiktok",
        "youtube",
        "appstore",
        "mercadolivre",
        "google_news",
    ]

    for conector in conectores:
        monkeypatch.setattr(f"src.coletor.{conector}.coletar", lambda f: _stats_sucesso())

    empresa = Empresa(nome="MultiConector")
    db_session.add(empresa)
    db_session.commit()

    for conector in conectores:
        fonte = Fonte(
            empresa_id=empresa.id,
            entidade_tipo="empresa",
            entidade_id=empresa.id,
            conector_tipo=conector,
            url=f"url-{conector}",
        )
        db_session.add(fonte)
        db_session.commit()

        response = client_loyall.post(f"/api/coleta/disparar/{fonte.id}")
        assert response.status_code == 200, f"{conector}: {response.json}"
        assert response.json == _stats_sucesso(), conector


# ── CP-UX-reprocessar: botão admin "Reprocessar empresa" ──────────────────


def test_reprocessar_cliente_403(client_cliente_factory, db_session: Session) -> None:
    """Cliente (não-Loyall) recebe 403 — rota restrita a admin Loyall."""
    empresa = Empresa(nome="ReprocGate")
    db_session.add(empresa)
    db_session.commit()

    tc = client_cliente_factory(empresa.id)
    resp = tc.post(f"/ui/empresas/{empresa.id}/reprocessar")
    assert resp.status_code == 403


def test_reprocessar_loyall_dispara_async(
    client_loyall: FlaskClient, db_session: Session, monkeypatch
) -> None:
    """Loyall: 200 + banner, e a rota CHAMA disparar_pos_coleta_async com o
    empresa_id (wiring — sem rodar o pipeline). Confirma o fire-and-forget."""
    empresa = Empresa(nome="ReprocLoyall")
    db_session.add(empresa)
    db_session.commit()

    chamadas = []
    monkeypatch.setattr(
        "src.coletor.orquestrador.disparar_pos_coleta_async",
        lambda empresa_id, *a, **k: chamadas.append(empresa_id),
    )

    resp = client_loyall.post(f"/ui/empresas/{empresa.id}/reprocessar")
    assert resp.status_code == 200
    assert "segundo plano" in resp.data.decode()
    assert chamadas == [empresa.id]
