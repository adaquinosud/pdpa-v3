"""Testes da UI Flask+Jinja+HTMX (Bloco 4 — CP5)."""

from __future__ import annotations

from src.models.empresa import Empresa


# ── Rotas públicas ───────────────────────────────────────────────────────


def test_home_sem_login_redireciona_login(client):
    r = client.get("/")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/login")


def test_login_form_acessivel(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert b"PDPA" in r.data
    assert b"email" in r.data.lower()


def test_login_post_credencial_valida(client, usuario_loyall):
    r = client.post(
        "/login",
        data={"email": usuario_loyall.email, "senha": "senha-teste-12345"},
    )
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/empresas")


def test_login_post_credencial_invalida(client, usuario_loyall):
    r = client.post(
        "/login",
        data={"email": usuario_loyall.email, "senha": "errada"},
    )
    assert r.status_code == 401
    assert b"Credenciais" in r.data or b"inv" in r.data.lower()


def test_logout_limpa_sessao(client, usuario_loyall):
    client.post(
        "/login",
        data={"email": usuario_loyall.email, "senha": "senha-teste-12345"},
    )
    r = client.post("/logout")
    assert r.status_code == 302
    # Próxima request sem sessão → redirect login
    r2 = client.get("/empresas", follow_redirects=False)
    assert r2.status_code == 302


# ── Lista de empresas ───────────────────────────────────────────────────


def test_lista_empresas_loyall(client_loyall):
    # Cria via API
    e1 = client_loyall.post("/api/empresas/", json={"nome": "Acme"}).get_json()
    client_loyall.post("/api/empresas/", json={"nome": "Bcme"}).get_json()
    r = client_loyall.get("/empresas")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Acme" in html
    assert "Bcme" in html
    # Detalhe link funcionando
    assert f"/empresas/{e1['id']}" in html


def test_lista_empresas_cliente_so_a_sua(client_loyall, client_cliente_factory):
    e1 = client_loyall.post("/api/empresas/", json={"nome": "EmpDoCli"}).get_json()
    client_loyall.post("/api/empresas/", json={"nome": "Outra"}).get_json()
    cli = client_cliente_factory(e1["id"])
    # Cliente com 1 empresa → redirect direto pro detalhe
    r = cli.get("/empresas", follow_redirects=False)
    assert r.status_code == 302
    assert f"/empresas/{e1['id']}" in r.headers["Location"]


def test_detalhe_empresa_renderiza(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "EE"}).get_json()
    client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "GG"})
    client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "LL"})
    r = client_loyall.get(f"/empresas/{e['id']}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "EE" in html
    assert "GG" in html
    assert "LL" in html


def test_detalhe_empresa_cliente_de_outra_403(client_loyall, client_cliente_factory):
    e1 = client_loyall.post("/api/empresas/", json={"nome": "EA"}).get_json()
    e2 = client_loyall.post("/api/empresas/", json={"nome": "EB"}).get_json()
    cli = client_cliente_factory(e1["id"])
    r = cli.get(f"/empresas/{e2['id']}")
    assert r.status_code == 403


# ── HTMX partials ────────────────────────────────────────────────────────


def test_htmx_criar_agrupamento_devolve_fragmento(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "E"}).get_json()
    r = client_loyall.post(
        f"/ui/empresas/{e['id']}/agrupamentos",
        data={"nome": "AG1", "descricao": "Teste"},
    )
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "AG1" in html
    assert "<tr" in html  # fragmento HTML (não JSON)


def test_htmx_criar_agrupamento_cliente_bloqueado(client_loyall, client_cliente_factory):
    e = client_loyall.post("/api/empresas/", json={"nome": "E"}).get_json()
    cli = client_cliente_factory(e["id"])
    r = cli.post(f"/ui/empresas/{e['id']}/agrupamentos", data={"nome": "X"})
    assert r.status_code == 403


def test_htmx_criar_local_devolve_fragmento(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "E"}).get_json()
    r = client_loyall.post(
        f"/ui/empresas/{e['id']}/locais",
        data={"nome": "Loja", "endereco": "Rua X"},
    )
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Loja" in html
    assert "<tr" in html


