"""Sugestão heurística de tema_declarado a partir do enunciado (sem LLM)."""

from __future__ import annotations

from src.models.empresa import Empresa
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.pesquisa.persistencia import adicionar_pergunta, atualizar_pergunta
from src.pesquisa.tema_sugestao import sugerir_tema


def test_heuristica_remove_prefixo_interrogativo():
    assert sugerir_tema("Como você avalia a qualidade do atendimento telefônico?") == (
        "Qualidade do atendimento telefônico"
    )
    assert sugerir_tema("O que você acha do prazo de entrega?") == "Prazo de entrega"
    assert sugerir_tema("Qual sua opinião sobre o tempo de espera na fila?") == (
        "Tempo de espera na fila"
    )
    assert sugerir_tema("Qual seu nível de satisfação com o suporte pós-venda?") == (
        "Suporte pós-venda"
    )


def test_heuristica_bordas():
    assert sugerir_tema("") is None
    assert sugerir_tema(None) is None
    assert sugerir_tema("   ?  ") is None
    assert sugerir_tema("Preço") == "Preço"  # sem prefixo → mantém
    # miolo preservado (não arranca stopword do meio)
    assert "de entrega" in sugerir_tema("O prazo de entrega foi bom?")


def _pesq(db_session):
    e = Empresa(nome="Esg")
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="externa",
        proposito="coleta",
        titulo="P",
        status="rascunho",
        anonima=False,
        entidade_tipo="empresa",
    )
    db_session.add(p)
    db_session.flush()
    return p


def test_adicionar_pergunta_sugere_tema(db_session):
    p = _pesq(db_session)
    q = adicionar_pergunta(
        db_session, p.id, enunciado="Como você avalia o tempo de espera?", formato="mista"
    )
    assert q.tema_declarado == "Tempo de espera"


def test_editar_enunciado_sugere_quando_tema_vazio(db_session):
    p = _pesq(db_session)
    q = PesquisaPergunta(pesquisa_id=p.id, ordem=1, enunciado="Antigo?", formato="aberta")
    db_session.add(q)
    db_session.flush()
    atualizar_pergunta(db_session, q.id, enunciado="O que você acha do prazo de entrega?")
    db_session.flush()
    assert q.tema_declarado == "Prazo de entrega"


def test_editar_enunciado_nao_sobrescreve_tema_preenchido(db_session):
    p = _pesq(db_session)
    q = PesquisaPergunta(
        pesquisa_id=p.id, ordem=1, enunciado="X?", formato="aberta", tema_declarado="Meu tema"
    )
    db_session.add(q)
    db_session.flush()
    atualizar_pergunta(db_session, q.id, enunciado="Como você avalia o atendimento?")
    db_session.flush()
    assert q.tema_declarado == "Meu tema"  # não mexe no que o operador já definiu
