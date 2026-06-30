"""Tests da estrutura de coleta — Fase 2 · Passo 1 (Respondente + Resposta).

Frente aditiva: 2 tabelas + Pesquisa.proposito. Cobre defaults/CHECKs, escopo
entidade_tipo/entidade_id (vocabulário do pai), pessoa_id nullable (anônimo),
valor tipado da Resposta e o unique (respondente, pergunta).
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.empresa import Empresa
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.pessoa import Pessoa
from src.models.respondente import Respondente, Resposta


def _pesquisa(db_session, nome, natureza="interna", proposito="coleta"):
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(empresa_id=e.id, natureza=natureza, proposito=proposito, titulo="T")
    db_session.add(p)
    db_session.flush()
    q = PesquisaPergunta(pesquisa_id=p.id, ordem=1, enunciado="Como foi?", formato="mista")
    db_session.add(q)
    db_session.flush()
    return p, q


# ── Pesquisa.proposito ───────────────────────────────────────────────────────


def test_proposito_default_coleta(db_session):
    e = Empresa(nome="EProp")
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(empresa_id=e.id, natureza="externa", titulo="T")  # sem proposito
    db_session.add(p)
    db_session.commit()
    assert db_session.get(Pesquisa, p.id).proposito == "coleta"


def test_proposito_check_invalido(db_session):
    e = Empresa(nome="EPropCheck")
    db_session.add(e)
    db_session.flush()
    db_session.add(Pesquisa(empresa_id=e.id, natureza="externa", titulo="T", proposito="xxx"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_proposito_livre_vs_natureza(db_session):
    """Sem CHECK amarrando: interna+coleta E externa+confronto são aceitos."""
    p1, _ = _pesquisa(db_session, "EA", natureza="interna", proposito="coleta")
    p2, _ = _pesquisa(db_session, "EB", natureza="externa", proposito="confronto")
    db_session.commit()
    assert db_session.get(Pesquisa, p1.id).proposito == "coleta"
    assert db_session.get(Pesquisa, p2.id).proposito == "confronto"


# ── Respondente ──────────────────────────────────────────────────────────────


def test_respondente_anonimo_e_identificado(db_session):
    p, q = _pesquisa(db_session, "EResp")
    anon = Respondente(pesquisa_id=p.id, entidade_tipo="empresa")  # pessoa_id NULL
    pessoa = Pessoa(tipo="interno_consentido", nome_display="Ana")
    db_session.add(pessoa)
    db_session.flush()
    ident = Respondente(pesquisa_id=p.id, pessoa_id=pessoa.id, entidade_tipo="local", entidade_id=7)
    db_session.add_all([anon, ident])
    db_session.commit()
    assert db_session.get(Respondente, anon.id).pessoa_id is None
    assert db_session.get(Respondente, ident.id).pessoa_id == pessoa.id


def test_respondente_escopo_tres_tipos(db_session):
    p, _ = _pesquisa(db_session, "EEscopo")
    for tipo, eid in [("empresa", None), ("agrupamento", 3), ("local", 9)]:
        db_session.add(Respondente(pesquisa_id=p.id, entidade_tipo=tipo, entidade_id=eid))
    db_session.commit()
    assert db_session.query(Respondente).filter_by(pesquisa_id=p.id).count() == 3


def test_respondente_escopo_invalido(db_session):
    p, _ = _pesquisa(db_session, "EEscopoInv")
    db_session.add(Respondente(pesquisa_id=p.id, entidade_tipo="regiao"))  # fora do CHECK
    with pytest.raises(IntegrityError):
        db_session.commit()


# ── Resposta ─────────────────────────────────────────────────────────────────


def test_resposta_valor_tipado(db_session):
    p, q = _pesquisa(db_session, "ERespost")
    r = Respondente(pesquisa_id=p.id, entidade_tipo="empresa")
    db_session.add(r)
    db_session.flush()
    db_session.add(
        Resposta(respondente_id=r.id, pergunta_id=q.id, valor_nota=5, valor_texto="Ótimo")
    )
    db_session.commit()
    resp = db_session.query(Resposta).one()
    assert resp.valor_nota == 5 and resp.valor_texto == "Ótimo" and resp.valor_opcao is None


def test_resposta_unique_respondente_pergunta(db_session):
    p, q = _pesquisa(db_session, "EUnique")
    r = Respondente(pesquisa_id=p.id, entidade_tipo="empresa")
    db_session.add(r)
    db_session.flush()
    db_session.add(Resposta(respondente_id=r.id, pergunta_id=q.id, valor_nota=4))
    db_session.commit()
    db_session.add(Resposta(respondente_id=r.id, pergunta_id=q.id, valor_nota=2))  # dup
    with pytest.raises(IntegrityError):
        db_session.commit()
