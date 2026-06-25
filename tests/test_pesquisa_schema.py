"""Tests do Motor de Pesquisa CP-F1.1: schema pesquisas + pesquisa_perguntas.

Schema aditivo e isolado — só valida persistência, defaults, relationship,
ordenação e cascade. Nada toca o pipeline.
"""

from __future__ import annotations

from src.models.pesquisa import Pesquisa, PesquisaPergunta


def _empresa(client_loyall, nome):
    return client_loyall.post("/api/empresas/", json={"nome": nome}).get_json()["id"]


def test_pesquisa_defaults(client_loyall, db_session):
    e = _empresa(client_loyall, "EPesqDef")
    p = Pesquisa(empresa_id=e, natureza="externa", titulo="Satisfação retirada")
    db_session.add(p)
    db_session.commit()
    got = db_session.query(Pesquisa).filter_by(empresa_id=e).one()
    # defaults da Fase 1
    assert got.escopo_local_modo == "local"
    assert got.status == "rascunho"
    assert got.versao == 1
    assert got.anonima is False
    assert got.canal is None
    assert got.criada_em is not None


def test_perguntas_relationship_ordenada(client_loyall, db_session):
    e = _empresa(client_loyall, "EPesqRel")
    p = Pesquisa(empresa_id=e, natureza="externa", titulo="T")
    db_session.add(p)
    db_session.commit()
    # inserção fora de ordem; relationship deve devolver por `ordem`
    db_session.add_all(
        [
            PesquisaPergunta(pesquisa_id=p.id, ordem=2, enunciado="Q2", formato="aberta"),
            PesquisaPergunta(
                pesquisa_id=p.id,
                ordem=1,
                enunciado="Q1",
                formato="fechada",
                subpilar_alvo="D2",
                opcoes_json='{"tipo":"nota","pontos":5}',
            ),
        ]
    )
    db_session.commit()
    db_session.refresh(p)
    assert [q.ordem for q in p.perguntas] == [1, 2]
    assert p.perguntas[0].subpilar_alvo == "D2"
    assert p.perguntas[1].gerada_por_ancora is False


def test_cascade_delete_perguntas(client_loyall, db_session):
    e = _empresa(client_loyall, "EPesqCascade")
    p = Pesquisa(empresa_id=e, natureza="interna", titulo="Interna")
    db_session.add(p)
    db_session.commit()
    db_session.add(PesquisaPergunta(pesquisa_id=p.id, ordem=1, enunciado="Q", formato="mista"))
    db_session.commit()
    pid = p.id
    db_session.delete(p)
    db_session.commit()
    assert db_session.query(PesquisaPergunta).filter_by(pesquisa_id=pid).count() == 0


def test_pergunta_porque_persistido(client_loyall, db_session):
    """porque (justificativa interna) é gravado — a regra 6 (não serializar ao
    respondente) é contrato do serializador da Fase 2, não do schema."""
    e = _empresa(client_loyall, "EPesqPorque")
    p = Pesquisa(empresa_id=e, natureza="externa", titulo="T")
    db_session.add(p)
    db_session.commit()
    db_session.add(
        PesquisaPergunta(
            pesquisa_id=p.id,
            ordem=1,
            enunciado="Como foi a retirada do veículo?",
            porque="D2 mostra ratio baixo persistente vs. lojas comparáveis",
            formato="aberta",
            subpilar_alvo="D2",
        )
    )
    db_session.commit()
    q = db_session.query(PesquisaPergunta).filter_by(pesquisa_id=p.id).one()
    assert q.porque.startswith("D2 mostra")
