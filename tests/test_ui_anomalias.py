"""Tests da tela de anomalias (Monitoramento ML CP-6 — UI + validação)."""

from __future__ import annotations

from src.anomalias.combinador import detectar_e_persistir
from src.models.anomalia import AnomaliaDetectada


def _empresa(client_loyall, sfx):
    return client_loyall.post("/api/empresas/", json={"nome": f"EUI-{sfx}"}).get_json()


def _seed(empresa_id):
    def _fake(_emp):
        return [
            {
                "tipo": "tema",
                "chave": "tema: fila no balcão",
                "severidade": "critico",
                "score_final": 88.0,
                "direcao": "negativa",
                "tendencia": "Tema em alta — corroborado por tema",
            },
            {
                "tipo": "indicador",
                "chave": "loja 1 · D1",
                "severidade": "atencao",
                "score_final": 50.0,
                "subpilar": "D1",
                "local_id": None,
                "score_cross_sectional": 45.0,
                "score_temporal": 30.0,
            },
        ]

    detectar_e_persistir(empresa_id, detectar_fn=_fake)


def test_tela_anomalias_renderiza_com_resumo(client_loyall):
    e = _empresa(client_loyall, "rend")
    _seed(e["id"])
    r = client_loyall.get(f"/empresas/{e['id']}/anomalias")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "fila no balcão" in html
    assert "1 críticas" in html and "1 atenção" in html
    assert "corroborado por tema" in html  # badge de corroboração
    assert "Validar:" in html


def test_tela_filtra_por_severidade(client_loyall):
    e = _empresa(client_loyall, "filt")
    _seed(e["id"])
    r = client_loyall.get(f"/empresas/{e['id']}/anomalias?severidade=critico")
    html = r.get_data(as_text=True)
    assert "fila no balcão" in html
    assert "loja 1 · D1" not in html  # a de atenção foi filtrada


def test_validar_atualiza_estado_e_devolve_card(client_loyall, db_session):
    e = _empresa(client_loyall, "val")
    _seed(e["id"])
    aid = (
        db_session.query(AnomaliaDetectada)
        .filter_by(empresa_id=e["id"], chave="tema: fila no balcão")
        .first()
        .id
    )
    r = client_loyall.post(
        f"/ui/empresas/{e['id']}/anomalias/{aid}/validar", data={"estado": "confirmado"}
    )
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "confirmado" in html and f"anomalia-card-{aid}" in html

    db_session.expire_all()
    a = db_session.get(AnomaliaDetectada, aid)
    assert a.estado_validacao == "confirmado" and a.revisada is True


def test_validar_estado_invalido_400(client_loyall, db_session):
    e = _empresa(client_loyall, "inv")
    _seed(e["id"])
    aid = db_session.query(AnomaliaDetectada).filter_by(empresa_id=e["id"]).first().id
    r = client_loyall.post(
        f"/ui/empresas/{e['id']}/anomalias/{aid}/validar", data={"estado": "lixo"}
    )
    assert r.status_code == 400
