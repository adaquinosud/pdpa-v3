"""Testes dos endpoints do Painel Executivo (Bloco 5 CP-1)."""

from __future__ import annotations

from datetime import datetime, timedelta

from src.models.verbatim import Verbatim


def _criar_verbatim(
    db_session,
    empresa_id,
    fonte_id,
    local_id=None,
    texto="t",
    subpilar="Pa1",
    tipo="promotor",
    data_dias_atras=10,
):
    v = Verbatim(
        empresa_id=empresa_id,
        fonte_id=fonte_id,
        local_id=local_id,
        texto=texto,
        data_criacao_original=datetime.utcnow() - timedelta(days=data_dias_atras),
        hash_dedup=f"hash-{texto}-{datetime.utcnow().timestamp()}",
        subpilar=subpilar,
        tipo=tipo,
    )
    db_session.add(v)
    db_session.commit()
    return v


def _empresa_estrutura(client_loyall, suffix=None):
    import uuid

    sfx = suffix or uuid.uuid4().hex[:6]
    e = client_loyall.post("/api/empresas/", json={"nome": f"EPnl-{sfx}"}).get_json()
    a = client_loyall.post(
        f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "GPnl"}
    ).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais",
        json={"nome": "LPnl", "agrupamento_id": a["id"]},
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ_p_{sfx}"},
    ).get_json()
    return {"e": e, "a": a, "loc": loc, "f": f}


# ── Nível 1: 4 pilares ─────────────────────────────────────────────────


def test_painel_nivel1_vazio(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "EPnlVazio"}).get_json()
    r = client_loyall.get(f"/api/empresas/{e['id']}/painel/nivel1")
    assert r.status_code == 200
    body = r.get_json()
    assert body["total_verbatins"] == 0
    assert len(body["pilares"]) == 4
    assert [p["pilar"] for p in body["pilares"]] == ["P", "D", "Pa", "A"]
    for p in body["pilares"]:
        assert p["total"] == 0


def test_painel_nivel1_agrega_por_pilar(client_loyall, db_session):
    ctx = _empresa_estrutura(client_loyall)
    # 2 Pa1 promotor, 1 D2 detrator, 1 P3 conversivel, 1 sem_lastro inativo
    for _ in range(2):
        _criar_verbatim(
            db_session,
            ctx["e"]["id"],
            ctx["f"]["id"],
            ctx["loc"]["id"],
            texto=f"t-{_}-a",
            subpilar="Pa1",
            tipo="promotor",
        )
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="t-d2",
        subpilar="D2",
        tipo="detrator",
    )
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="t-p3",
        subpilar="P3",
        tipo="conversivel",
    )
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="t-sl",
        subpilar="sem_lastro",
        tipo="inativo",
    )
    r = client_loyall.get(f"/api/empresas/{ctx['e']['id']}/painel/nivel1")
    body = r.get_json()
    assert body["total_verbatins"] == 5

    pilar = {p["pilar"]: p for p in body["pilares"]}
    assert pilar["Pa"]["total"] == 2
    assert pilar["Pa"]["promotor"] == 2
    assert pilar["D"]["total"] == 1
    assert pilar["D"]["detrator"] == 1
    assert pilar["P"]["total"] == 1
    assert pilar["P"]["conversivel"] == 1
    assert pilar["A"]["total"] == 0
    assert body["outros"]["sem_lastro"] == 1


def test_painel_nivel1_filtro_periodo(client_loyall, db_session):
    ctx = _empresa_estrutura(client_loyall)
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="recente",
        data_dias_atras=3,
    )
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="velho",
        data_dias_atras=400,
    )
    r = client_loyall.get(f"/api/empresas/{ctx['e']['id']}/painel/nivel1?periodo=7d")
    assert r.get_json()["total_verbatins"] == 1
    r = client_loyall.get(f"/api/empresas/{ctx['e']['id']}/painel/nivel1?periodo=12m")
    assert r.get_json()["total_verbatins"] == 1
    r = client_loyall.get(f"/api/empresas/{ctx['e']['id']}/painel/nivel1")
    assert r.get_json()["total_verbatins"] == 2


