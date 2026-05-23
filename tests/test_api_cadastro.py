"""Testes da API de cadastro do Bloco 4 — CP2.

Cobre:
    - empresas: site + observacao (campos novos via migration 012)
    - agrupamentos: CRUD + nested em empresa + UNIQUE(empresa, nome)
    - locais: CRUD + agrupamento_id opcional + filtro ?agrupamento_id
    - fontes: CRUD + criação polimórfica (em local vs em empresa) +
      validação de conector com/sem scraper
    - cascata: SET NULL ao deletar Agrupamento; CASCADE ao deletar
      Local (fontes do local) e Empresa (locais/agrupamentos/fontes)
"""

from __future__ import annotations


# ── Empresa — campos novos site + observacao (migration 012) ─────────────


def test_empresa_create_com_site_e_observacao(client):
    resp = client.post(
        "/api/empresas/",
        json={
            "nome": "BH Airport",
            "setor": "aeroporto",
            "site": "https://www.bh-airport.com.br",
            "observacao": "Concessionária Confins",
        },
    )
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["site"] == "https://www.bh-airport.com.br"
    assert body["observacao"] == "Concessionária Confins"


def test_empresa_update_site(client):
    e = client.post("/api/empresas/", json={"nome": "X"}).get_json()
    resp = client.put(f"/api/empresas/{e['id']}", json={"site": "https://x.com"})
    assert resp.status_code == 200
    assert resp.get_json()["site"] == "https://x.com"


# ── Agrupamentos ─────────────────────────────────────────────────────────


def test_agrupamento_create_e_list_da_empresa(client):
    e = client.post("/api/empresas/", json={"nome": "E1"}).get_json()
    r1 = client.post(
        f"/api/empresas/{e['id']}/agrupamentos",
        json={"nome": "Aeroporto", "descricao": "Operação core"},
    )
    assert r1.status_code == 201
    body = r1.get_json()
    assert body["nome"] == "Aeroporto"
    assert body["ativo"] is True  # default

    r2 = client.post(
        f"/api/empresas/{e['id']}/agrupamentos",
        json={"nome": "Lojas", "ativo": False},
    )
    assert r2.status_code == 201
    assert r2.get_json()["ativo"] is False

    lista = client.get(f"/api/empresas/{e['id']}/agrupamentos").get_json()
    assert len(lista) == 2
    assert sorted(a["nome"] for a in lista) == ["Aeroporto", "Lojas"]


def test_agrupamento_unique_por_empresa(client):
    e = client.post("/api/empresas/", json={"nome": "E2"}).get_json()
    client.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "Geral"})
    dup = client.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "Geral"})
    assert dup.status_code == 409


def test_agrupamento_update_e_delete(client):
    e = client.post("/api/empresas/", json={"nome": "E3"}).get_json()
    a = client.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "AG"}).get_json()
    upd = client.put(f"/api/agrupamentos/{a['id']}", json={"ativo": False})
    assert upd.status_code == 200
    assert upd.get_json()["ativo"] is False
    rem = client.delete(f"/api/agrupamentos/{a['id']}")
    assert rem.status_code == 200
    assert client.get(f"/api/agrupamentos/{a['id']}").status_code == 404


# ── Locais — agrupamento_id opcional + filtro ────────────────────────────


def test_local_create_sem_agrupamento(client):
    e = client.post("/api/empresas/", json={"nome": "E4"}).get_json()
    r = client.post(
        f"/api/empresas/{e['id']}/locais",
        json={"nome": "L sem grupo"},
    )
    assert r.status_code == 201
    assert r.get_json()["agrupamento_id"] is None


def test_local_create_com_agrupamento(client):
    e = client.post("/api/empresas/", json={"nome": "E5"}).get_json()
    a = client.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    r = client.post(
        f"/api/empresas/{e['id']}/locais",
        json={"nome": "L com grupo", "agrupamento_id": a["id"]},
    )
    assert r.status_code == 201
    assert r.get_json()["agrupamento_id"] == a["id"]


def test_local_create_agrupamento_de_outra_empresa_falha(client):
    e1 = client.post("/api/empresas/", json={"nome": "E_A"}).get_json()
    e2 = client.post("/api/empresas/", json={"nome": "E_B"}).get_json()
    ag_outra = client.post(
        f"/api/empresas/{e2['id']}/agrupamentos", json={"nome": "Outro"}
    ).get_json()
    r = client.post(
        f"/api/empresas/{e1['id']}/locais",
        json={"nome": "X", "agrupamento_id": ag_outra["id"]},
    )
    assert r.status_code == 400


def test_local_filter_por_agrupamento_id(client):
    e = client.post("/api/empresas/", json={"nome": "E6"}).get_json()
    a = client.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G1"}).get_json()
    client.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L1", "agrupamento_id": a["id"]})
    client.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L_solto"})

    todos = client.get(f"/api/empresas/{e['id']}/locais").get_json()
    assert len(todos) == 2

    no_agrup = client.get(f"/api/empresas/{e['id']}/locais?agrupamento_id={a['id']}").get_json()
    assert len(no_agrup) == 1
    assert no_agrup[0]["nome"] == "L1"

    sem_agrup = client.get(f"/api/empresas/{e['id']}/locais?agrupamento_id=null").get_json()
    assert len(sem_agrup) == 1
    assert sem_agrup[0]["nome"] == "L_solto"