def test_htmx_criar_fonte_local_devolve_fragmento(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "E"}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    r = client_loyall.post(
        f"/ui/locais/{loc['id']}/fontes",
        data={"conector_tipo": "google", "url": "ChIJ_x", "ativo": "on"},
    )
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "google" in html


def test_htmx_deletar_agrupamento(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "E"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "AG"}).get_json()
    r = client_loyall.delete(f"/ui/agrupamentos/{a['id']}")
    assert r.status_code == 200
    # Confirma que sumiu
    assert client_loyall.get(f"/api/agrupamentos/{a['id']}").status_code == 404


def test_htmx_deletar_local(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "E"}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    r = client_loyall.delete(f"/ui/locais/{loc['id']}")
    assert r.status_code == 200
    assert client_loyall.get(f"/api/locais/{loc['id']}").status_code == 404


# ── Importar Excel via UI ───────────────────────────────────────────────


def test_importar_get_form(client_loyall):
    r = client_loyall.get("/empresas/importar")
    assert r.status_code == 200
    assert b"Importar" in r.data


def test_importar_cliente_403(client_loyall, client_cliente_factory):
    e = client_loyall.post("/api/empresas/", json={"nome": "E"}).get_json()
    cli = client_cliente_factory(e["id"])
    r = cli.get("/empresas/importar")
    assert r.status_code == 403


# ── Nova empresa via UI ──────────────────────────────────────────────────


def test_nova_empresa_post_redireciona(client_loyall, db_session):
    r = client_loyall.post(
        "/empresas/nova",
        data={"nome": "ViaUI", "setor": "varejo", "site": "https://x"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    e = db_session.query(Empresa).filter_by(nome="ViaUI").first()
    assert e is not None
    assert e.site == "https://x"


def test_nova_empresa_cliente_403(client_loyall, client_cliente_factory):
    e = client_loyall.post("/api/empresas/", json={"nome": "E"}).get_json()
    cli = client_cliente_factory(e["id"])
    r = cli.get("/empresas/nova")
    assert r.status_code == 403


# ── CP-A: Edição inline + inativar via UI ────────────────────────────────


def test_ui_inline_edit_agrupamento_get_form(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "EedAg"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    r = client_loyall.get(f"/ui/agrupamentos/{a['id']}/editar")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "<input" in html
    assert 'name="nome"' in html
    assert "salvar" in html


def test_ui_inline_save_agrupamento(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "EsvAg"}).get_json()
    a = client_loyall.post(
        f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "Antigo"}
    ).get_json()
    r = client_loyall.put(
        f"/ui/agrupamentos/{a['id']}",
        data={"nome": "Novo nome", "descricao": "Nova desc"},
    )
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Novo nome" in html
    # Verifica persistência
    body = client_loyall.get(f"/api/agrupamentos/{a['id']}").get_json()
    assert body["nome"] == "Novo nome"
    assert body["descricao"] == "Nova desc"


def test_ui_inline_save_agrupamento_conflito_nome(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "Eag"}).get_json()
    client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "X"})
    a2 = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "Y"}).get_json()
    r = client_loyall.put(f"/ui/agrupamentos/{a2['id']}", data={"nome": "X"})
    assert r.status_code == 409


