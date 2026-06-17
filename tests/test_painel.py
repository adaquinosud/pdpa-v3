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


def test_painel_nivel1_periodos_novos(client_loyall, db_session):
    """Manual Cap. 4 + pedido user: 6m e 15m disponíveis."""
    ctx = _empresa_estrutura(client_loyall)
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="t1",
        data_dias_atras=100,
    )
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="t2",
        data_dias_atras=300,
    )
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="t3",
        data_dias_atras=500,
    )
    r6m = client_loyall.get(f"/api/empresas/{ctx['e']['id']}/painel/nivel1?periodo=6m")
    assert r6m.get_json()["total_verbatins"] == 1  # só os 100 dias
    r15m = client_loyall.get(f"/api/empresas/{ctx['e']['id']}/painel/nivel1?periodo=15m")
    assert r15m.get_json()["total_verbatins"] == 2  # 100 e 300 dias


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
    # Manual Cap. 2: Pa1 = Empatia Comercial
    assert pa1["nome"] == "Empatia Comercial"
    # ratio = 1 promotor / 1 detrator = 1.0 → faixa "atencao"
    assert pa1["ratio"] == 1.0
    assert pa1["faixa"] == "atencao"
    d1 = next(c for c in body["matriz"] if c["subpilar"] == "D1")
    assert d1["conversivel"] == 1
    assert d1["total"] == 1
    assert d1["nome"] == "Acessibilidade"
    a1 = next(c for c in body["matriz"] if c["subpilar"] == "A1")
    assert a1["total"] == 0  # zero é coberto
    assert a1["nome"] == "Exemplo"


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


def test_painel_nivel2_filtro_periodo_7d(client_loyall, db_session):
    """Manual Cap. 4 + hotfix: data_de/data_ate removidos, só periodo."""
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
    r = client_loyall.get(f"/api/empresas/{ctx['e']['id']}/painel/nivel2?periodo=7d")
    assert r.get_json()["total_verbatins"] == 1


# ── Ratio P/D (Manual Cap. 4) ─────────────────────────────────────────


def test_calcular_ratio_zero_e_zero():
    from src.api.painel import calcular_ratio

    assert calcular_ratio(0, 0) == 0.0


def test_calcular_ratio_zero_detratores_cap_999():
    from src.api.painel import calcular_ratio

    # Saturação positiva — Manual Cap. 4
    assert calcular_ratio(10, 0) == 9.99
    assert calcular_ratio(1, 0) == 9.99


def test_calcular_ratio_zero_promotores_zero():
    from src.api.painel import calcular_ratio

    # Saturação negativa — Manual Cap. 4
    assert calcular_ratio(0, 10) == 0.0


def test_calcular_ratio_normal():
    from src.api.painel import calcular_ratio

    assert calcular_ratio(2, 1) == 2.0
    assert calcular_ratio(1, 2) == 0.5
    assert calcular_ratio(3, 1) == 3.0


def test_calcular_ratio_cap_em_caso_muito_alto():
    from src.api.painel import calcular_ratio

    # 1000 promotores, 1 detrator → 1000.0 mas capeado em 9.99
    assert calcular_ratio(1000, 1) == 9.99


def test_ratio_em_palavras_casos_do_spec():
    from src.api.painel import ratio_em_palavras

    # cap superior → sem detratores; cap inferior/zero → nenhum promotor
    assert ratio_em_palavras(9.99) == "sem detratores"
    assert ratio_em_palavras(0.0) == "nenhum promotor"
    # ratio ≥ 1: "X promotores para cada detrator" (singular quando X=1)
    assert ratio_em_palavras(6.0) == "6 promotores para cada detrator"
    assert ratio_em_palavras(2.0) == "2 promotores para cada detrator"
    assert ratio_em_palavras(1.0) == "1 promotor para cada detrator"
    # ratio < 1: "1 promotor para cada X detratores"
    assert ratio_em_palavras(0.5) == "1 promotor para cada 2 detratores"
    assert ratio_em_palavras(0.125) == "1 promotor para cada 8 detratores"


