"""Testes UI do CP-5 (Bloco 6): modal de temas no painel + admin/temas."""

from __future__ import annotations

from datetime import datetime, timedelta

from src.models.temas import Tema, VerbatimTema
from src.models.verbatim import Verbatim


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"EUT-{sfx}"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais",
        json={"nome": "L", "agrupamento_id": a["id"]},
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ_ut_{sfx}"},
    ).get_json()
    return e, a, loc, f


def _criar_verbatim(db_session, empresa_id, fonte_id, local_id, texto, sub="Pa1", tipo="promotor"):
    v = Verbatim(
        empresa_id=empresa_id,
        fonte_id=fonte_id,
        local_id=local_id,
        texto=texto,
        data_criacao_original=datetime.utcnow() - timedelta(days=3),
        hash_dedup=f"h-{texto}-{datetime.utcnow().timestamp()}",
        subpilar=sub,
        tipo=tipo,
        tem_texto=True,
    )
    db_session.add(v)
    db_session.commit()
    return v


# ── /ui/empresas/<id>/painel/temas-modal ─────────────────────────────


def test_temas_modal_loyall_renderiza_drawer(client_loyall, db_session):
    e, _, loc, f = _ctx(client_loyall, "m1")
    v = _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "txt", sub="Pa1", tipo="promotor")
    t = Tema(empresa_id=e["id"], nome="fila check-in", slug="fila-check-in")
    db_session.add(t)
    db_session.commit()
    db_session.add(VerbatimTema(verbatim_id=v.id, tema_id=t.id, confianca=0.8, origem="llm"))
    db_session.commit()

    r = client_loyall.get(f"/ui/empresas/{e['id']}/painel/temas-modal?subpilar=Pa1&tipo=promotor")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'id="temas-drawer"' in html
    assert "Pa1" in html
    assert "promotor" in html
    assert "fila check-in" in html


def test_temas_modal_sem_dados_mostra_empty_state(client_loyall):
    e, _, _, _ = _ctx(client_loyall, "m2")
    r = client_loyall.get(f"/ui/empresas/{e['id']}/painel/temas-modal?subpilar=Pa1&tipo=promotor")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Nenhum tema extraído" in html
    assert "flask temas-extrair" in html  # comando de instrução


def test_temas_modal_cliente_outra_empresa_403(client_loyall, client_cliente_factory):
    e1 = client_loyall.post("/api/empresas/", json={"nome": "EUTout1"}).get_json()
    e2 = client_loyall.post("/api/empresas/", json={"nome": "EUTout2"}).get_json()
    c = client_cliente_factory(e2["id"])
    r = c.get(f"/ui/empresas/{e1['id']}/painel/temas-modal?subpilar=Pa1&tipo=promotor")
    assert r.status_code == 403


def test_temas_modal_sem_login_redireciona(app):
    e_id = 1
    with app.test_client() as anon:
        r = anon.get(f"/ui/empresas/{e_id}/painel/temas-modal?subpilar=Pa1&tipo=promotor")
        # _require_login_html redireciona para /login
        assert r.status_code in (302, 401)


def test_temas_modal_subpilar_obrigatorio_400(client_loyall):
    e, _, _, _ = _ctx(client_loyall, "m3")
    r = client_loyall.get(f"/ui/empresas/{e['id']}/painel/temas-modal")
    # painel_temas API retorna 400 quando subpilar/tipo ausentes;
    # painel_temas_modal repassa esse status.
    assert r.status_code == 400


# ── /admin/temas/<id> ────────────────────────────────────────────────


def test_admin_temas_loyall_renderiza(client_loyall, db_session):
    e, _, _, _ = _ctx(client_loyall, "a1")
    db_session.add_all(
        [
            Tema(empresa_id=e["id"], nome="fila", slug="fila"),
            Tema(empresa_id=e["id"], nome="atendimento", slug="atendimento"),
        ]
    )
    db_session.commit()
    r = client_loyall.get(f"/admin/temas/{e['id']}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Catálogo de temas" in html
    assert "fila" in html
    assert "atendimento" in html


def test_admin_temas_cliente_403(client_loyall, client_cliente_factory):
    e = client_loyall.post("/api/empresas/", json={"nome": "EUTa2"}).get_json()
    c = client_cliente_factory(e["id"])
    r = c.get(f"/admin/temas/{e['id']}")
    assert r.status_code == 403


# ── filtro ?tema_id=X em /verbatins (UI + API) ───────────────────────


def test_verbatins_filtro_tema_id(client_loyall, db_session):
    e, _, loc, f = _ctx(client_loyall, "f1")
    v1 = _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "tem-fila")
    _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "sem-fila")
    t = Tema(empresa_id=e["id"], nome="fila", slug="fila")
    db_session.add(t)
    db_session.commit()
    db_session.add(VerbatimTema(verbatim_id=v1.id, tema_id=t.id, confianca=0.7, origem="llm"))
    db_session.commit()

    # API: lista filtrada por tema
    body = client_loyall.get(f"/api/empresas/{e['id']}/verbatins?tema_id={t.id}").get_json()
    assert body["total"] == 1
    assert body["verbatins"][0]["id"] == v1.id

    # UI: tela HTML responde 200 com filtro aplicado
    r = client_loyall.get(f"/empresas/{e['id']}/verbatins?tema_id={t.id}")
    assert r.status_code == 200


# ── breadcrumb e voltar contextual (validação leve) ──────────────────


def test_painel_renderiza_botao_temas_e_link_admin(client_loyall, db_session):
    """Painel inclui botão 'T' por bucket (matriz) e link 'Temas (admin)' na sidebar."""
    e, _, loc, f = _ctx(client_loyall, "p1")
    # Verbatim em Pa1/promotor pra matriz ter linha com count > 0
    _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "txt", sub="Pa1", tipo="promotor")
    r = client_loyall.get(f"/empresas/{e['id']}/painel")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # Botão T por bucket usa hx-get para ui.painel_temas_modal
    assert "painel/temas-modal" in html
    # Sidebar admin temas (loyall only)
    assert "Temas (admin)" in html
    # Breadcrumb Empresas › … › Painel
    assert "Breadcrumb" in html
    assert "Painel" in html


def test_verbatins_voltar_painel_quando_origem(client_loyall, db_session):
    e, _, loc, f = _ctx(client_loyall, "v1")
    _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "txt")
    r = client_loyall.get(f"/empresas/{e['id']}/verbatins?origem=painel&periodo=30d")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # No header h1, "← Painel" aparece (voltar_texto)
    assert "← Painel" in html
    # Breadcrumb com ramo Painel
    assert ">Painel</a>" in html


def test_verbatins_voltar_empresa_sem_origem(client_loyall, db_session):
    e, _, loc, f = _ctx(client_loyall, "v2")
    _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "txt")
    r = client_loyall.get(f"/empresas/{e['id']}/verbatins")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # voltar_texto = nome da empresa
    assert "← EUT-v2" in html
