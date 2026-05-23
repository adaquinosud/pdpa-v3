"""Testes do auth — Bloco 4 CP4.

Cobre:
    - login/logout/me (POST /api/auth/*)
    - cookies de sessão funcionando entre requests
    - login_required em endpoints de cadastro
    - loyall_required em criar/editar empresa e agrupamento
    - cliente só vê e edita a própria empresa
    - cliente NÃO pode criar/editar agrupamento (item 42 PENDENCIAS)
    - import-cadastro restrito a admin_loyall
"""

from __future__ import annotations


def _login(client_test, email: str, senha: str = "senha-teste-12345"):
    return client_test.post("/api/auth/login", json={"email": email, "senha": senha})


# ── /api/auth/* ──────────────────────────────────────────────────────────


def test_login_credencial_valida(client, usuario_loyall):
    r = _login(client, usuario_loyall.email)
    assert r.status_code == 200
    body = r.get_json()
    assert body["email"] == usuario_loyall.email
    assert body["papel"] == "admin_loyall"
    assert "senha_hash" not in body  # nunca expor


def test_login_senha_invalida(client, usuario_loyall):
    r = client.post(
        "/api/auth/login",
        json={"email": usuario_loyall.email, "senha": "senha-errada"},
    )
    assert r.status_code == 401


def test_login_user_inexistente(client):
    r = _login(client, "naoexiste@example.test")
    assert r.status_code == 401


def test_login_user_inativo(client, usuario_loyall, db_session):
    usuario_loyall.ativo = False
    db_session.commit()
    r = _login(client, usuario_loyall.email)
    assert r.status_code == 401


def test_login_faltando_campo(client):
    assert client.post("/api/auth/login", json={"email": "x@x"}).status_code == 400
    assert client.post("/api/auth/login", json={"senha": "y"}).status_code == 400


