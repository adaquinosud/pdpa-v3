"""Tests do canal web (Fase 2 · Passo 2a): token público + núcleo registrar_respostas
+ rota pública /p/<token>. D-canal: coleta→Verbatim, confronto→Resposta."""

from __future__ import annotations

import json

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


# ── regressão: campo em branco (nota-only) não colide no hash_dedup → salva OK ─


def _pergunta(db_session, p, ordem):
    q = PesquisaPergunta(pesquisa_id=p.id, ordem=ordem, enunciado=f"Q{ordem}", formato="mista")
    db_session.add(q)
    db_session.flush()
    return q


def test_notaonly_mesma_submissao_duas_perguntas(client_loyall, db_session):
    """Duas perguntas com a MESMA nota e comentário EM BRANCO na mesma submissão →
    antes colidiam no hash_dedup (UNIQUE → 500). Agora o discriminador por resposta
    dá identidade única → salva OK, ambas viram verbatim."""
    p, q1 = _pesquisa_pronta(db_session, "EVazioA", "coleta", anonima=True, token="tok-va")
    eid = p.empresa_id
    q2 = _pergunta(db_session, p, 2)
    db_session.commit()
    r = client_loyall.post(
        "/p/tok-va",
        data={
            f"q_{q1.id}_nota": "5",
            f"q_{q1.id}_texto": "",
            f"q_{q2.id}_nota": "5",
            f"q_{q2.id}_texto": "",
        },
    )
    assert r.status_code == 200 and "Obrigado" in r.get_data(as_text=True)
    vs = db_session.query(Verbatim).filter_by(empresa_id=eid).all()
    assert len(vs) == 2 and all(v.texto == "" and v.rating == 5 for v in vs)
    assert len({v.hash_dedup for v in vs}) == 2  # hashes distintos (discriminador)
    assert all(v.review_id_externo and v.review_id_externo.startswith("resp:") for v in vs)


def test_notaonly_entre_submissoes_mesma_nota(client_loyall, db_session):
    """Dois respondentes com a MESMA nota e comentário em branco (submissões
    SEPARADAS) → antes o 2º colidia (500). Agora ambos salvam e coexistem."""
    p, q = _pesquisa_pronta(db_session, "EVazioB", "coleta", anonima=True, token="tok-vb")
    eid = p.empresa_id
    db_session.commit()
    r1 = client_loyall.post("/p/tok-vb", data={f"q_{q.id}_nota": "4", f"q_{q.id}_texto": ""})
    r2 = client_loyall.post("/p/tok-vb", data={f"q_{q.id}_nota": "4", f"q_{q.id}_texto": ""})
    assert r1.status_code == 200 and r2.status_code == 200
    assert db_session.query(Respondente).filter_by(pesquisa_id=p.id).count() == 2
    assert db_session.query(Verbatim).filter_by(empresa_id=eid).count() == 2  # coexistem


# ── validação da resposta pública: nota + unidade obrigatórias; comentário opcional ─


def _pergunta_nota(db_session, p, ordem=2):
    q = PesquisaPergunta(
        pesquisa_id=p.id,
        ordem=ordem,
        enunciado="Nota do atendimento",
        formato="mista",
        opcoes_json=json.dumps({"tipo": "nota", "rotulos": ["1", "2", "3", "4", "5"]}),
    )
    db_session.add(q)
    db_session.flush()
    return q


def _pergunta_unidade(db_session, p, ordem=3):
    q = PesquisaPergunta(
        pesquisa_id=p.id,
        ordem=ordem,
        enunciado="Qual unidade?",
        formato="fechada",
        opcoes_json=json.dumps(
            {
                "tipo": "unidade",
                "opcoes": [
                    {"entidade_tipo": "local", "entidade_id": 1, "rotulo": "Loja A"},
                    {"entidade_tipo": "local", "entidade_id": 2, "rotulo": "Loja B"},
                ],
            }
        ),
    )
    db_session.add(q)
    db_session.flush()
    return q


def test_form_nota_required_comentario_opcional(client_loyall, db_session):
    """Client-side: a nota é required (radio) e ganha *; o comentário segue opcional."""
    p, _q = _pesquisa_pronta(db_session, "EValReq", "confronto", token="tok-vr")
    qn = _pergunta_nota(db_session, p)
    db_session.commit()
    html = client_loyall.get("/p/tok-vr").get_data(as_text=True)
    assert f'name="q_{qn.id}_nota" value="1" required' in html  # nota obrigatória
    assert "Seu comentário (opcional)" in html  # comentário permanece opcional
    assert "obrigatório" in html  # legenda do *


def test_valida_nota_unidade_ok_comentario_vazio(client_loyall, db_session):
    """Nota + unidade preenchidas, comentário EM BRANCO → salva (200)."""
    p, _q = _pesquisa_pronta(db_session, "EValOk", "confronto", anonima=True, token="tok-vok")
    qn = _pergunta_nota(db_session, p)
    qu = _pergunta_unidade(db_session, p)
    db_session.commit()
    r = client_loyall.post(
        "/p/tok-vok",
        data={f"q_{qn.id}_nota": "5", f"q_{qn.id}_texto": "", f"ancora_{qu.id}": "local:1"},
    )
    assert r.status_code == 200 and "Obrigado" in r.get_data(as_text=True)
    assert db_session.query(Respondente).filter_by(pesquisa_id=p.id).count() == 1


def test_valida_sem_nota_erro_amigavel(client_loyall, db_session):
    """Sem nota → erro amigável (400) apontando a pergunta, sem gravar, sem 500."""
    p, _q = _pesquisa_pronta(db_session, "EValN", "confronto", anonima=True, token="tok-vn")
    qn = _pergunta_nota(db_session, p)
    db_session.commit()
    r = client_loyall.post("/p/tok-vn", data={f"q_{qn.id}_texto": "só comentário"})
    body = r.get_data(as_text=True)
    assert r.status_code == 400 and "Obrigado" not in body
    assert "obrigatório" in body and "Nota do atendimento" in body  # aponta a pergunta
    assert db_session.query(Respondente).filter_by(pesquisa_id=p.id).count() == 0  # não gravou


def test_valida_sem_unidade_multiloja_erro(client_loyall, db_session):
    """Multi-loja sem a âncora de unidade → erro (400) apontando 'Qual unidade?'."""
    p, _q = _pesquisa_pronta(db_session, "EValU", "confronto", anonima=True, token="tok-vu")
    qn = _pergunta_nota(db_session, p)
    _pergunta_unidade(db_session, p)  # âncora obrigatória, deixada em branco no POST
    db_session.commit()
    r = client_loyall.post("/p/tok-vu", data={f"q_{qn.id}_nota": "4"})  # nota ok, sem unidade
    body = r.get_data(as_text=True)
    assert r.status_code == 400 and "Obrigado" not in body
    assert "Qual unidade?" in body
    assert db_session.query(Respondente).filter_by(pesquisa_id=p.id).count() == 0