def test_ratio_em_palavras_decimal_virgula_ptbr():
    from src.api.painel import ratio_em_palavras

    assert ratio_em_palavras(1.5) == "1,5 promotores para cada detrator"
    assert ratio_em_palavras(3.33) == "3,3 promotores para cada detrator"  # 1 casa
    assert ratio_em_palavras(0.9) == "1 promotor para cada 1,1 detratores"


def test_faixa_ratio_5_niveis():
    from src.api.painel import faixa_ratio

    assert faixa_ratio(0.0) == "critico"
    assert faixa_ratio(0.49) == "critico"
    assert faixa_ratio(0.5) == "fraco"
    assert faixa_ratio(0.99) == "fraco"
    assert faixa_ratio(1.0) == "atencao"
    assert faixa_ratio(1.99) == "atencao"
    assert faixa_ratio(2.0) == "bom"
    assert faixa_ratio(4.99) == "bom"
    assert faixa_ratio(5.0) == "excelente"
    assert faixa_ratio(9.99) == "excelente"


def test_painel_nivel1_inclui_ratio_e_faixa(client_loyall, db_session):
    ctx = _empresa_estrutura(client_loyall)
    # 4 promotor Pa1 + 1 detrator Pa1 → ratio Pa = 4.0 = "bom"
    for i in range(4):
        _criar_verbatim(
            db_session,
            ctx["e"]["id"],
            ctx["f"]["id"],
            ctx["loc"]["id"],
            texto=f"prom-{i}",
            subpilar="Pa1",
            tipo="promotor",
        )
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="det",
        subpilar="Pa1",
        tipo="detrator",
    )
    r = client_loyall.get(f"/api/empresas/{ctx['e']['id']}/painel/nivel1")
    body = r.get_json()
    pa = next(p for p in body["pilares"] if p["pilar"] == "Pa")
    assert pa["ratio"] == 4.0
    assert pa["faixa"] == "bom"
    # Pilar sem dados → ratio 0.0, faixa "critico"
    p = next(p for p in body["pilares"] if p["pilar"] == "P")
    assert p["ratio"] == 0.0
    assert p["faixa"] == "critico"


def test_ui_painel_link_sem_classificacao_clicavel(client_loyall, db_session):
    """B5 ext. CP-2: ao ter verbatins sem classificação, o painel
    renderiza link clicável para /verbatins?sem_classificacao=1.
    """
    ctx = _empresa_estrutura(client_loyall)
    # 1 verbatim sem_lastro e 1 sem classificação (subpilar NULL)
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="sl",
        subpilar="sem_lastro",
        tipo="inativo",
    )
    v_nc = Verbatim(
        empresa_id=ctx["e"]["id"],
        fonte_id=ctx["f"]["id"],
        local_id=ctx["loc"]["id"],
        texto="nc",
        data_criacao_original=datetime.utcnow(),
        hash_dedup="hash-nc-painel",
        subpilar=None,
        tipo=None,
    )
    db_session.add(v_nc)
    db_session.commit()

    r = client_loyall.get(f"/empresas/{ctx['e']['id']}/painel")
    html = r.data.decode()
    # Link no resumo "Fora dos 4 pilares"
    assert "sem_classificacao=1" in html
    # Linha da matriz e resumo ambas devem ter o link
    occurrences = html.count("sem_classificacao=1")
    assert occurrences >= 2, f"esperava >=2 links, obtido {occurrences}"
    # Link sem_lastro continua funcionando
    assert "subpilar=sem_lastro" in html


# ── B5 ext. CP-3: Índice Geral / Previsibilidade / Concentração ──────


def test_calcular_indice_geral_sem_volume():
    from src.api.painel import calcular_indice_geral

    assert calcular_indice_geral([]) == 0.0
    assert calcular_indice_geral([{"total": 0, "ratio": 5.0, "subpilar": "P1"}]) == 0.0


