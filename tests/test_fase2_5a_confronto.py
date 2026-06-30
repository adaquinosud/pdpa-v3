"""Tests do 5a — classificação da Resposta de confronto, sem tocar a base.

Fronteira inegociável: classifica na própria Resposta; NENHUM Verbatim criado;
base/ratio do cliente intocados. Lote ignora já-classificadas; coleta não entra.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.models.empresa import Empresa
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.respondente import Respondente, Resposta
from src.models.verbatim import Verbatim
from src.pesquisa.confronto import classificar_respostas_confronto


@pytest.fixture
def fake_classificar(monkeypatch):
    """Substitui classificar() por um fake puro (sem rede)."""
    chamadas = []

    def _fake(texto, **kw):
        chamadas.append(texto)
        return SimpleNamespace(
            subpilar="D2", tipo="detrator", confianca=0.91, prompt_versao="vtest"
        )

    monkeypatch.setattr("src.classifier.classifier_v3.classificar", _fake)
    return chamadas


def _resposta_confronto(db_session, *, proposito="confronto", texto="a gente resolve rápido"):
    e = Empresa(nome=f"E{id(texto)}")
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="interna",
        proposito=proposito,
        titulo="T",
        status="pronta",
        anonima=True,
        entidade_tipo="empresa",
    )
    db_session.add(p)
    db_session.flush()
    q = PesquisaPergunta(pesquisa_id=p.id, ordem=1, enunciado="Como foi?", formato="aberta")
    db_session.add(q)
    db_session.flush()
    r = Respondente(pesquisa_id=p.id, entidade_tipo="empresa")
    db_session.add(r)
    db_session.flush()
    resp = Resposta(respondente_id=r.id, pergunta_id=q.id, valor_texto=texto)
    db_session.add(resp)
    db_session.flush()
    return p, resp


def test_classifica_resposta_na_propria(db_session, fake_classificar):
    p, resp = _resposta_confronto(db_session)
    db_session.commit()
    stats = classificar_respostas_confronto(db_session, pesquisa_id=p.id)
    db_session.commit()
    assert stats["classificadas"] == 1
    got = db_session.get(Resposta, resp.id)
    assert got.subpilar_classificado == "D2" and got.valencia_classificada == "detrator"
    assert got.confianca_classificacao == 0.91 and got.classificado_em is not None


def test_nao_cria_verbatim_base_intocada(db_session, fake_classificar):
    p, resp = _resposta_confronto(db_session)
    db_session.commit()
    classificar_respostas_confronto(db_session, pesquisa_id=p.id)
    db_session.commit()
    assert db_session.query(Verbatim).count() == 0  # fronteira: nenhuma ponte


def test_lote_ignora_ja_classificadas(db_session, fake_classificar):
    p, resp = _resposta_confronto(db_session)
    db_session.commit()
    classificar_respostas_confronto(db_session, pesquisa_id=p.id)
    db_session.commit()
    stats2 = classificar_respostas_confronto(db_session, pesquisa_id=p.id)  # 2ª passada
    assert stats2["classificadas"] == 0  # já tem classificado_em


def test_coleta_nao_entra(db_session, fake_classificar):
    p, resp = _resposta_confronto(db_session, proposito="coleta")
    db_session.commit()
    stats = classificar_respostas_confronto(db_session, empresa_id=p.empresa_id)
    assert stats["classificadas"] == 0  # só 'confronto' entra
    assert db_session.get(Resposta, resp.id).classificado_em is None