def test_me_sem_login(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_com_login(client, usuario_loyall):
    _login(client, usuario_loyall.email)
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.get_json()["email"] == usuario_loyall.email


def test_logout_limpa_sessao(client, usuario_loyall):
    _login(client, usuario_loyall.email)
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


# ── login_required em endpoints de cadastro ─────────────────────────────


def test_listar_empresas_exige_login(client):
    assert client.get("/api/empresas/").status_code == 401


def test_criar_empresa_exige_login(client):
    r = client.post("/api/empresas/", json={"nome": "X"})
    assert r.status_code == 401


def test_disparar_coleta_exige_login(client):
    assert client.post("/api/coleta/disparar/1").status_code == 401


def test_import_cadastro_exige_login(client):
    assert (
        client.post(
            "/api/empresas/import-cadastro",
            data={},
            content_type="multipart/form-data",
        ).status_code
        == 401
    )


# ── loyall_required: cliente NÃO pode escrever empresa nem agrupamento ──


def test_cliente_nao_pode_criar_empresa(client_loyall, client_cliente_factory):
    """Cliente logado em uma empresa NÃO pode criar nova empresa."""
    e = client_loyall.post("/api/empresas/", json={"nome": "EmpDoCliente"}).get_json()
    cli = client_cliente_factory(e["id"])
    r = cli.post("/api/empresas/", json={"nome": "OutraEmp"})
    assert r.status_code == 403


def test_cliente_nao_pode_atualizar_empresa(client_loyall, client_cliente_factory):
    e = client_loyall.post("/api/empresas/", json={"nome": "E"}).get_json()
    cli = client_cliente_factory(e["id"])
    r = cli.put(f"/api/empresas/{e['id']}", json={"site": "https://x"})
    assert r.status_code == 403


def test_cliente_nao_pode_criar_agrupamento(client_loyall, client_cliente_factory):
    """Agrupamento é prerrogativa Loyall (item 42 PENDENCIAS)."""
    e = client_loyall.post("/api/empresas/", json={"nome": "E"}).get_json()
    cli = client_cliente_factory(e["id"])
    r = cli.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"})
    assert r.status_code == 403


def test_cliente_pode_LER_agrupamento_da_sua_empresa(client_loyall, client_cliente_factory):
    e = client_loyall.post("/api/empresas/", json={"nome": "E"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    cli = client_cliente_factory(e["id"])
    assert cli.get(f"/api/empresas/{e['id']}/agrupamentos").status_code == 200
    assert cli.get(f"/api/agrupamentos/{a['id']}").status_code == 200


# ── Isolamento por empresa ──────────────────────────────────────────────


def test_cliente_so_ve_sua_empresa_no_listar(client_loyall, client_cliente_factory):
    """GET /api/empresas/ retorna só a empresa do cliente, não todas."""
    e1 = client_loyall.post("/api/empresas/", json={"nome": "EA"}).get_json()
    client_loyall.post("/api/empresas/", json={"nome": "EB"}).get_json()
    cli = client_cliente_factory(e1["id"])
    body = cli.get("/api/empresas/").get_json()
    assert len(body) == 1
    assert body[0]["nome"] == "EA"


def test_cliente_nao_acessa_outra_empresa(client_loyall, client_cliente_factory):
    e1 = client_loyall.post("/api/empresas/", json={"nome": "EA"}).get_json()
    e2 = client_loyall.post("/api/empresas/", json={"nome": "EB"}).get_json()
    cli = client_cliente_factory(e1["id"])
    r = cli.get(f"/api/empresas/{e2['id']}")
    assert r.status_code == 403


def test_cliente_cria_local_da_sua_empresa(client_loyall, client_cliente_factory):
    e = client_loyall.post("/api/empresas/", json={"nome": "E"}).get_json()
    cli = client_cliente_factory(e["id"])
    r = cli.post(f"/api/empresas/{e['id']}/locais", json={"nome": "Loja"})
    assert r.status_code == 201


def test_cliente_NAO_cria_local_de_outra_empresa(client_loyall, client_cliente_factory):
    e1 = client_loyall.post("/api/empresas/", json={"nome": "EA"}).get_json()
    e2 = client_loyall.post("/api/empresas/", json={"nome": "EB"}).get_json()
    cli = client_cliente_factory(e1["id"])
    r = cli.post(f"/api/empresas/{e2['id']}/locais", json={"nome": "X"})
    assert r.status_code == 403


def test_cliente_pode_editar_fonte_da_sua_empresa(client_loyall, client_cliente_factory):
    e = client_loyall.post("/api/empresas/", json={"nome": "E"}).get_json()
    local = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    f = client_loyall.post(
        f"/api/locais/{local['id']}/fontes",
        json={"conector_tipo": "google", "url": "ChIJ_x"},
    ).get_json()
    cli = client_cliente_factory(e["id"])
    r = cli.put(f"/api/fontes/{f['id']}", json={"ativo": False})
    assert r.status_code == 200


def test_cliente_NAO_edita_fonte_de_outra_empresa(client_loyall, client_cliente_factory):
    e1 = client_loyall.post("/api/empresas/", json={"nome": "EA"}).get_json()
    e2 = client_loyall.post("/api/empresas/", json={"nome": "EB"}).get_json()
    local2 = client_loyall.post(f"/api/empresas/{e2['id']}/locais", json={"nome": "L"}).get_json()
    f2 = client_loyall.post(
        f"/api/locais/{local2['id']}/fontes",
        json={"conector_tipo": "google", "url": "ChIJ_y"},
    ).get_json()
    cli = client_cliente_factory(e1["id"])
    r = cli.put(f"/api/fontes/{f2['id']}", json={"ativo": False})
    assert r.status_code == 403


# ── import-cadastro só admin_loyall ────────────────────────────────────


def test_import_cadastro_cliente_403(client_loyall, client_cliente_factory):
    e = client_loyall.post("/api/empresas/", json={"nome": "E"}).get_json()
    cli = client_cliente_factory(e["id"])
    r = cli.post(
        "/api/empresas/import-cadastro",
        data={},
        content_type="multipart/form-data",
    )
    assert r.status_code == 403