def test_calcular_indice_geral_todos_saturados_da_10():
    """Hotfix opção B: todos pilares saturados (>= 5) → Índice 10."""
    from src.api.painel import calcular_indice_geral

    matriz = [
        {"total": 100, "ratio": 9.99, "subpilar": "P1", "promotor": 100, "detrator": 0},
        {"total": 100, "ratio": 9.99, "subpilar": "D1", "promotor": 100, "detrator": 0},
        {"total": 100, "ratio": 9.99, "subpilar": "Pa1", "promotor": 100, "detrator": 0},
        {"total": 100, "ratio": 9.99, "subpilar": "A1", "promotor": 100, "detrator": 0},
    ]
    pilares = [
        {"pilar": p, "ratio": 9.99, "total": 100, "promotor": 100, "detrator": 0}
        for p in ["P", "D", "Pa", "A"]
    ]
    assert calcular_indice_geral(matriz, pilares=pilares) == 10.0


def test_calcular_indice_geral_pilar_critico_puxa_pra_baixo():
    """Hotfix opção B: pilar crítico domina, mesmo com média ponderada saturada."""
    from src.api.painel import calcular_indice_geral

    # Pa saturado em 9.99 com 2000 verbatins + P crítico em 0.4 com 100 verbatins.
    # Antes (CP-3 ingênuo): ratio_medio_ponderado ≈ 9.54 × 2 = 19 → cap 10.
    # Agora (opção B): min(0.4, 9.54) × 2 = 0.80.
    matriz = [
        {"total": 100, "ratio": 0.4, "subpilar": "P1", "promotor": 2, "detrator": 5},
        {"total": 2000, "ratio": 9.99, "subpilar": "Pa1", "promotor": 2000, "detrator": 0},
    ]
    pilares = [
        {"pilar": "P", "ratio": 0.4, "total": 100, "promotor": 2, "detrator": 5},
        {"pilar": "D", "ratio": 0.0, "total": 0, "promotor": 0, "detrator": 0},
        {"pilar": "Pa", "ratio": 9.99, "total": 2000, "promotor": 2000, "detrator": 0},
        {"pilar": "A", "ratio": 0.0, "total": 0, "promotor": 0, "detrator": 0},
    ]
    indice = calcular_indice_geral(matriz, pilares=pilares)
    # min(0.4, ratio_medio_ponderado) × 2 = 0.4 × 2 = 0.8
    assert indice == 0.8


def test_calcular_indice_geral_todos_criticos_resulta_baixo():
    """Edge: todos pilares com ratio 0.3 → Índice ~0.6."""
    from src.api.painel import calcular_indice_geral

    matriz = [
        {"total": 10, "ratio": 0.3, "subpilar": "P1", "promotor": 1, "detrator": 3},
        {"total": 10, "ratio": 0.3, "subpilar": "D1", "promotor": 1, "detrator": 3},
        {"total": 10, "ratio": 0.3, "subpilar": "Pa1", "promotor": 1, "detrator": 3},
        {"total": 10, "ratio": 0.3, "subpilar": "A1", "promotor": 1, "detrator": 3},
    ]
    pilares = [
        {"pilar": p, "ratio": 0.3, "total": 10, "promotor": 1, "detrator": 3}
        for p in ["P", "D", "Pa", "A"]
    ]
    assert calcular_indice_geral(matriz, pilares=pilares) == 0.6


def test_calcular_indice_geral_sem_pilares_arg_deriva_da_matriz():
    """Fallback: quando pilares não é passado, agrega da matriz."""
    from src.api.painel import calcular_indice_geral

    matriz = [
        {"subpilar": "P1", "total": 10, "ratio": 0.5, "promotor": 1, "detrator": 2},
        {"subpilar": "Pa1", "total": 10, "ratio": 9.99, "promotor": 10, "detrator": 0},
    ]
    # min(min(P=0.5, Pa=9.99), ratio_medio) × 2 = 0.5 × 2 = 1.0
    indice = calcular_indice_geral(matriz)
    assert indice == 1.0


