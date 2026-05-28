"""Tests do IA Chat (CP-B4): contexto, cache exato e rota. gerar_fn fake — $0."""

from __future__ import annotations

from datetime import datetime

from src.ia.chat import _normalizar, escopo_hash, responder, responder_stream
from src.ia.contexto import formatar_contexto, montar_contexto
from src.models.chat_cache import ChatCache
from src.models.verbatim import Verbatim


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"EIA-{sfx}"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "Loja 1", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": f"ChIJ_{sfx}"}
    ).get_json()
    return e, a, loc, f


def _verb(db_session, e, loc, f, sub, tipo, n, texto="comentário"):
    for i in range(n):
        db_session.add(
            Verbatim(
                empresa_id=e["id"],
                fonte_id=f["id"],
                local_id=loc["id"],
                texto=f"{texto} {tipo} {i}",
                subpilar=sub,
                tipo=tipo,
                tem_texto=True,
                data_criacao_original=datetime(2026, 5, 1),
                hash_dedup=f"h{sub}{tipo}{i}-{datetime.utcnow().timestamp()}",
            )
        )


def test_normalizar_pergunta():
    assert _normalizar("  Qual o GARGALO?? ") == "qual o gargalo"
    assert _normalizar("Onde   estão   as oportunidades.") == "onde estão as oportunidades"


def test_montar_e_formatar_contexto(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "ctx")
    _verb(db_session, e, loc, f, "D2", "detrator", 5, texto="fila enorme")
    _verb(db_session, e, loc, f, "P1", "promotor", 3)
    db_session.commit()
    dados = montar_contexto(db_session, e["id"])
    assert dados["resumo"]["volume_classificado"] == 8
    assert dados["resumo"]["pilar_gargalo"]  # algum pilar
    assert len(dados["verbatins_detratores"]) == 5
    texto = formatar_contexto(dados)
    assert "## RESUMO" in texto and "FALAS RECENTES" in texto
    assert "fila enorme" in texto


def test_responder_usa_cache_no_segundo_hit(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "cache")
    _verb(db_session, e, loc, f, "D2", "detrator", 4)
    db_session.commit()

    chamadas = {"n": 0}

    def fake(system_prompt, contexto, pergunta):
        chamadas["n"] += 1
        return {"resposta": f"resposta {chamadas['n']}", "tokens_in": 10, "tokens_out": 5}

    out1 = responder(db_session, e["id"], "Qual o gargalo?", gerar_fn=fake)
    assert out1["cached"] is False and out1["resposta"] == "resposta 1"
    # mesma pergunta (variação cosmética) → cache, não chama de novo
    out2 = responder(db_session, e["id"], "  qual o GARGALO  ", gerar_fn=fake)
    assert out2["cached"] is True and out2["resposta"] == "resposta 1"
    assert chamadas["n"] == 1
    assert db_session.query(ChatCache).filter_by(empresa_id=e["id"]).count() == 1


def test_responder_escopo_separa_cache(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "esc")
    _verb(db_session, e, loc, f, "D2", "detrator", 4)
    db_session.commit()

    def fake(sp, ctx, p):
        return {"resposta": "r", "tokens_in": 1, "tokens_out": 1}

    responder(db_session, e["id"], "X?", ag_id=None, periodo=None, gerar_fn=fake)
    responder(db_session, e["id"], "X?", ag_id=a["id"], periodo="30d", gerar_fn=fake)
    # escopos diferentes → 2 entradas de cache distintas
    assert db_session.query(ChatCache).filter_by(empresa_id=e["id"]).count() == 2
    assert escopo_hash(None, None) != escopo_hash(a["id"], "30d")


def test_tab_ia_renderiza_sugestoes(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "tab")
    _verb(db_session, e, loc, f, "D2", "detrator", 4)
    db_session.commit()
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/ia").get_data(as_text=True)
    assert "Pergunte ao consultor PDPA" in h
    assert "principal gargalo" in h  # perguntas-sugestão renderizadas


