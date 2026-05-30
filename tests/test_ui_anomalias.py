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


def test_card_colapsado_estrutura_e_acao_rapida(client_loyall):
    e = _empresa(client_loyall, "col")
    _seed(e["id"])
    html = client_loyall.get(f"/empresas/{e['id']}/anomalias").get_data(as_text=True)
    assert 'class="anom-card' in html and "data-anom=" in html  # card colapsável
    assert "toggleAnom(" in html  # clique no header alterna
    assert "anom-resumo" in html  # resumo curto no estado colapsado
    assert "Expandir todos" in html and "Colapsar todos" in html
    assert '"estado": "falso_positivo"' in html  # validação rápida no header


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


# ── CP-UX-b: título legível (nome da loja) no header da anomalia ──────────


def test_anomalia_view_titulo_com_local_usa_nome():
    """Indicador com local_nome → titulo = 'Nome · subpilar' (substitui loja XX)."""
    from types import SimpleNamespace

    from src.ui import _anomalia_view

    a = SimpleNamespace(
        id=1,
        tipo="indicador",
        chave="loja 77 · D3",
        severidade="atencao",
        score_final=50.0,
        score_temporal=None,
        score_cross_sectional=None,
        magnitude=None,
        direcao="negativa",
        tendencia=None,
        subpilar="D3",
        periodo="2026-04",
        local_id=77,
        tema_id=None,
        leitura_editorial=None,
        estado_validacao="pendente",
        nota_editorial=None,
    )
    view = _anomalia_view(a, local_nome="TikTok @bhairport", tema_nome=None)
    assert view.titulo == "TikTok @bhairport · D3"
    assert view.local_nome == "TikTok @bhairport"


def test_anomalia_view_titulo_sem_local_usa_chave():
    """Tema/cruzamento (sem local) → titulo = chave (fallback, inalterado)."""
    from types import SimpleNamespace

    from src.ui import _anomalia_view

    a = SimpleNamespace(
        id=2,
        tipo="tema",
        chave="tema: fila no balcão",
        severidade="critico",
        score_final=88.0,
        score_temporal=None,
        score_cross_sectional=None,
        magnitude=None,
        direcao="negativa",
        tendencia=None,
        subpilar=None,
        periodo=None,
        local_id=None,
        tema_id=9,
        leitura_editorial=None,
        estado_validacao="pendente",
        nota_editorial=None,
    )
    view = _anomalia_view(a, local_nome=None, tema_nome="fila no balcão")
    assert view.titulo == "tema: fila no balcão"