def test_faixa_indice_geral():
    from src.api.painel import faixa_indice_geral

    assert faixa_indice_geral(7.5) == "saudavel"
    assert faixa_indice_geral(7.0) == "saudavel"
    assert faixa_indice_geral(6.0) == "atencao"
    assert faixa_indice_geral(5.0) == "atencao"
    assert faixa_indice_geral(4.99) == "critico"
    assert faixa_indice_geral(0.0) == "critico"


def test_calcular_previsibilidade_empresa_vazia(client_loyall, db_session):
    """Edge: empresa sem verbatins → 0 (sem locais/meses pra calcular)."""
    from src.api.painel import calcular_previsibilidade
    from src.utils.db import db_session as get_session

    e = client_loyall.post("/api/empresas/", json={"nome": "EPrev0"}).get_json()
    with get_session() as s:
        prev = calcular_previsibilidade(e["id"], s, {}, pct_conversiveis=0.0)
    # Sem locais (var=0) + sem meses (vol_temporal=0) + 0% conv =
    # (1*0.4 + 1*0.3 + 0*0.3) * 100 = 70
    assert prev == 70.0


def test_calcular_previsibilidade_1_local_so(client_loyall, db_session):
    """Edge: 1 local, vários meses → var_locais=0 (precisa >= 2 locais)."""
    from src.api.painel import calcular_previsibilidade
    from src.utils.db import db_session as get_session

    ctx = _empresa_estrutura(client_loyall)
    # 5 verbatins do mesmo local, mesmo mês
    for i in range(5):
        _criar_verbatim(
            db_session,
            ctx["e"]["id"],
            ctx["f"]["id"],
            ctx["loc"]["id"],
            texto=f"v{i}",
            subpilar="Pa1",
            tipo="promotor",
            data_dias_atras=10,
        )
    with get_session() as s:
        prev = calcular_previsibilidade(ctx["e"]["id"], s, {}, pct_conversiveis=0.0)
    # 1 local (< 2) → var_locais=0; 1 mês (< 3) → vol_temporal=0; 0 conv
    # → (0.4 + 0.3 + 0) * 100 = 70
    assert prev == 70.0


