"""Execução da sonda INVALIDADA sai da leitura sem virar "falhou" (§6.22).

Uma execução pode estar ``concluida`` — rodou e as IAs devolveram — e mesmo assim
não valer como medição. Foi o caso da BEXP: sondada pelo termo "Grupo BEXP", que o
§6.22.4 mediu como artefato (fintech, mineração, BMW/MINI).

⚠️ Por que coluna e não valor novo em ``status``: ``status`` é o CICLO DE VIDA da
máquina; ``valida`` é JULGAMENTO sobre o INSUMO. Marcar 'falhou' resolveria a
leitura pelo mecanismo certo — e escreveria estado FALSO com consumidor visível: a
aba passaria a dizer *"as IAs não retornaram"*, quando retornaram. É a classe de
defeito que esta sessão inteira caçou.
"""

from __future__ import annotations

from datetime import datetime

from src.models.empresa import Empresa
from src.models.sonda_ia import SondaIAExecucao
from src.ui import _explorar_reputacao_ia


def _empresa(db_session, sfx):
    e = Empresa(nome=f"ESI-{sfx}-{id(db_session)}")
    db_session.add(e)
    db_session.flush()
    return e


def _execucao(db_session, empresa_id, competencia="2026-09", **kw):
    kw.setdefault("status", "concluida")
    ex = SondaIAExecucao(empresa_id=empresa_id, competencia=competencia, **kw)
    db_session.add(ex)
    db_session.flush()
    return ex


def test_execucao_nasce_valida(db_session):
    """O default torna a migração NEUTRA: toda linha existente segue valendo."""
    e = _empresa(db_session, "default")
    ex = _execucao(db_session, e.id)
    db_session.commit()
    db_session.expire_all()
    assert db_session.get(SondaIAExecucao, ex.id).valida is True


def test_invalidada_sai_da_leitura(db_session):
    """É isto que faz o Parecer voltar a tratar a empresa como NÃO SONDADA."""
    e = _empresa(db_session, "saileitura")
    ex = _execucao(db_session, e.id)
    db_session.commit()
    r = _explorar_reputacao_ia(db_session, e.id)
    assert r.tem_dado is False or r.ultima_invalidada is False  # antes: entra na leitura

    ex.valida = False
    ex.invalidada_motivo = "termo = razão social"
    ex.invalidada_em = datetime.utcnow()
    db_session.commit()
    r2 = _explorar_reputacao_ia(db_session, e.id)
    assert r2.tem_dado is False


def test_invalidada_NAO_vira_falhou(db_session):
    """⚠️ O ponto da fatia inteira.

    A execução segue ``concluida`` — que é o que ela é — e a aba distingue os três
    vazios. Se ``ultima_falhou`` virasse True, a tela diria que as IAs não
    retornaram: estado falso, com consumidor visível.
    """
    e = _empresa(db_session, "naofalhou")
    ex = _execucao(db_session, e.id)
    ex.valida = False
    ex.invalidada_motivo = "termo = razão social (inferido do código)"
    db_session.commit()

    r = _explorar_reputacao_ia(db_session, e.id)
    assert r.tem_dado is False
    assert r.ultima_invalidada is True
    assert r.ultima_falhou is False, "invalidada NÃO é falha das IAs"
    assert r.ultima_motivo == "termo = razão social (inferido do código)"
    db_session.expire_all()
    assert db_session.get(SondaIAExecucao, ex.id).status == "concluida", "status INTOCADO"


def test_falhou_de_verdade_continua_falhou(db_session):
    """O caminho antigo não regride: falha real segue sendo falha real."""
    e = _empresa(db_session, "falhoumesmo")
    _execucao(db_session, e.id, status="falhou")
    db_session.commit()
    r = _explorar_reputacao_ia(db_session, e.id)
    assert r.tem_dado is False
    assert r.ultima_falhou is True
    assert r.ultima_invalidada is False


def test_execucao_valida_continua_sendo_lida(db_session):
    """Caminho FELIZ: sem este teste o filtro novo poderia estar suprimindo sempre.

    ⚠️ O discriminador não é ``tem_dado`` — uma execução sem respostas classificadas
    é ``False`` nos dois casos. O que separa "foi LIDA" de "foi FILTRADA" é o ramo:
    lida e sem conteúdo cai no caminho *degradada* pré-existente
    (``ui:5524-5533``), que força ``ultima_falhou=True``; filtrada cairia no
    ``execucao is None``, onde ``ultima_falhou`` seguiria o status ('concluida' →
    False). Então ``True`` aqui é a PROVA de que a execução válida chegou ao leitor.
    """
    e = _empresa(db_session, "valida")
    _execucao(db_session, e.id)
    db_session.commit()
    r = _explorar_reputacao_ia(db_session, e.id)
    assert r.ultima_invalidada is False
    assert r.ultima_falhou is True, "execução válida sem conteúdo = degradada, não filtrada"
