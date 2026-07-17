"""Pergunta de nota (fechada/mista) criada manualmente nasce com a ESCALA PADRÃO 1-5,
eliminando o aviso 'sem escala' (R4) na origem. Aberta segue sem escala."""

from __future__ import annotations

import json

from src.models.empresa import Empresa
from src.models.pesquisa import Pesquisa
from src.pesquisa.persistencia import adicionar_pergunta
from src.pesquisa.validador import checar_escala


def _pesq_vazia(db_session):
    e = Empresa(nome="EEscala")
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="interna",
        proposito="coleta",
        titulo="S",
        status="rascunho",
        anonima=False,
        entidade_tipo="empresa",
    )
    db_session.add(p)
    db_session.commit()
    return e, p


def test_mista_nasce_com_escala_padrao(db_session):
    _e, p = _pesq_vazia(db_session)
    q = adicionar_pergunta(db_session, p.id, enunciado="Como foi?", formato="mista")
    assert q.opcoes_json is not None
    opc = json.loads(q.opcoes_json)
    assert opc["tipo"] == "nota" and opc["pontos"] == 5
    assert checar_escala(opc) is None  # R4 passa → aviso 'sem escala' NÃO dispara


def test_fechada_nasce_com_escala_padrao(db_session):
    _e, p = _pesq_vazia(db_session)
    q = adicionar_pergunta(db_session, p.id, enunciado="Nota?", formato="fechada")
    assert q.opcoes_json is not None and checar_escala(json.loads(q.opcoes_json)) is None


def test_aberta_nao_recebe_escala(db_session):
    _e, p = _pesq_vazia(db_session)
    q = adicionar_pergunta(db_session, p.id, enunciado="Comente", formato="aberta")
    assert q.opcoes_json is None  # aberta não tem nota → sem escala


def test_opcoes_json_explicito_sobrepoe(db_session):
    """opcoes_json explícito (legado/override) tem precedência sobre o default."""
    _e, p = _pesq_vazia(db_session)
    custom = json.dumps({"tipo": "nota", "pontos": 5, "rotulos": ["a", "b", "c", "d", "e"]})
    q = adicionar_pergunta(db_session, p.id, enunciado="X", formato="mista", opcoes_json=custom)
    assert q.opcoes_json == custom


def test_rota_adicionar_mista_grava_escala(client_loyall, db_session):
    """Caminho real da tela: POST 'Adicionar pergunta' mista → nasce com escala."""
    _e, p = _pesq_vazia(db_session)
    from src.models.pesquisa import PesquisaPergunta

    client_loyall.post(
        f"/empresas/{p.empresa_id}/pesquisas/{p.id}/perguntas",
        data={"enunciado": "Como foi o atendimento?", "formato": "mista"},
    )
    q = db_session.query(PesquisaPergunta).filter_by(pesquisa_id=p.id).one()
    assert q.formato == "mista" and q.opcoes_json is not None
    assert checar_escala(json.loads(q.opcoes_json)) is None