def test_calcular_previsibilidade_lojas_uniformes_alta(client_loyall, db_session):
    """5 lojas com mesmo ratio → var_locais=0 → previsibilidade alta."""
    from src.api.painel import calcular_previsibilidade
    from src.utils.db import db_session as get_session

    e = client_loyall.post("/api/empresas/", json={"nome": "EPrevU"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    for i in range(5):
        loc = client_loyall.post(
            f"/api/empresas/{e['id']}/locais",
            json={"nome": f"L{i}", "agrupamento_id": a["id"]},
        ).get_json()
        f_ = client_loyall.post(
            f"/api/locais/{loc['id']}/fontes",
            json={"conector_tipo": "google", "url": f"ChIJ_pv_{i}"},
        ).get_json()
        # 5 verbatins por loja, todos Pa1/promotor (ratio=9.99 em cada)
        for j in range(5):
            _criar_verbatim(
                db_session,
                e["id"],
                f_["id"],
                loc["id"],
                texto=f"l{i}-v{j}",
                subpilar="Pa1",
                tipo="promotor",
            )
    with get_session() as s:
        prev = calcular_previsibilidade(e["id"], s, {}, pct_conversiveis=0.0)
    # 5 lojas com ratio idêntico → var_locais=0 → contribui 100% no fator 0.4
    # 0 conv → 0 no fator 0.3
    # Score >= 70 (idealmente 100 mas meses pode ser 0 se tudo no mesmo mês)
    assert prev >= 70.0


def test_calcular_previsibilidade_lojas_dispersas_reduz_score(client_loyall, db_session):
    """Lojas com ratios muito diferentes → var_locais alto → score reduz."""
    from src.api.painel import calcular_previsibilidade
    from src.utils.db import db_session as get_session

    e = client_loyall.post("/api/empresas/", json={"nome": "EPrevD"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    # 5 lojas: ratios variando muito (1 promotor vs 5 detratores em alguns)
    for i in range(5):
        loc = client_loyall.post(
            f"/api/empresas/{e['id']}/locais",
            json={"nome": f"L{i}", "agrupamento_id": a["id"]},
        ).get_json()
        f_ = client_loyall.post(
            f"/api/locais/{loc['id']}/fontes",
            json={"conector_tipo": "google", "url": f"ChIJ_pvd_{i}"},
        ).get_json()
        # locais pares: 5 promotor; ímpares: 5 detrator → ratios 9.99 vs 0
        tipo = "promotor" if i % 2 == 0 else "detrator"
        for j in range(5):
            _criar_verbatim(
                db_session,
                e["id"],
                f_["id"],
                loc["id"],
                texto=f"l{i}-v{j}",
                subpilar="Pa1",
                tipo=tipo,
            )
    with get_session() as s:
        prev_dispersa = calcular_previsibilidade(e["id"], s, {}, pct_conversiveis=0.0)
    # CV alto → var_locais ~1.0 → fator (1-1)*0.4 = 0
    # Score deve cair em relação ao teste uniforme
    assert prev_dispersa < 70.0


def test_painel_nivel1_inclui_indice_previsibilidade_concentracao(client_loyall, db_session):
    ctx = _empresa_estrutura(client_loyall)
    # 10 verbatins Pa1 promotor + 5 D2 detrator
    for i in range(10):
        _criar_verbatim(
            db_session,
            ctx["e"]["id"],
            ctx["f"]["id"],
            ctx["loc"]["id"],
            texto=f"p{i}",
            subpilar="Pa1",
            tipo="promotor",
        )
    for i in range(5):
        _criar_verbatim(
            db_session,
            ctx["e"]["id"],
            ctx["f"]["id"],
            ctx["loc"]["id"],
            texto=f"d{i}",
            subpilar="D2",
            tipo="detrator",
        )
    body = client_loyall.get(f"/api/empresas/{ctx['e']['id']}/painel/nivel1").get_json()
    assert "indice_geral" in body
    assert "previsibilidade" in body
    assert "concentracao_detratores" in body
    assert "indice_geral_faixa" in body
    # Concentração precisa ≥5 locais; só 1 local aqui → None
    assert body["concentracao_detratores"] is None
    assert body["concentracao_faixa"] == "indisponivel"


def test_painel_nivel1_concentracao_calcula_com_5_locais_volume_min(client_loyall, db_session):
    """Concentração: ≥5 locais com volume MÍNIMO de 5 verbatins cada (hotfix)."""
    e = client_loyall.post("/api/empresas/", json={"nome": "EConc"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "AC"}).get_json()
    # 5 locais, cada um com 5 verbatins (4 promotor + 1 detrator) → ratio 4.0
    # Necessário >= 5 verbatins/local após hotfix.
    for i in range(5):
        loc = client_loyall.post(
            f"/api/empresas/{e['id']}/locais",
            json={"nome": f"L{i}", "agrupamento_id": a["id"]},
        ).get_json()
        f_ = client_loyall.post(
            f"/api/locais/{loc['id']}/fontes",
            json={"conector_tipo": "google", "url": f"ChIJ_c_{i}"},
        ).get_json()
        for j in range(4):
            _criar_verbatim(
                db_session,
                e["id"],
                f_["id"],
                loc["id"],
                texto=f"p{i}-{j}",
                subpilar="Pa1",
                tipo="promotor",
            )
        _criar_verbatim(
            db_session,
            e["id"],
            f_["id"],
            loc["id"],
            texto=f"d{i}",
            subpilar="Pa1",
            tipo="detrator",
        )
    body = client_loyall.get(f"/api/empresas/{e['id']}/painel/nivel1").get_json()
    # 5 detratores total, 5 nas piores 5 lojas (todas iguais) → 100%
    assert body["concentracao_detratores"] == 100.0


def test_painel_nivel1_concentracao_locais_com_pouco_volume_ignorados(client_loyall, db_session):
    """Hotfix: locais com < 5 verbatins não entram no cálculo de concentração."""
    e = client_loyall.post("/api/empresas/", json={"nome": "EConcLow"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "AC"}).get_json()
    # 4 locais com 1 verbatim cada (volume insuficiente) + 1 local com 5 verbatins
    for i in range(5):
        loc = client_loyall.post(
            f"/api/empresas/{e['id']}/locais",
            json={"nome": f"L{i}", "agrupamento_id": a["id"]},
        ).get_json()
        f_ = client_loyall.post(
            f"/api/locais/{loc['id']}/fontes",
            json={"conector_tipo": "google", "url": f"ChIJ_cl_{i}"},
        ).get_json()
        if i == 0:
            # 5 verbatins neste local
            for j in range(5):
                _criar_verbatim(
                    db_session,
                    e["id"],
                    f_["id"],
                    loc["id"],
                    texto=f"l0-v{j}",
                    subpilar="Pa1",
                    tipo="detrator",
                )
        else:
            # apenas 1 — abaixo do mínimo
            _criar_verbatim(
                db_session,
                e["id"],
                f_["id"],
                loc["id"],
                texto=f"l{i}-v0",
                subpilar="Pa1",
                tipo="promotor",
            )
    body = client_loyall.get(f"/api/empresas/{e['id']}/painel/nivel1").get_json()
    # Apenas 1 local com volume suficiente → < 5 com volume → None.
    assert body["concentracao_detratores"] is None


def test_ui_painel_3_cards_metricas_consolidadas(client_loyall, db_session):
    """B5 ext. CP-3: 3 cards no topo do painel (Índice/Previsibilidade/Concentração)."""
    ctx = _empresa_estrutura(client_loyall)
    _criar_verbatim(
        db_session,
        ctx["e"]["id"],
        ctx["f"]["id"],
        ctx["loc"]["id"],
        texto="p",
        subpilar="Pa1",
        tipo="promotor",
    )
    r = client_loyall.get(f"/empresas/{ctx['e']['id']}/painel")
    html = r.data.decode()
    assert "Índice Geral" in html
    assert "Previsibilidade" in html
    assert "Concentração (top-5)" in html  # relabel CP-LG-3 (opção i)
    assert "Desigualdade (Gini)" in html  # card Gini adicionado no CP-LG-3


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


# ── descrever_escopo (hotfix UI: textos contextuais) ─────────────────


def test_descrever_escopo_vazio():
    from src.api.painel import descrever_escopo

    assert descrever_escopo("BH Airport") == "geral da BH Airport"


def test_descrever_escopo_apenas_agrupamento():
    from src.api.painel import descrever_escopo

    res = descrever_escopo("BH Airport", agrupamento_nome="Aeroporto")
    assert res == "no agrupamento Aeroporto"


def test_descrever_escopo_local_supera_agrupamento():
    from src.api.painel import descrever_escopo

    # Quando ambos preenchidos, local ganha (mais específico).
    res = descrever_escopo("BH Airport", agrupamento_nome="Lojas", local_nome="Linx Confins")
    assert res == "em Linx Confins"


def test_descrever_escopo_com_fonte_amigavel():
    from src.api.painel import descrever_escopo

    res = descrever_escopo("BH Airport", local_nome="Terminal Confins", fonte_conector="google")
    assert res == "em Terminal Confins via Google Reviews"


def test_descrever_escopo_com_periodo():
    from src.api.painel import descrever_escopo

    res = descrever_escopo("BH Airport", periodo="30d")
    assert res == "geral da BH Airport nos últimos 30 dias"


def test_descrever_escopo_combinacao_completa():
    from src.api.painel import descrever_escopo

    res = descrever_escopo(
        "BH Airport",
        local_nome="Terminal Confins",
        fonte_conector="google",
        periodo="7d",
    )
    assert res == "em Terminal Confins via Google Reviews nos últimos 7 dias"


def test_descrever_escopo_fonte_sem_local_nem_agrupamento():
    from src.api.painel import descrever_escopo

    res = descrever_escopo("BH Airport", fonte_conector="instagram")
    assert res == "geral da BH Airport via Instagram"


def test_descrever_escopo_periodo_invalido_e_ignorado():
    from src.api.painel import descrever_escopo

    res = descrever_escopo("BH Airport", periodo="2y")
    assert res == "geral da BH Airport"


def test_painel_nivel1_inclui_filtros_descricao(client_loyall, db_session):
    """Endpoint nivel1 deve devolver `filtros_descricao` no JSON."""
    ctx = _empresa_estrutura(client_loyall, "fd")
    body = client_loyall.get(f"/api/empresas/{ctx['e']['id']}/painel/nivel1").get_json()
    assert "filtros_descricao" in body
    # Sem filtros → "geral da <nome>"
    assert body["filtros_descricao"].startswith("geral da")


def test_painel_nivel1_filtros_descricao_com_agrupamento(client_loyall, db_session):
    ctx = _empresa_estrutura(client_loyall, "fdag")
    body = client_loyall.get(
        f"/api/empresas/{ctx['e']['id']}/painel/nivel1?agrupamento_id={ctx['a']['id']}"
    ).get_json()
    assert body["filtros_descricao"] == "no agrupamento GPnl"


def test_painel_nivel1_filtros_descricao_com_local_e_periodo(client_loyall, db_session):
    ctx = _empresa_estrutura(client_loyall, "fdlp")
    body = client_loyall.get(
        f"/api/empresas/{ctx['e']['id']}/painel/nivel1" f"?local_id={ctx['loc']['id']}&periodo=30d"
    ).get_json()
    assert body["filtros_descricao"] == "em LPnl nos últimos 30 dias"


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
    # Nomes oficiais dos 12 subpilares (Manual Cap. 2)
    assert "Empatia Comercial" in html
    assert "Calibração da Promessa" in html
    assert "Eficácia Operacional" in html
    # Ratio P/D presente no card de pilar e na matriz
    assert "Ratio P/D" in html
    # Períodos do manual + adicionais
    for p in ["7d", "30d", "90d", "6m", "12m", "15m"]:
        assert f'value="{p}"' in html
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
    # Confere headers da tabela de pilares (com ratio + faixa)
    header_row = next(r for r in rows1 if r and r[0] == "Pilar")
    assert header_row[0:3] == ("Pilar", "Nome", "Total")
    assert "Ratio P/D" in header_row
    assert "Faixa" in header_row
    # Pa deve aparecer com total=1, nome correto, ratio 9.99 (1 prom, 0 detr)
    pa_row = next(r for r in rows1 if r and r[0] == "Pa")
    assert pa_row[1] == "Parceria"
    assert pa_row[2] == 1
    assert pa_row[3] == 1  # promotor
    assert pa_row[7] == 9.99  # Ratio P/D (saturação positiva)
    assert pa_row[8] == "excelente"

    ws2 = wb["Detalhamento por Subpilar"]
    rows2 = list(ws2.iter_rows(values_only=True))
    header2 = next(r for r in rows2 if r and r[0] == "Pilar")
    assert "Nome do Subpilar" in header2
    assert "Ratio P/D" in header2
    pa1_row = next(r for r in rows2 if r and r[1] == "Pa1")
    assert pa1_row[2] == "Empatia Comercial"  # nome oficial
    assert pa1_row[3] == 1  # promotor (1ª coluna de tipo após Nome)
    assert pa1_row[7] == 1  # total
    assert pa1_row[8] == 9.99  # ratio
    d2_row = next(r for r in rows2 if r and r[1] == "D2")
    assert d2_row[2] == "Eficácia Operacional"
    assert d2_row[5] == 1  # detrator


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