def test_delete_agrupamento_seta_null_no_local(client):
    e = client.post("/api/empresas/", json={"nome": "E7"}).get_json()
    a = client.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    local = client.post(
        f"/api/empresas/{e['id']}/locais",
        json={"nome": "L", "agrupamento_id": a["id"]},
    ).get_json()
    client.delete(f"/api/agrupamentos/{a['id']}")
    local_apos = client.get(f"/api/locais/{local['id']}").get_json()
    assert local_apos["agrupamento_id"] is None


# ── Fontes — conector com scraper vs catalogado + polimórfico ────────────


def test_fonte_com_scraper_no_local(client):
    e = client.post("/api/empresas/", json={"nome": "E8"}).get_json()
    local = client.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    r = client.post(
        f"/api/locais/{local['id']}/fontes",
        json={
            "conector_tipo": "google",
            "url": "ChIJExamplePlaceId",
            "ativo": True,
        },
    )
    assert r.status_code == 201
    body = r.get_json()
    assert body["entidade_tipo"] == "local"
    assert body["entidade_id"] == local["id"]
    assert body["empresa_id"] == e["id"]
    assert body["ativo"] is True


def test_fonte_catalogada_so_se_inativa(client):
    e = client.post("/api/empresas/", json={"nome": "E9"}).get_json()
    local = client.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    # website com ativo=True → 400
    r_bad = client.post(
        f"/api/locais/{local['id']}/fontes",
        json={"conector_tipo": "website", "url": "https://x.com", "ativo": True},
    )
    assert r_bad.status_code == 400

    # website com ativo=False → 201
    r_ok = client.post(
        f"/api/locais/{local['id']}/fontes",
        json={"conector_tipo": "website", "url": "https://x.com", "ativo": False},
    )
    assert r_ok.status_code == 201


def test_fonte_conector_desconhecido_rejeitado(client):
    e = client.post("/api/empresas/", json={"nome": "E10"}).get_json()
    local = client.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    r = client.post(
        f"/api/locais/{local['id']}/fontes",
        json={"conector_tipo": "xyz_invalido", "url": "https://x.com"},
    )
    assert r.status_code == 400
    assert "desconhecido" in r.get_json()["erro"]


def test_fonte_direta_na_empresa(client):
    e = client.post("/api/empresas/", json={"nome": "E11"}).get_json()
    r = client.post(
        f"/api/empresas/{e['id']}/fontes",
        json={"conector_tipo": "google_news", "url": "BH Airport"},
    )
    assert r.status_code == 201
    body = r.get_json()
    assert body["entidade_tipo"] == "empresa"
    assert body["entidade_id"] == e["id"]


def test_fonte_listar_da_empresa_inclui_local_e_direta(client):
    e = client.post("/api/empresas/", json={"nome": "E12"}).get_json()
    local = client.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    client.post(
        f"/api/locais/{local['id']}/fontes",
        json={"conector_tipo": "google", "url": "ChIJ_1"},
    )
    client.post(
        f"/api/empresas/{e['id']}/fontes",
        json={"conector_tipo": "google_news", "url": "Q"},
    )
    fontes = client.get(f"/api/empresas/{e['id']}/fontes").get_json()
    assert len(fontes) == 2
    tipos = sorted(f["entidade_tipo"] for f in fontes)
    assert tipos == ["empresa", "local"]


def test_fonte_update_ativo(client):
    e = client.post("/api/empresas/", json={"nome": "E13"}).get_json()
    local = client.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    f = client.post(
        f"/api/locais/{local['id']}/fontes",
        json={"conector_tipo": "google", "url": "ChIJ_2"},
    ).get_json()
    upd = client.put(f"/api/fontes/{f['id']}", json={"ativo": False})
    assert upd.status_code == 200
    assert upd.get_json()["ativo"] is False


def test_delete_local_cascateia_fontes_dele(client):
    e = client.post("/api/empresas/", json={"nome": "E14"}).get_json()
    local = client.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    f = client.post(
        f"/api/locais/{local['id']}/fontes",
        json={"conector_tipo": "google", "url": "ChIJ_3"},
    ).get_json()
    client.delete(f"/api/locais/{local['id']}")
    assert client.get(f"/api/fontes/{f['id']}").status_code == 404


def test_delete_empresa_cascateia_tudo(client):
    e = client.post("/api/empresas/", json={"nome": "E15"}).get_json()
    a = client.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    local = client.post(
        f"/api/empresas/{e['id']}/locais",
        json={"nome": "L", "agrupamento_id": a["id"]},
    ).get_json()
    f = client.post(
        f"/api/locais/{local['id']}/fontes",
        json={"conector_tipo": "google", "url": "ChIJ_4"},
    ).get_json()
    client.delete(f"/api/empresas/{e['id']}")
    assert client.get(f"/api/agrupamentos/{a['id']}").status_code == 404
    assert client.get(f"/api/locais/{local['id']}").status_code == 404
    assert client.get(f"/api/fontes/{f['id']}").status_code == 404
