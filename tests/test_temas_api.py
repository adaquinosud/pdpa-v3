"""Testes dos endpoints REST de temas (Bloco 6 CP-3).

Cobre: catálogo, criar manual, merge, temas de verbatim, painel temas,
reprocessar inline (com mock do extrator). Permissões: cliente vs loyall.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from src.models.temas import Tema, TemaCache, TemaCruzamento, VerbatimTema
from src.models.verbatim import Verbatim


def _cruz(empresa_id, label, buckets, tipos, n_sub, peso):
    """Monta um TemaCruzamento de teste."""
    return TemaCruzamento(
        empresa_id=empresa_id,
        tema_label=label,
        buckets_envolvidos_json=json.dumps(buckets),
        tipos_envolvidos_json=json.dumps(tipos),
        n_subpilares_distintos=n_sub,
        peso=peso,
        periodo_inicio=date(2026, 1, 1),
        periodo_fim=date(2026, 1, 31),
        hash_escopo=f"h-{label}",
    )


def _cache(empresa_id, subpilar, tipo, label, volume, ex_ids, agrupamento_id=None, percentual=0.0):
    """Monta um TemaCache de teste preenchendo os campos NOT NULL."""
    return TemaCache(
        empresa_id=empresa_id,
        agrupamento_id=agrupamento_id,
        subpilar=subpilar,
        tipo=tipo,
        tema_label=label,
        volume=volume,
        percentual=percentual,
        periodo_inicio=date(2026, 1, 1),
        periodo_fim=date(2026, 1, 31),
        exemplos_verbatim_ids=json.dumps(ex_ids),
        hash_escopo=f"h-{label}-{tipo}-{agrupamento_id}",
    )


def _ctx(client_loyall, sfx):
    """Cria empresa + agrupamento + local + fonte."""
    e = client_loyall.post("/api/empresas/", json={"nome": f"ETm-{sfx}"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais",
        json={"nome": "L", "agrupamento_id": a["id"]},
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ_t_{sfx}"},
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


# ── GET /api/empresas/<id>/temas ─────────────────────────────────────


def test_listar_temas_vazio(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "ETmV"}).get_json()
    r = client_loyall.get(f"/api/empresas/{e['id']}/temas")
    assert r.status_code == 200
    body = r.get_json()
    assert body["temas"] == []


def test_listar_temas_com_volume(client_loyall, db_session):
    e, _, loc, f = _ctx(client_loyall, "lv1")
    v = _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "txt")
    t = Tema(empresa_id=e["id"], nome="fila", slug="fila")
    db_session.add(t)
    db_session.commit()
    db_session.add(VerbatimTema(verbatim_id=v.id, tema_id=t.id, confianca=0.8, origem="llm"))
    db_session.commit()
    body = client_loyall.get(f"/api/empresas/{e['id']}/temas").get_json()
    assert len(body["temas"]) == 1
    assert body["temas"][0]["nome"] == "fila"
    assert body["temas"][0]["volume"] == 1


def test_listar_temas_filtro_busca(client_loyall, db_session):
    e, _, _, _ = _ctx(client_loyall, "lf1")
    db_session.add_all(
        [
            Tema(empresa_id=e["id"], nome="fila check-in", slug="fila-check-in"),
            Tema(empresa_id=e["id"], nome="limpeza", slug="limpeza"),
        ]
    )
    db_session.commit()
    body = client_loyall.get(f"/api/empresas/{e['id']}/temas?q=fila").get_json()
    assert len(body["temas"]) == 1
    assert body["temas"][0]["slug"] == "fila-check-in"


def test_listar_temas_oculta_inativos_por_default(client_loyall, db_session):
    e, _, _, _ = _ctx(client_loyall, "li1")
    db_session.add(Tema(empresa_id=e["id"], nome="a", slug="a-li", ativo=True))
    db_session.add(Tema(empresa_id=e["id"], nome="b", slug="b-li", ativo=False))
    db_session.commit()
    body = client_loyall.get(f"/api/empresas/{e['id']}/temas").get_json()
    assert len(body["temas"]) == 1
    body_all = client_loyall.get(f"/api/empresas/{e['id']}/temas?incluir_inativos=1").get_json()
    assert len(body_all["temas"]) == 2


# ── POST /api/empresas/<id>/temas ────────────────────────────────────


def test_criar_tema_manual(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "ECm"}).get_json()
    r = client_loyall.post(f"/api/empresas/{e['id']}/temas", json={"nome": "Fila no check-in"})
    assert r.status_code == 201
    body = r.get_json()
    assert body["slug"] == "fila-no-check-in"
    assert body["ativo"] is True


def test_criar_tema_duplicado_409(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "ECd"}).get_json()
    client_loyall.post(f"/api/empresas/{e['id']}/temas", json={"nome": "Fila"})
    r2 = client_loyall.post(f"/api/empresas/{e['id']}/temas", json={"nome": "fila"})
    assert r2.status_code == 409
    assert "já existe" in r2.get_json()["erro"]


def test_criar_tema_nome_vazio_400(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "ECnv"}).get_json()
    r = client_loyall.post(f"/api/empresas/{e['id']}/temas", json={"nome": ""})
    assert r.status_code == 400


def test_cliente_total_nao_cria_tema_403(client_loyall, client_cliente_factory):
    e = client_loyall.post("/api/empresas/", json={"nome": "ECcli"}).get_json()
    cli = client_cliente_factory(e["id"])
    r = cli.post(f"/api/empresas/{e['id']}/temas", json={"nome": "tema-x"})
    assert r.status_code == 403


# ── POST /api/temas/<id>/merge ───────────────────────────────────────


def test_merge_consolida_vinculacoes(client_loyall, db_session):
    e, _, loc, f = _ctx(client_loyall, "mg1")
    v1 = _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "v1")
    v2 = _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "v2")
    t_origem = Tema(empresa_id=e["id"], nome="demora", slug="demora")
    t_destino = Tema(empresa_id=e["id"], nome="lentidão", slug="lentidao")
    db_session.add_all([t_origem, t_destino])
    db_session.commit()
    # v1 vinculado a origem
    db_session.add(
        VerbatimTema(verbatim_id=v1.id, tema_id=t_origem.id, confianca=0.8, origem="llm")
    )
    # v2 vinculado a AMBOS (deve descartar a vinculação a origem após merge)
    db_session.add(
        VerbatimTema(verbatim_id=v2.id, tema_id=t_origem.id, confianca=0.6, origem="llm")
    )
    db_session.add(
        VerbatimTema(verbatim_id=v2.id, tema_id=t_destino.id, confianca=0.9, origem="llm")
    )
    db_session.commit()

    r = client_loyall.post(
        f"/api/temas/{t_origem.id}/merge",
        json={"tema_destino_id": t_destino.id, "motivo": "sinônimos"},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["vinculacoes_movidas"] == 1  # v1 → tema destino
    assert body["vinculacoes_descartadas"] == 1  # v2 já tinha destino

    db_session.expire_all()
    # Tema origem agora inativo
    db_session.refresh(t_origem)
    assert t_origem.ativo is False
    # v1 agora vinculado ao destino
    assert (
        db_session.query(VerbatimTema).filter_by(verbatim_id=v1.id, tema_id=t_destino.id).first()
        is not None
    )
    # Nenhuma vinculação restante ao origem
    assert db_session.query(VerbatimTema).filter_by(tema_id=t_origem.id).count() == 0


def test_merge_mesmo_id_400(client_loyall, db_session):
    e, _, _, _ = _ctx(client_loyall, "mgs")
    t = Tema(empresa_id=e["id"], nome="x", slug="x-mgs")
    db_session.add(t)
    db_session.commit()
    r = client_loyall.post(f"/api/temas/{t.id}/merge", json={"tema_destino_id": t.id})
    assert r.status_code == 400


def test_merge_cliente_403(client_loyall, client_cliente_factory):
    e = client_loyall.post("/api/empresas/", json={"nome": "EMg"}).get_json()
    cli = client_cliente_factory(e["id"])
    r = cli.post("/api/temas/1/merge", json={"tema_destino_id": 2})
    assert r.status_code == 403


# ── GET /api/verbatins/<id>/temas ────────────────────────────────────


def test_temas_de_verbatim(client_loyall, db_session):
    e, _, loc, f = _ctx(client_loyall, "vt")
    v = _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "txt")
    t1 = Tema(empresa_id=e["id"], nome="t1", slug="t1-vt")
    t2 = Tema(empresa_id=e["id"], nome="t2", slug="t2-vt")
    db_session.add_all([t1, t2])
    db_session.commit()
    db_session.add(VerbatimTema(verbatim_id=v.id, tema_id=t1.id, confianca=0.6, origem="llm"))
    db_session.add(
        VerbatimTema(
            verbatim_id=v.id,
            tema_id=t2.id,
            confianca=0.9,
            origem="llm",
            evidencia_curta="ev",
        )
    )
    db_session.commit()
    body = client_loyall.get(f"/api/verbatins/{v.id}/temas").get_json()
    assert len(body["temas"]) == 2
    # Ordenado por confiança desc
    assert body["temas"][0]["nome"] == "t2"
    assert body["temas"][0]["confianca"] == 0.9
    assert body["temas"][0]["evidencia_curta"] == "ev"


def test_temas_de_verbatim_404(client_loyall):
    r = client_loyall.get("/api/verbatins/999999/temas")
    assert r.status_code == 404


# ── GET /api/empresas/<id>/painel/temas ──────────────────────────────


def test_painel_temas_drill_down(client_loyall, db_session):
    """CP-13: painel lê de temas_cache. Volume = SUM(cache), agregado por label
    across agrupamentos; exemplos resolvidos pelos ids guardados no cache."""
    e, a, loc, f = _ctx(client_loyall, "pt1")
    # 3 verbatins D2 detrator (servem de exemplo p/ os ids do cache)
    vs = [
        _criar_verbatim(db_session, e["id"], f["id"], loc["id"], f"v{i}", "D2", "detrator")
        for i in range(3)
    ]
    t_demora = Tema(empresa_id=e["id"], nome="demora bagagem", slug="demora-bagagem")
    t_fila = Tema(empresa_id=e["id"], nome="fila check-in", slug="fila-check-in")
    db_session.add_all([t_demora, t_fila])
    db_session.commit()
    # Cache: "demora bagagem" em 2 agrupamentos (vol 2 + 1 = 3, exemplos 3 ids);
    # "fila check-in" vol 1. Comprova agregação por label e leitura do cache.
    db_session.add_all(
        [
            _cache(e["id"], "D2", "detrator", "demora bagagem", 2, [vs[0].id, vs[1].id], a["id"]),
            _cache(e["id"], "D2", "detrator", "demora bagagem", 1, [vs[2].id], None),
            _cache(e["id"], "D2", "detrator", "fila check-in", 1, [vs[0].id], a["id"]),
            # Bucket de outro tipo: não deve aparecer
            _cache(e["id"], "D2", "promotor", "demora bagagem", 9, [vs[0].id], a["id"]),
        ]
    )
    db_session.commit()

    body = client_loyall.get(
        f"/api/empresas/{e['id']}/painel/temas?subpilar=D2&tipo=detrator"
    ).get_json()
    assert body["subpilar"] == "D2"
    assert body["tipo"] == "detrator"
    assert len(body["temas"]) == 2
    assert body["temas"][0]["nome"] == "demora bagagem"
    assert body["temas"][0]["volume"] == 3  # 2 + 1 agregados; promotor (9) excluído
    assert body["temas"][0]["slug"] == "demora-bagagem"
    assert len(body["temas"][0]["exemplos"]) == 3
    assert body["temas"][1]["nome"] == "fila check-in"
    assert body["temas"][1]["volume"] == 1


def test_painel_temas_sem_subpilar_tipo_400(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "EPt"}).get_json()
    r = client_loyall.get(f"/api/empresas/{e['id']}/painel/temas")
    assert r.status_code == 400


def test_painel_temas_oculta_inativos(client_loyall, db_session):
    """Tema inativo: o INNER JOIN (ativo=True) descarta a row de cache dele."""
    e, a, loc, f = _ctx(client_loyall, "pt_inat")
    v = _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "x", "D2", "detrator")
    t = Tema(empresa_id=e["id"], nome="t", slug="t-inat", ativo=False)
    db_session.add(t)
    db_session.commit()
    db_session.add(_cache(e["id"], "D2", "detrator", "t", 1, [v.id], a["id"]))
    db_session.commit()
    body = client_loyall.get(
        f"/api/empresas/{e['id']}/painel/temas?subpilar=D2&tipo=detrator"
    ).get_json()
    assert body["temas"] == []


def test_painel_temas_filtra_por_agrupamento(client_loyall, db_session):
    """Bug fix: ?agrupamento_id=X restringe ao agrupamento (cache é indexado por ele)."""
    e, a_aero, loc, f = _ctx(client_loyall, "pt_ag")
    a_lojas = client_loyall.post(
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
            _cache(e["id"], "D1", "detrator", "sinalização", 8, [], a_aero["id"]),
            _cache(e["id"], "D1", "detrator", "falta produtos lojas", 59, [], a_lojas["id"]),
        ]
    )
    db_session.commit()

    # sem filtro: consolidado da empresa (os dois)
    body = client_loyall.get(
        f"/api/empresas/{e['id']}/painel/temas?subpilar=D1&tipo=detrator"
    ).get_json()
    assert {t["nome"] for t in body["temas"]} == {"sinalização", "falta produtos lojas"}
    assert body["agrupamento_id"] is None

    # filtrado por Aeroporto: só o tema do Aeroporto (falta produtos lojas some)
    body2 = client_loyall.get(
        f"/api/empresas/{e['id']}/painel/temas?subpilar=D1&tipo=detrator"
        f"&agrupamento_id={a_aero['id']}"
    ).get_json()
    assert body2["agrupamento_id"] == a_aero["id"]
    assert {t["nome"] for t in body2["temas"]} == {"sinalização"}


# ── GET /api/empresas/<id>/temas/cruzamentos (Nível 4) ───────────────


def test_painel_cruzamentos_ordena_por_peso(client_loyall, db_session):
    e = client_loyall.post("/api/empresas/", json={"nome": "ECruzApi"}).get_json()
    db_session.add_all(
        [
            _cruz(
                e["id"],
                "infraestrutura",
                ["A1:promotor", "D1:promotor", "P2:detrator"],
                ["detrator", "promotor"],
                3,
                25.82,
            ),
            _cruz(
                e["id"],
                "atendimento",
                ["Pa1:conversivel", "Pa1:promotor"],
                ["conversivel", "promotor"],
                1,
                14.13,
            ),
        ]
    )
    db_session.commit()
    body = client_loyall.get(f"/api/empresas/{e['id']}/temas/cruzamentos").get_json()
    assert len(body["cruzamentos"]) == 2
    c0 = body["cruzamentos"][0]
    assert c0["tema_label"] == "infraestrutura"  # maior peso primeiro
    assert c0["n_subpilares_distintos"] == 3
    assert c0["buckets_envolvidos"] == ["A1:promotor", "D1:promotor", "P2:detrator"]
    assert c0["membros"] is None  # literal


def test_painel_cruzamentos_filtra_min_subpilares(client_loyall, db_session):
    e = client_loyall.post("/api/empresas/", json={"nome": "ECruzFiltro"}).get_json()
    db_session.add_all(
        [
            _cruz(e["id"], "infraestrutura", ["A1:promotor", "D1:promotor"], ["promotor"], 2, 10.0),
            _cruz(e["id"], "atendimento", ["Pa1:promotor", "Pa1:conversivel"], ["x"], 1, 9.0),
        ]
    )
    db_session.commit()
    body = client_loyall.get(
        f"/api/empresas/{e['id']}/temas/cruzamentos?min_subpilares=2"
    ).get_json()
    assert len(body["cruzamentos"]) == 1
    assert body["cruzamentos"][0]["tema_label"] == "infraestrutura"


def test_painel_cruzamentos_vazio(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "ECruzVazio"}).get_json()
    body = client_loyall.get(f"/api/empresas/{e['id']}/temas/cruzamentos").get_json()
    assert body["cruzamentos"] == []


# ── POST /api/empresas/<id>/temas/reprocessar ────────────────────────


def test_reprocessar_inline_persiste_temas(client_loyall, db_session, monkeypatch):
    e, _, loc, f = _ctx(client_loyall, "rp1")
    _criar_verbatim(
        db_session, e["id"], f["id"], loc["id"], "Bagagem demorou muito", "D2", "detrator"
    )
    _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "Fila enorme", "D1", "detrator")

    # Mock do extrator devolvendo temas previsíveis
    def fake_extrator(texto, contexto, catalogo_recente=None):
        if "bagagem" in texto.lower():
            return [{"nome": "demora bagagem", "confianca": 0.9, "evidencia_curta": "demorou"}]
        return [{"nome": "fila", "confianca": 0.8, "evidencia_curta": "enorme"}]

    monkeypatch.setattr("src.api.temas.extrair_temas", fake_extrator)

    r = client_loyall.post(f"/api/empresas/{e['id']}/temas/reprocessar", json={})
    assert r.status_code == 200
    body = r.get_json()
    assert body["verbatins_processados"] == 2
    assert body["novos_vinculos"] == 2
    assert body["erros"] == 0
    assert body["custo_estimado_usd"] > 0

    # Verifica que os temas foram criados no catálogo
    temas = client_loyall.get(f"/api/empresas/{e['id']}/temas").get_json()
    slugs = {t["slug"] for t in temas["temas"]}
    assert "demora-bagagem" in slugs
    assert "fila" in slugs


def test_reprocessar_excede_cap_413(client_loyall, db_session, monkeypatch):
    """Quando há mais que REPROCESSAR_INLINE_MAX verbatins elegíveis, devolve 413."""
    monkeypatch.setattr("src.api.temas.REPROCESSAR_INLINE_MAX", 1)
    e, _, loc, f = _ctx(client_loyall, "rpcap")
    _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "t1")
    _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "t2")
    r = client_loyall.post(f"/api/empresas/{e['id']}/temas/reprocessar", json={})
    assert r.status_code == 413
    body = r.get_json()
    assert "CLI" in body["erro"]
    assert body["total_elegivel"] == 2


def test_reprocessar_apenas_novos_pula_ja_processados(client_loyall, db_session, monkeypatch):
    e, _, loc, f = _ctx(client_loyall, "rpan")
    v1 = _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "ja-proc")
    _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "novo")  # v2: alvo
    # v1 já tem tema vinculado
    t = Tema(empresa_id=e["id"], nome="existe", slug="existe-rpan")
    db_session.add(t)
    db_session.commit()
    db_session.add(VerbatimTema(verbatim_id=v1.id, tema_id=t.id, confianca=0.7, origem="llm"))
    db_session.commit()

    chamadas = []

    def fake_extrator(texto, contexto, catalogo_recente=None):
        chamadas.append(texto)
        return [{"nome": "novo-tema", "confianca": 0.7, "evidencia_curta": "x"}]

    monkeypatch.setattr("src.api.temas.extrair_temas", fake_extrator)

    r = client_loyall.post(
        f"/api/empresas/{e['id']}/temas/reprocessar", json={"apenas_novos": True}
    )
    assert r.status_code == 200
    assert r.get_json()["verbatins_processados"] == 1
    assert chamadas == ["novo"]  # v1 foi pulado


def test_reprocessar_cliente_403(client_loyall, client_cliente_factory):
    e = client_loyall.post("/api/empresas/", json={"nome": "ERp"}).get_json()
    cli = client_cliente_factory(e["id"])
    r = cli.post(f"/api/empresas/{e['id']}/temas/reprocessar", json={})
    assert r.status_code == 403


# ── Idempotência da persistência ─────────────────────────────────────


def test_persistir_temas_idempotente(client_loyall, db_session, monkeypatch):
    """Rodar reprocessar 2x não duplica vinculações (UNIQUE garante)."""
    e, _, loc, f = _ctx(client_loyall, "rpid")
    _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "verbatim único")

    def fake(texto, contexto, catalogo_recente=None):
        return [{"nome": "tema-id", "confianca": 0.8, "evidencia_curta": "x"}]

    monkeypatch.setattr("src.api.temas.extrair_temas", fake)

    r1 = client_loyall.post(f"/api/empresas/{e['id']}/temas/reprocessar", json={})
    r2 = client_loyall.post(f"/api/empresas/{e['id']}/temas/reprocessar", json={})
    assert r1.status_code == r2.status_code == 200
    # 2ª vez não cria vinculação nova (já existe pareamento UNIQUE)
    total_vinculos = db_session.query(VerbatimTema).count()
    assert total_vinculos == 1