def test_ui_inline_save_agrupamento_cliente_403(client_loyall, client_cliente_factory):
    e = client_loyall.post("/api/empresas/", json={"nome": "E"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    cli = client_cliente_factory(e["id"])
    r = cli.put(f"/ui/agrupamentos/{a['id']}", data={"nome": "Hack"})
    assert r.status_code == 403


def test_ui_inativar_agrupamento_via_patch(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "Einat"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    r = client_loyall.patch(f"/ui/agrupamentos/{a['id']}/inativar")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "reativar" in html  # botão agora oferece reativar
    # toggle de volta
    r2 = client_loyall.patch(f"/ui/agrupamentos/{a['id']}/inativar")
    html2 = r2.get_data(as_text=True)
    assert "inativar" in html2


def test_ui_inline_save_local(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "ElocS"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "Antigo"}).get_json()
    r = client_loyall.put(
        f"/ui/locais/{loc['id']}",
        data={
            "nome": "Novo",
            "agrupamento_id": str(a["id"]),
            "endereco": "Rua Y",
        },
    )
    assert r.status_code == 200
    body = client_loyall.get(f"/api/locais/{loc['id']}").get_json()
    assert body["nome"] == "Novo"
    assert body["agrupamento_id"] == a["id"]
    assert body["endereco"] == "Rua Y"


def test_ui_inativar_local_alterna_status(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "Eil"}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    r = client_loyall.patch(f"/ui/locais/{loc['id']}/inativar")
    assert r.status_code == 200
    body = client_loyall.get(f"/api/locais/{loc['id']}").get_json()
    assert body["status"] == "desativado"


def test_ui_inline_save_fonte_url(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "Ef"}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": "ChIJ_old"},
    ).get_json()
    r = client_loyall.put(
        f"/ui/fontes/{f['id']}",
        data={"url": "ChIJ_NEW", "observacao": "atualizada"},
    )
    assert r.status_code == 200
    body = client_loyall.get(f"/api/fontes/{f['id']}").get_json()
    assert body["url"] == "ChIJ_NEW"
    assert body["observacao"] == "atualizada"


def test_ui_inativar_fonte_via_patch(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "Efnt"}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": "ChIJ_xx"},
    ).get_json()
    r = client_loyall.patch(f"/ui/fontes/{f['id']}/inativar")
    assert r.status_code == 200
    body = client_loyall.get(f"/api/fontes/{f['id']}").get_json()
    assert body["ativo"] is False


# ── Modal de edição da empresa ──────────────────────────────────────────


def test_ui_editar_empresa_modal_get(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "EM"}).get_json()
    r = client_loyall.get(f"/ui/empresas/{e['id']}/editar-modal")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'name="nome"' in html
    assert 'name="site"' in html
    assert "observacao" in html


def test_ui_editar_empresa_modal_cliente_403(client_loyall, client_cliente_factory):
    e = client_loyall.post("/api/empresas/", json={"nome": "E"}).get_json()
    cli = client_cliente_factory(e["id"])
    r = cli.get(f"/ui/empresas/{e['id']}/editar-modal")
    assert r.status_code == 403


def test_ui_salvar_empresa_via_put(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "EsvU"}).get_json()
    r = client_loyall.put(
        f"/ui/empresas/{e['id']}",
        data={
            "nome": "Renomeado",
            "setor": "novo-setor",
            "site": "https://novo.example",
            "observacao": "nova obs",
        },
    )
    assert r.status_code == 200
    body = client_loyall.get(f"/api/empresas/{e['id']}").get_json()
    assert body["nome"] == "Renomeado"
    assert body["setor"] == "novo-setor"
    assert body["site"] == "https://novo.example"
    assert body["observacao"] == "nova obs"


def test_ui_salvar_empresa_conflito_nome(client_loyall):
    client_loyall.post("/api/empresas/", json={"nome": "Ja-existe"})
    e2 = client_loyall.post("/api/empresas/", json={"nome": "Outra"}).get_json()
    r = client_loyall.put(
        f"/ui/empresas/{e2['id']}",
        data={"nome": "Ja-existe"},
    )
    assert r.status_code == 409


def test_ui_salvar_empresa_cliente_403(client_loyall, client_cliente_factory):
    e = client_loyall.post("/api/empresas/", json={"nome": "E"}).get_json()
    cli = client_cliente_factory(e["id"])
    r = cli.put(f"/ui/empresas/{e['id']}", data={"nome": "Hack"})
    assert r.status_code == 403


# ── Detalhe agora exibe botão 'editar' no header para loyall ───────────


def test_detalhe_mostra_botao_editar_para_loyall(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "EedB"}).get_json()
    r = client_loyall.get(f"/empresas/{e['id']}")
    html = r.get_data(as_text=True)
    assert "editar-modal" in html  # link do botão


def test_detalhe_nao_mostra_botao_editar_para_cliente(client_loyall, client_cliente_factory):
    e = client_loyall.post("/api/empresas/", json={"nome": "EedB2"}).get_json()
    cli = client_cliente_factory(e["id"])
    r = cli.get(f"/empresas/{e['id']}")
    html = r.get_data(as_text=True)
    assert "editar-modal" not in html