def test_painel_nivel1_filtro_agrupamento(client_loyall, db_session):
    ctx = _empresa_estrutura(client_loyall)
    a2 = client_loyall.post(
        f"/api/empresas/{ctx['e']['id']}/agrupamentos", json={"nome": "G2"}
    ).get_json()
    loc2 = client_loyall.post(
        f"/api/empresas/{ctx['e']['id']}/locais",
        json={"nome": "L2", "agrupamento_id": a2["id"]},
    ).get_json()
    f2 = client_loyall.post(
        f"/api/locais/{loc2['id']}/fontes",
        json={"conector_tipo": "google", "url": "ChIJ_g2"},
    ).get_json()
    _criar_verbatim(db_session, ctx["e"]["id"], ctx["f"]["id"], ctx["loc"]["id"], texto="g1")
    _criar_verbatim(db_session, ctx["e"]["id"], f2["id"], loc2["id"], texto="g2")
    r = client_loyall.get(
        f"/api/empresas/{ctx['e']['id']}/painel/nivel1?agrupamento_id={ctx['a']['id']}"
    )
    assert r.get_json()["total_verbatins"] == 1


def test_painel_nivel1_periodo_invalido_400(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "EPnlInv"}).get_json()
    r = client_loyall.get(f"/api/empresas/{e['id']}/painel/nivel1?periodo=2y")
    assert r.status_code == 400


# ── Nível 2: matriz subpilar × tipo ─────────────────────────────────────


def test_painel_nivel2_matriz_completa(client_loyall, db_session):
    ctx = _empresa_estrutura(client_loyall)
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="t1",
        subpilar="Pa1",
        tipo="promotor",
    )
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="t2",
        subpilar="Pa1",
        tipo="detrator",
    )
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="t3",
        subpilar="D1",
        tipo="conversivel",
    )
    r = client_loyall.get(f"/api/empresas/{ctx['e']['id']}/painel/nivel2")
    body = r.get_json()
    assert body["total_verbatins"] == 3
    assert len(body["matriz"]) == 12  # P1-3, D1-3, Pa1-3, A1-3
    pa1 = next(c for c in body["matriz"] if c["subpilar"] == "Pa1")
    assert pa1["promotor"] == 1
    assert pa1["detrator"] == 1
    assert pa1["total"] == 2
    d1 = next(c for c in body["matriz"] if c["subpilar"] == "D1")
    assert d1["conversivel"] == 1
    assert d1["total"] == 1
    a1 = next(c for c in body["matriz"] if c["subpilar"] == "A1")
    assert a1["total"] == 0  # zero é coberto


def test_painel_nivel2_inclui_sem_lastro_separado(client_loyall, db_session):
    ctx = _empresa_estrutura(client_loyall)
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="sl",
        subpilar="sem_lastro",
        tipo="inativo",
    )
    r = client_loyall.get(f"/api/empresas/{ctx['e']['id']}/painel/nivel2")
    body = r.get_json()
    assert body["sem_lastro"]["total"] == 1
    assert body["sem_lastro"]["inativo"] == 1
    # Não polui a matriz principal
    assert all(c["total"] == 0 for c in body["matriz"])


def test_painel_nivel2_filtro_data_de_ate(client_loyall, db_session):
    ctx = _empresa_estrutura(client_loyall)
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="t",
        subpilar="Pa1",
        tipo="promotor",
        data_dias_atras=5,
    )
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="t2",
        subpilar="Pa1",
        tipo="promotor",
        data_dias_atras=30,
    )
    de = (datetime.utcnow() - timedelta(days=10)).date().isoformat()
    r = client_loyall.get(f"/api/empresas/{ctx['e']['id']}/painel/nivel2?data_de={de}")
    assert r.get_json()["total_verbatins"] == 1


def test_painel_cliente_de_outra_empresa_403(client_loyall, client_cliente_factory):
    e_a = client_loyall.post("/api/empresas/", json={"nome": "EPnlA"}).get_json()
    e_b = client_loyall.post("/api/empresas/", json={"nome": "EPnlB"}).get_json()
    cli = client_cliente_factory(e_a["id"])
    r1 = cli.get(f"/api/empresas/{e_b['id']}/painel/nivel1")
    assert r1.status_code == 403
    r2 = cli.get(f"/api/empresas/{e_b['id']}/painel/nivel2")
    assert r2.status_code == 403


def test_painel_cliente_propria_empresa_200(client_loyall, client_cliente_factory):
    e = client_loyall.post("/api/empresas/", json={"nome": "EPnlOk"}).get_json()
    cli = client_cliente_factory(e["id"])
    assert cli.get(f"/api/empresas/{e['id']}/painel/nivel1").status_code == 200
    assert cli.get(f"/api/empresas/{e['id']}/painel/nivel2").status_code == 200


