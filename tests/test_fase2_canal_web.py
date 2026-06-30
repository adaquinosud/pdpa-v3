"""Tests do canal web (Fase 2 · Passo 2a): token público + núcleo registrar_respostas
+ rota pública /p/<token>. D-canal: coleta→Verbatim, confronto→Resposta."""

from __future__ import annotations

from src.coletor.excel import _find_or_create_fonte  # noqa: F401  (garante o módulo)
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.pessoa import Pessoa, PessoaIdentificador
from src.models.respondente import Respondente, Resposta
from src.models.verbatim import Verbatim
from src.pesquisa.coleta import registrar_respostas
from src.pesquisa.persistencia import aprovar, payload_publico


def _pesquisa_pronta(db_session, nome, proposito, anonima=False, token="tok-123"):
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="externa",
        proposito=proposito,
        titulo="Satisfação",
        status="pronta",
        anonima=anonima,
        token_publico=token,
        entidade_tipo="empresa",
    )
    db_session.add(p)
    db_session.flush()
    q = PesquisaPergunta(pesquisa_id=p.id, ordem=1, enunciado="Como foi?", formato="mista")
    db_session.add(q)
    db_session.flush()
    return p, q


# ── token + payload ──────────────────────────────────────────────────────────


def test_aprovar_gera_token_publico(client_loyall, db_session):
    e = Empresa(nome="ETok")
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(empresa_id=e.id, natureza="externa", titulo="T", status="rascunho")
    db_session.add(p)
    db_session.flush()
    db_session.add(PesquisaPergunta(pesquisa_id=p.id, ordem=1, enunciado="Oi?", formato="aberta"))
    db_session.flush()
    ok, _ = aprovar(db_session, p.id)
    assert ok is True
    assert db_session.get(Pesquisa, p.id).token_publico  # gerado ao publicar


def test_payload_expoe_pergunta_id(db_session):
    p, q = _pesquisa_pronta(db_session, "EPayload", "coleta")
    payload = payload_publico(p)
    assert payload["perguntas"][0]["id"] == q.id


# ── núcleo registrar_respostas ───────────────────────────────────────────────


def test_registrar_confronto_cria_resposta(db_session):
    p, q = _pesquisa_pronta(db_session, "EConf", "confronto")
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=None,
        respostas=[{"pergunta_id": q.id, "texto": "Ótimo", "nota": 5, "opcao": None}],
    )
    db_session.commit()
    assert db_session.query(Respondente).filter_by(pesquisa_id=p.id).count() == 1
    r = db_session.query(Resposta).one()
    assert r.valor_nota == 5 and r.valor_texto == "Ótimo"
    assert db_session.query(Verbatim).count() == 0  # confronto NÃO vira verbatim


def test_registrar_coleta_cria_verbatim(db_session):
    p, q = _pesquisa_pronta(db_session, "EColeta", "coleta")
    pessoa = Pessoa(tipo="interno_consentido", nome_display="Ana")
    db_session.add(pessoa)
    db_session.flush()
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=pessoa.id,
        respostas=[{"pergunta_id": q.id, "texto": "Atendimento bom", "nota": 4, "opcao": None}],
    )
    db_session.commit()
    assert db_session.query(Respondente).filter_by(pesquisa_id=p.id).count() == 1
    v = db_session.query(Verbatim).one()
    assert v.texto == "Atendimento bom" and v.rating == 4
    assert v.pessoa_id == pessoa.id and v.autor == "Ana"  # autor coexiste
    f = db_session.get(Fonte, v.fonte_id)
    assert f.conector_tipo == "pesquisa_web"
    assert db_session.query(Resposta).count() == 0  # coleta NÃO vira resposta estruturada


# ── rota pública ─────────────────────────────────────────────────────────────


def test_rota_token_invalido_erro_amigavel(client_loyall):
    r = client_loyall.get("/p/inexistente")
    assert r.status_code == 404
    assert "indispon" in r.get_data(as_text=True).lower()


def test_rota_get_renderiza_form(client_loyall, db_session):
    p, q = _pesquisa_pronta(db_session, "EGet", "confronto", token="tok-get")
    db_session.commit()
    r = client_loyall.get("/p/tok-get")
    assert r.status_code == 200
    assert "Satisfação" in r.get_data(as_text=True)


def test_rota_submit_anonimo(client_loyall, db_session):
    p, q = _pesquisa_pronta(db_session, "EAnon", "confronto", anonima=True, token="tok-anon")
    db_session.commit()
    r = client_loyall.post(
        "/p/tok-anon", data={f"q_{q.id}_texto": "Tudo certo", f"q_{q.id}_nota": "5"}
    )
    assert r.status_code == 200 and "Obrigado" in r.get_data(as_text=True)
    resp = db_session.query(Respondente).filter_by(pesquisa_id=p.id).one()
    assert resp.pessoa_id is None  # anônimo


def test_rota_submit_identificado_cria_pessoa(client_loyall, db_session):
    p, q = _pesquisa_pronta(db_session, "EIdent", "confronto", anonima=False, token="tok-id")
    db_session.commit()
    r = client_loyall.post(
        "/p/tok-id",
        data={
            f"q_{q.id}_texto": "Bom",
            f"q_{q.id}_nota": "4",
            "nome": "João",
            "email": "Joao@X.com",
            "consentimento": "on",
        },
    )
    assert r.status_code == 200 and "Obrigado" in r.get_data(as_text=True)
    ident = db_session.query(PessoaIdentificador).filter_by(external_id="joao@x.com").one()
    assert ident.fonte == "pesquisa" and ident.tipo == "interno_consentido"
    resp = db_session.query(Respondente).filter_by(pesquisa_id=p.id).one()
    assert resp.pessoa_id == ident.pessoa_id
