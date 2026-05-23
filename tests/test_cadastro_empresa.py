"""Testes do CRUD REST de empresas (src/api/empresas.py)."""

from flask.testing import FlaskClient


def test_listar_vazio(client_loyall: FlaskClient) -> None:
    response = client_loyall.get("/api/empresas/")
    assert response.status_code == 200
    assert response.json == []


def test_criar_empresa_minima(client_loyall: FlaskClient) -> None:
    response = client_loyall.post("/api/empresas/", json={"nome": "Acme SA", "setor": "teste"})
    assert response.status_code == 201
    body = response.json
    assert body["id"] is not None
    assert body["nome"] == "Acme SA"
    assert body["setor"] == "teste"
    assert body["razao_social"] is None
    assert body["cnpj"] is None
    assert body["criada_em"] is not None


def test_criar_empresa_completa(client_loyall: FlaskClient) -> None:
    response = client_loyall.post(
        "/api/empresas/",
        json={
            "nome": "Beta LTDA",
            "razao_social": "Beta Comercial LTDA",
            "cnpj": "00.111.222/0001-33",
            "setor": "varejo",
            "branding_json": '{"cor":"#ff0000"}',
        },
    )
    assert response.status_code == 201
    body = response.json
    assert body["razao_social"] == "Beta Comercial LTDA"
    assert body["cnpj"] == "00.111.222/0001-33"
    assert body["branding_json"] == '{"cor":"#ff0000"}'


def test_post_sem_nome_400(client_loyall: FlaskClient) -> None:
    response = client_loyall.post("/api/empresas/", json={"setor": "teste"})
    assert response.status_code == 400
    assert "obrigatório" in response.json["erro"]


def test_post_nome_duplicado_409(client_loyall: FlaskClient) -> None:
    client_loyall.post("/api/empresas/", json={"nome": "Dup SA"})
    response = client_loyall.post("/api/empresas/", json={"nome": "Dup SA"})
    assert response.status_code == 409
    assert "já existe" in response.json["erro"]


def test_get_por_id(client_loyall: FlaskClient) -> None:
    created = client_loyall.post("/api/empresas/", json={"nome": "Get Test"}).json
    response = client_loyall.get(f"/api/empresas/{created['id']}")
    assert response.status_code == 200
    assert response.json["nome"] == "Get Test"


def test_get_inexistente_404(client_loyall: FlaskClient) -> None:
    response = client_loyall.get("/api/empresas/9999")
    assert response.status_code == 404
    assert response.json["erro"] == "Empresa não encontrada"


def test_put_atualiza_campos(client_loyall: FlaskClient) -> None:
    created = client_loyall.post("/api/empresas/", json={"nome": "Old"}).json
    response = client_loyall.put(f"/api/empresas/{created['id']}", json={"setor": "novo-setor"})
    assert response.status_code == 200
    assert response.json["setor"] == "novo-setor"
    assert response.json["nome"] == "Old"  # nome não foi tocado
    # atualizada_em bumped
    assert response.json["atualizada_em"] >= created["atualizada_em"]


def test_put_inexistente_404(client_loyall: FlaskClient) -> None:
    response = client_loyall.put("/api/empresas/9999", json={"setor": "x"})
    assert response.status_code == 404


def test_delete_empresa(client_loyall: FlaskClient) -> None:
    created = client_loyall.post("/api/empresas/", json={"nome": "Del"}).json
    response = client_loyall.delete(f"/api/empresas/{created['id']}")
    assert response.status_code == 200
    assert response.json["removido"] is True
    assert response.json["id"] == created["id"]

    follow_up = client_loyall.get(f"/api/empresas/{created['id']}")
    assert follow_up.status_code == 404


def test_delete_inexistente_404(client_loyall: FlaskClient) -> None:
    response = client_loyall.delete("/api/empresas/9999")
    assert response.status_code == 404


def test_listar_ordenado_por_nome(client_loyall: FlaskClient) -> None:
    for nome in ["Zulu", "Alpha", "Mike"]:
        client_loyall.post("/api/empresas/", json={"nome": nome})
    response = client_loyall.get("/api/empresas/")
    assert response.status_code == 200
    nomes = [e["nome"] for e in response.json]
    assert nomes == ["Alpha", "Mike", "Zulu"]