# ── UI: página /empresas/<id>/painel ──────────────────────────────────


def test_ui_painel_renderiza_visao_geral_e_detalhamento(client_loyall, db_session):
    ctx = _empresa_estrutura(client_loyall)
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="elogio",
        subpilar="Pa1",
        tipo="promotor",
    )
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="reclamacao",
        subpilar="D2",
        tipo="detrator",
    )
    r = client_loyall.get(f"/empresas/{ctx['e']['id']}/painel")
    assert r.status_code == 200
    html = r.data.decode()
    assert "Visão Geral" in html
    assert "Detalhamento por Subpilar" in html
    # Pilares P/D/Pa/A presentes
    for pilar in ["Precisão", "Disponibilidade", "Parceria", "Aconselhamento"]:
        assert pilar in html
    # Botão exportar
    assert "Exportar Excel" in html


def test_ui_painel_403_cliente_de_outra_empresa(client_loyall, client_cliente_factory):
    e_a = client_loyall.post("/api/empresas/", json={"nome": "EPnlUiA"}).get_json()
    e_b = client_loyall.post("/api/empresas/", json={"nome": "EPnlUiB"}).get_json()
    cli = client_cliente_factory(e_a["id"])
    r = cli.get(f"/empresas/{e_b['id']}/painel")
    assert r.status_code == 403


# ── Exportar XLSX ─────────────────────────────────────────────────────


def test_exportar_painel_xlsx_basico(client_loyall, db_session):
    ctx = _empresa_estrutura(client_loyall)
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="t1",
        subpilar="Pa1",
        tipo="promotor",
    )
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="t2",
        subpilar="D2",
        tipo="detrator",
    )
    r = client_loyall.get(f"/api/empresas/{ctx['e']['id']}/painel/exportar.xlsx")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers.get("Content-Type", "")
    assert r.data[:2] == b"PK"

    from io import BytesIO
    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(r.data))
    assert "Visão Geral" in wb.sheetnames
    assert "Detalhamento por Subpilar" in wb.sheetnames

    ws1 = wb["Visão Geral"]
    rows1 = list(ws1.iter_rows(values_only=True))
    # Confere headers da tabela de pilares
    header_row = next(r for r in rows1 if r and r[0] == "Pilar")
    assert header_row[0:3] == ("Pilar", "Nome", "Total")
    # Pa deve aparecer com total=1
    pa_row = next(r for r in rows1 if r and r[0] == "Pa")
    assert pa_row[2] == 1
    assert pa_row[3] == 1  # promotor

    ws2 = wb["Detalhamento por Subpilar"]
    rows2 = list(ws2.iter_rows(values_only=True))
    pa1_row = next(r for r in rows2 if r and r[1] == "Pa1")
    assert pa1_row[2] == 1  # promotor
    assert pa1_row[6] == 1  # total
    d2_row = next(r for r in rows2 if r and r[1] == "D2")
    assert d2_row[4] == 1  # detrator


def test_exportar_painel_xlsx_aplica_filtros(client_loyall, db_session):
    ctx = _empresa_estrutura(client_loyall)
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="recente",
        subpilar="Pa1",
        tipo="promotor",
        data_dias_atras=3,
    )
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="velho",
        subpilar="D2",
        tipo="detrator",
        data_dias_atras=400,
    )
    r = client_loyall.get(f"/api/empresas/{ctx['e']['id']}/painel/exportar.xlsx?periodo=7d")
    assert r.status_code == 200
    from io import BytesIO
    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(r.data))
    ws1 = wb["Visão Geral"]
    rows1 = list(ws1.iter_rows(values_only=True))
    pa_row = next(r for r in rows1 if r and r[0] == "Pa")
    assert pa_row[2] == 1
    d_row = next(r for r in rows1 if r and r[0] == "D")
    assert d_row[2] == 0  # filtrado pelo periodo


def test_exportar_painel_xlsx_cliente_outra_empresa_403(client_loyall, client_cliente_factory):
    e_a = client_loyall.post("/api/empresas/", json={"nome": "EPnlXlsxA"}).get_json()
    e_b = client_loyall.post("/api/empresas/", json={"nome": "EPnlXlsxB"}).get_json()
    cli = client_cliente_factory(e_a["id"])
    r = cli.get(f"/api/empresas/{e_b['id']}/painel/exportar.xlsx")
    assert r.status_code == 403
