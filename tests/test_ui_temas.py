"""Testes UI do CP-5 (Bloco 6): modal de temas no painel + admin/temas."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from src.models.temas import AcaoVenda, Tema, TemaCache, TemaCruzamento, VerbatimTema
from src.models.verbatim import Verbatim


def _cache(empresa_id, subpilar, tipo, label, volume, ex_ids, agrupamento_id=None):
    """TemaCache de teste com os campos NOT NULL preenchidos."""
    return TemaCache(
        empresa_id=empresa_id,
        agrupamento_id=agrupamento_id,
        subpilar=subpilar,
        tipo=tipo,
        tema_label=label,
        volume=volume,
        percentual=0.0,
        periodo_inicio=date(2026, 1, 1),
        periodo_fim=date(2026, 1, 31),
        exemplos_verbatim_ids=json.dumps(ex_ids),
        hash_escopo=f"h-{label}-{tipo}-{agrupamento_id}",
    )


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
    e, a, loc, f = _ctx(client_loyall, "m1")
    v = _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "txt", sub="Pa1", tipo="promotor")
    t = Tema(empresa_id=e["id"], nome="fila check-in", slug="fila-check-in")
    db_session.add(t)
    db_session.commit()
    db_session.add(_cache(e["id"], "Pa1", "promotor", "fila check-in", 1, [v.id], a["id"]))
    db_session.commit()

    r = client_loyall.get(f"/ui/empresas/{e['id']}/painel/temas-modal?subpilar=Pa1&tipo=promotor")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'id="temas-drawer"' in html
    assert "Pa1" in html
    assert "promotor" in html
    assert "fila check-in" in html
    assert "txt" in html  # texto do exemplo veio do SELECT batched
    # nota de nível agrupamento + "Todos os agrupamentos" (sem filtro)
    assert "nível" in html and "agrupamento" in html
    assert "Todos os agrupamentos" in html


def test_temas_modal_filtra_e_mostra_agrupamento(client_loyall, db_session):
    """Com ?agrupamento_id=X, o modal restringe e exibe o nome do agrupamento."""
    e, a, loc, f = _ctx(client_loyall, "mag")
    a2 = client_loyall.post(
        f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "Lojas"}
    ).get_json()
    db_session.add_all(
        [
            Tema(empresa_id=e["id"], nome="sinalização", slug="sinalizacao"),
            Tema(empresa_id=e["id"], nome="falta produtos lojas", slug="falta-produtos-lojas"),
        ]
    )
    db_session.commit()
    db_session.add_all(
        [
            _cache(e["id"], "D1", "detrator", "sinalização", 8, [], a["id"]),
            _cache(e["id"], "D1", "detrator", "falta produtos lojas", 59, [], a2["id"]),
        ]
    )
    db_session.commit()

    r = client_loyall.get(
        f"/ui/empresas/{e['id']}/painel/temas-modal?subpilar=D1&tipo=detrator"
        f"&agrupamento_id={a['id']}"
    )
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "sinalização" in html
    assert "falta produtos lojas" not in html  # do outro agrupamento → filtrado
    assert "Agrupamento:" in html  # header mostra o agrupamento filtrado
    assert "Todos os agrupamentos" not in html  # não é a visão consolidada


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


# ── B7 CP-5: seção "Temas transversais" no painel ────────────────────


def test_temas_tela_mostra_transversais(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "trans")
    cr = TemaCruzamento(
        empresa_id=e["id"],
        tema_label="preço alimentação",
        buckets_envolvidos_json=json.dumps(["P1:detrator", "Pa2:detrator"]),
        tipos_envolvidos_json=json.dumps(["detrator"]),
        n_subpilares_distintos=2,
        peso=4.39,
        periodo_inicio=date(2026, 1, 1),
        periodo_fim=date(2026, 1, 31),
        hash_escopo="hx-trans",
    )
    db_session.add(cr)
    db_session.commit()
    db_session.add(
        AcaoVenda(
            empresa_id=e["id"],
            tema_label="preço alimentação",
            cruzamento_id=cr.id,
            acao_texto="Renegociar contrato de concessão de alimentação.",
            impacto_qualitativo="alto",
            origem_modelo="claude-sonnet-4-6",
            hash_escopo="ha-trans",
        )
    )
    db_session.commit()

    r = client_loyall.get(f"/empresas/{e['id']}/temas")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Temas transversais" in html
    assert "preço alimentação" in html
    assert "P1:detrator" in html  # bucket chip (drill)
    assert "Renegociar contrato" in html  # ação N5 inline
    assert "impacto alto" in html  # selo
    assert "Abrangência:" in html  # rótulo qualitativo do peso


def test_painel_sem_transversais_nao_quebra(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "ESemTrans"}).get_json()
    r = client_loyall.get(f"/empresas/{e['id']}/painel")
    assert r.status_code == 200
    # seção é condicional — não aparece sem cruzamentos
    assert "Temas transversais" not in r.get_data(as_text=True)


def test_transversais_filtra_por_agrupamento(client_loyall, db_session):
    """Cruzamento 'preço lojas' só envolve Lojas → some ao filtrar outro agrupamento."""
    e, a_g, loc, f = _ctx(client_loyall, "tvag")  # a_g.nome == "G"
    a_lojas = client_loyall.post(
        f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "Lojas"}
    ).get_json()
    t = Tema(empresa_id=e["id"], nome="preço lojas", slug="preco-lojas")
    db_session.add(t)
    db_session.commit()
    # vínculo do tema só no agrupamento Lojas
    v = _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "caro demais")
    db_session.add(
        VerbatimTema(
            verbatim_id=v.id,
            tema_id=t.id,
            confianca=0.8,
            origem="llm",
            bucket_chave=f"{a_lojas['id']}:P1:detrator",
        )
    )
    db_session.add(
        TemaCruzamento(
            empresa_id=e["id"],
            tema_label="preço lojas",
            buckets_envolvidos_json=json.dumps(["P1:detrator", "Pa2:detrator"]),
            tipos_envolvidos_json=json.dumps(["detrator"]),
            n_subpilares_distintos=2,
            peso=8.3,
            periodo_inicio=date(2026, 1, 1),
            periodo_fim=date(2026, 1, 31),
            hash_escopo="hx-pl",
        )
    )
    db_session.commit()

    # sem filtro → aparece
    assert "preço lojas" in client_loyall.get(f"/empresas/{e['id']}/temas").get_data(as_text=True)
    # filtrado por Lojas → aparece (tema tem vínculo lá)
    html_lojas = client_loyall.get(
        f"/empresas/{e['id']}/temas?agrupamento_id={a_lojas['id']}"
    ).get_data(as_text=True)
    assert "preço lojas" in html_lojas
    # filtrado por G → some (tema não tem vínculo em G)
    html_g = client_loyall.get(f"/empresas/{e['id']}/temas?agrupamento_id={a_g['id']}").get_data(
        as_text=True
    )
    assert "preço lojas" not in html_g


# ── B6.6 CP-4: "Última coleta" nas telas ─────────────────────────────


def test_painel_mostra_ultima_coleta(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "uc1")
    _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "txt")  # data_coleta = agora
    html = client_loyall.get(f"/empresas/{e['id']}/painel").get_data(as_text=True)
    assert "Última coleta:" in html


def test_detalhe_sem_coleta_mostra_placeholder(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "ESemColeta"}).get_json()
    html = client_loyall.get(f"/empresas/{e['id']}").get_data(as_text=True)
    assert "sem coleta registrada" in html


# ── B6.6 CP-5: tela dedicada /empresas/<id>/temas ────────────────────


def test_temas_tela_renderiza_mapa_e_top_subpilar(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "tela")
    # verbatins p/ o Mapa de Lastro (n1/n2 calculam ratios)
    _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "ruim1", sub="D1", tipo="detrator")
    _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "ruim2", sub="D1", tipo="detrator")
    _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "bom1", sub="Pa1", tipo="promotor")
    # tema + cache p/ "top temas por subpilar"
    db_session.add(Tema(empresa_id=e["id"], nome="demora atendimento", slug="demora-atendimento"))
    db_session.commit()
    db_session.add(_cache(e["id"], "D1", "detrator", "demora atendimento", 7, [], a["id"]))
    db_session.commit()

    r = client_loyall.get(f"/empresas/{e['id']}/temas")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Mapa de Lastro" in html
    assert "Disponibilidade" in html  # nome do pilar D
    assert "Top temas por subpilar" in html
    assert "demora atendimento" in html
    # sidebar tem o link Temas
    assert ">Temas</a>" in html
    # nota da janela
    assert "últimos" in html and "dias" in html


def test_temas_tela_cliente_outra_empresa_403(client_loyall, client_cliente_factory):
    e1 = client_loyall.post("/api/empresas/", json={"nome": "ETmX1"}).get_json()
    e2 = client_loyall.post("/api/empresas/", json={"nome": "ETmX2"}).get_json()
    c = client_cliente_factory(e2["id"])
    r = c.get(f"/empresas/{e1['id']}/temas")
    assert r.status_code == 403


def test_painel_tem_link_temas_na_sidebar(client_loyall, db_session):
    # Painel agora é aba do Hub Explorar; Temas também virou aba. A navegação
    # para Temas se dá pela tab bar (?tab=temas), não mais por link de sidebar.
    e, _, loc, f = _ctx(client_loyall, "side")
    _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "x")
    html = client_loyall.get(f"/empresas/{e['id']}/painel").get_data(as_text=True)
    assert "ui.temas_empresa" not in html  # url_for resolvido, não literal
    assert "tab=temas" in html  # aba Temas presente na tab bar do Explorar


def test_temas_tela_top_subpilar_mostra_exemplos(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "ex")
    v = _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "preços absurdos no aeroporto")
    db_session.add(Tema(empresa_id=e["id"], nome="preço alto", slug="preco-alto"))
    db_session.commit()
    db_session.add(_cache(e["id"], "P1", "detrator", "preço alto", 5, [v.id], a["id"]))
    db_session.commit()
    html = client_loyall.get(f"/empresas/{e['id']}/temas").get_data(as_text=True)
    assert "preço alto" in html
    assert "preços absurdos no aeroporto" in html  # exemplo de verbatim na lista


def test_temas_modal_drill_subpilar_todos_tipos(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "drill")
    v = _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "demorou")
    db_session.add(Tema(empresa_id=e["id"], nome="demora", slug="demora"))
    db_session.commit()
    db_session.add_all(
        [
            _cache(e["id"], "D2", "detrator", "demora", 3, [v.id], a["id"]),
            _cache(e["id"], "D2", "promotor", "demora", 1, [v.id], a["id"]),
        ]
    )
    db_session.commit()
    r = client_loyall.get(f"/ui/empresas/{e['id']}/painel/temas-modal?subpilar=D2")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "todos os tipos" in html
    assert "demora" in html


def test_abrangencia_por_quartil():
    from src.ui import _abrangencia, _quartis

    pesos = [4.39, 5.28, 8.32, 14.13, 15.65, 20.33, 25.82]
    t25, t50, t75 = _quartis(pesos)
    assert _abrangencia(25.82, t25, t50, t75) == "muito alta"  # topo
    assert _abrangencia(14.13, t25, t50, t75) == "alta"  # >= P50
    assert _abrangencia(8.32, t25, t50, t75) == "média"  # >= P25
    assert _abrangencia(4.39, t25, t50, t75) == "baixa"  # < P25
    # casos de borda
    assert _quartis([]) == (0.0, 0.0, 0.0)
    assert _abrangencia(10, *_quartis([10])) == "muito alta"  # N=1 → tudo no topo
