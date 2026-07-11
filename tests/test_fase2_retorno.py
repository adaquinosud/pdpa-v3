"""Tests do retorno de pesquisa (Fase 2 · Passo 4) — agregação por pergunta,
filtro de escopo, anonimato por linha, escala lida de opcoes_json."""

from __future__ import annotations

import json

from src.models.empresa import Empresa
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.pessoa import Pessoa
from src.models.respondente import Respondente, Resposta
from src.pesquisa.retorno import retorno_pesquisa


def _escala(pontos):
    return json.dumps(
        {"tipo": "nota", "pontos": pontos, "rotulos": [str(i) for i in range(1, pontos + 1)]}
    )


def _pesquisa(db_session, nome, anonima=True, pontos=5):
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="externa",
        proposito="confronto",
        titulo="Sat",
        status="pronta",
        anonima=anonima,
        entidade_tipo="empresa",
    )
    db_session.add(p)
    db_session.flush()
    qs = {
        "nota": PesquisaPergunta(
            pesquisa_id=p.id,
            ordem=1,
            enunciado="Nota?",
            formato="fechada",
            opcoes_json=_escala(pontos),
        ),
        "texto": PesquisaPergunta(pesquisa_id=p.id, ordem=2, enunciado="Comente", formato="aberta"),
        "mista": PesquisaPergunta(
            pesquisa_id=p.id,
            ordem=3,
            enunciado="Geral?",
            formato="mista",
            opcoes_json=_escala(pontos),
        ),
    }
    db_session.add_all(qs.values())
    db_session.flush()
    return p, qs


def _respondente(db_session, p, *, pessoa_id=None, entidade=("empresa", None), respostas=None):
    r = Respondente(
        pesquisa_id=p.id, pessoa_id=pessoa_id, entidade_tipo=entidade[0], entidade_id=entidade[1]
    )
    db_session.add(r)
    db_session.flush()
    for q, vals in (respostas or {}).items():
        db_session.add(Resposta(respondente_id=r.id, pergunta_id=q.id, **vals))
    db_session.flush()
    return r


def test_agrega_nota_texto_mista(db_session):
    p, qs = _pesquisa(db_session, "Eagg")
    _respondente(
        db_session,
        p,
        respostas={
            qs["nota"]: {"valor_nota": 5},
            qs["texto"]: {"valor_texto": "Ótimo"},
            qs["mista"]: {"valor_nota": 4, "valor_texto": "Bom"},
        },
    )
    _respondente(
        db_session,
        p,
        respostas={
            qs["nota"]: {"valor_nota": 3},
            qs["mista"]: {"valor_nota": 2},
        },
    )
    db_session.commit()
    ret = retorno_pesquisa(db_session, p.id)
    assert ret["total_respondentes"] == 2
    por_ordem = {q["ordem"]: q for q in ret["perguntas"]}
    # nota: média (5+3)/2 = 4.0; distribuição com bucket 5 e 3 = 1 cada
    assert por_ordem[1]["nota"]["media"] == 4.0
    dist = {b["valor"]: b["n"] for b in por_ordem[1]["nota"]["distribuicao"]}
    assert dist[5] == 1 and dist[3] == 1 and dist[1] == 0
    # texto: 1 comentário
    assert por_ordem[2]["comentarios"] == ["Ótimo"]
    # mista: média (4+2)/2 = 3.0 + comentário
    assert por_ordem[3]["nota"]["media"] == 3.0 and por_ordem[3]["comentarios"] == ["Bom"]


def test_escala_lida_de_opcoes(db_session):
    """Escala não é hardcoded 1-5 — vem de opcoes_json (pontos)."""
    p, qs = _pesquisa(db_session, "Eescala", pontos=10)
    _respondente(db_session, p, respostas={qs["nota"]: {"valor_nota": 9}})
    db_session.commit()
    ret = retorno_pesquisa(db_session, p.id)
    nota = ret["perguntas"][0]["nota"]
    assert nota["pontos"] == 10 and len(nota["distribuicao"]) == 10


def test_filtro_por_escopo(db_session):
    p, qs = _pesquisa(db_session, "Eescopo")
    _respondente(db_session, p, entidade=("local", 1), respostas={qs["nota"]: {"valor_nota": 5}})
    _respondente(db_session, p, entidade=("local", 2), respostas={qs["nota"]: {"valor_nota": 1}})
    db_session.commit()
    # sem filtro: 2 respondentes; escopos presentes = 2
    full = retorno_pesquisa(db_session, p.id)
    assert full["total_respondentes"] == 2 and len(full["escopos"]) == 2
    # filtrado por local 1: 1 respondente, média 5
    so1 = retorno_pesquisa(db_session, p.id, escopo=("local", 1))
    assert so1["total_respondentes"] == 1
    assert so1["perguntas"][0]["nota"]["media"] == 5.0


def test_anonimato_por_linha(db_session):
    # identificada: lista respondentes; anônimo por linha quando sem pessoa
    p, qs = _pesquisa(db_session, "Eident", anonima=False)
    pess = Pessoa(tipo="interno_consentido", nome_display="Ana")
    db_session.add(pess)
    db_session.flush()
    _respondente(db_session, p, pessoa_id=pess.id, respostas={qs["nota"]: {"valor_nota": 5}})
    _respondente(db_session, p, pessoa_id=None, respostas={qs["nota"]: {"valor_nota": 4}})
    db_session.commit()
    ret = retorno_pesquisa(db_session, p.id)
    nomes = sorted(r["nome"] for r in ret["respondentes"])
    assert nomes == ["Ana", "anônimo"]


def test_anonima_nao_lista_respondentes(db_session):
    p, qs = _pesquisa(db_session, "Eanon", anonima=True)
    _respondente(db_session, p, respostas={qs["nota"]: {"valor_nota": 5}})
    db_session.commit()
    ret = retorno_pesquisa(db_session, p.id)
    assert ret["respondentes"] is None  # anônima → só agregado


def test_pesquisa_sem_respostas(db_session):
    p, qs = _pesquisa(db_session, "Evazia")
    db_session.commit()
    ret = retorno_pesquisa(db_session, p.id)
    assert ret["total_respondentes"] == 0
    assert all(q["n_respostas"] == 0 for q in ret["perguntas"])
    assert ret["perguntas"][0]["nota"]["media"] is None


def test_rota_respostas(client_loyall, db_session):
    p, qs = _pesquisa(db_session, "Erota")
    _respondente(db_session, p, respostas={qs["nota"]: {"valor_nota": 5}})
    db_session.commit()
    r = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas/{p.id}/respostas")
    assert r.status_code == 200
    assert "Sat" in r.get_data(as_text=True)