def test_rota_perguntar_responde(client_loyall, db_session, monkeypatch):
    e, a, loc, f = _ctx(client_loyall, "rota")
    _verb(db_session, e, loc, f, "D2", "detrator", 4)
    db_session.commit()

    import src.ia.chat as chat_mod

    monkeypatch.setattr(
        chat_mod,
        "_chamar_sonnet",
        lambda sp, ctx, p: {
            "resposta": "O gargalo é Disponibilidade.",
            "tokens_in": 1,
            "tokens_out": 1,
        },
    )
    r = client_loyall.post(
        f"/empresas/{e['id']}/explorar/ia/perguntar", data={"pergunta": "Qual o gargalo?"}
    )
    assert r.status_code == 200
    assert "O gargalo é Disponibilidade." in r.get_data(as_text=True)


def test_rota_perguntar_vazia(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "vazia")
    r = client_loyall.post(f"/empresas/{e['id']}/explorar/ia/perguntar", data={"pergunta": "   "})
    assert r.status_code == 200
    assert "Digite uma pergunta" in r.get_data(as_text=True)


def test_responder_stream_acumula_e_cacheia(client_loyall, db_session):
    """IA-1: stream acumula os deltas e persiste a resposta completa no cache."""
    e, a, loc, f = _ctx(client_loyall, "stream")
    _verb(db_session, e, loc, f, "D2", "detrator", 4)
    db_session.commit()

    def fake_stream(sp, ctx, p):
        for d in ["O gargalo ", "é ", "Disponibilidade."]:
            yield d

    chunks = list(responder_stream(e["id"], "Qual o gargalo?", stream_fn=fake_stream))
    assert "".join(chunks) == "O gargalo é Disponibilidade."
    assert db_session.query(ChatCache).filter_by(empresa_id=e["id"]).count() == 1

    # 2ª vez (cache hit): devolve a resposta inteira de uma vez, sem stream_fn
    def _boom(sp, ctx, p):
        raise AssertionError("não deveria chamar o LLM no cache hit")
        yield  # noqa

    chunks2 = list(responder_stream(e["id"], "  qual o GARGALO ", stream_fn=_boom))
    assert "".join(chunks2) == "O gargalo é Disponibilidade."


def test_rota_ia_stream(client_loyall, db_session, monkeypatch):
    e, a, loc, f = _ctx(client_loyall, "rstream")
    _verb(db_session, e, loc, f, "D2", "detrator", 4)
    db_session.commit()
    import src.ia.chat as chat_mod

    monkeypatch.setattr(
        chat_mod,
        "_chamar_sonnet_stream",
        lambda sp, ctx, p: iter(["Gargalo ", "é ", "Precisão."]),
    )
    r = client_loyall.post(
        f"/empresas/{e['id']}/explorar/ia/stream", data={"pergunta": "Qual o gargalo?"}
    )
    assert r.status_code == 200
    assert r.get_data(as_text=True) == "Gargalo é Precisão."


def test_tab_ia_tem_streaming_js(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "iajs")
    _verb(db_session, e, loc, f, "D2", "detrator", 4)
    db_session.commit()
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/ia").get_data(as_text=True)
    assert "ia/stream" in h and "getReader" in h  # ilha de streaming presente


def test_tab_ia_transcript_e_nova_conversa(client_loyall, db_session):
    """IA-3: aba tem transcript de sessão + botão Nova conversa + histórico separado."""
    e, a, loc, f = _ctx(client_loyall, "iatr")
    _verb(db_session, e, loc, f, "D2", "detrator", 4)
    db_session.commit()
    # cria uma Q&A cacheada NO ESCOPO ATUAL (sem filtros → escopo_hash(None, None))
    db_session.add(
        ChatCache(
            empresa_id=e["id"],
            escopo_hash=escopo_hash(None, None),
            pergunta_hash="y",
            pergunta="pergunta antiga",
            resposta="resposta antiga",
        )
    )
    db_session.commit()
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/ia").get_data(as_text=True)
    assert 'id="ia-transcript"' in h  # transcript da sessão
    assert "Nova conversa" in h  # botão
    assert "Histórico do escopo" in h and "pergunta antiga" in h  # cache separado
