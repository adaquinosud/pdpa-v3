"""A abertura de RA volta íntegra — e o texto truncado é recuperável (§4.60.6).

Contexto medido em 03/set (run pago de US$ 0,03): com ``includeInteractions:false``
o actor NÃO abre a página da reclamação (``detailFetched=False``) e devolve o
``snippet`` da listagem — ~103 chars com reticências — no lugar da descrição. Junto
vem ``interactionsCount=0`` mesmo em reclamação ``ANSWERED``, o que faz
``caso_classificador.py:43-45`` gravar ``desfecho='nao_respondida'``
DETERMINISTICAMENTE. Não era a conversa que se perdia: era a abertura, que é o
verbatim do diagnóstico, e o contador que sustenta a leitura de conduta.

Três garantias aqui:
1. o input do actor pede a thread SEMPRE (a flag é a causa; custo não muda);
2. o guard de ``detailFetched`` conta em vez de deixar passar em silêncio (§9);
3. recoletar um caso EXISTENTE substitui o texto truncado — antes desta frente o
   verbatim só nascia no ramo ``caso is None``, então a recoleta pagava o run e
   deixava o texto pobre.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from src.coletor import reclame_aqui as ra
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim

SNIPPET = "Fui à concessionária Jeep no dia 18/07 para conhecer um Compass e fui muito bem at..."
INTEIRO = (
    "Fui à concessionária Jeep no dia 18/07 para conhecer um Compass e fui muito bem "
    "atendido pelo vendedor, mas na hora de fechar o financiamento apareceram taxas "
    "que ninguém tinha mencionado, e até hoje ninguém me retornou sobre a devolução "
    "do sinal que paguei."
)


def _item(origem_id="c1", texto=INTEIRO, detail=True, interactions=None, status="ANSWERED"):
    return {
        "recordType": "complaint",
        "id": origem_id,
        "title": "Cobrança indevida",
        "descriptionText": texto,
        "status": status,
        "statusLabel": "Respondida",
        "solved": False,
        "evaluated": False,
        "created": "2026-08-20T10:00:00.000Z",
        "detailFetched": detail,
        "interactions": interactions or [],
        "interactionsCount": len(interactions or []),
    }


@pytest.fixture()
def fonte_ra(db_session):
    e = Empresa(nome="EBexpRA")
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="local",
        entidade_id=1,
        conector_tipo="reclame_aqui",
        url="https://www.reclameaqui.com.br/bexp-jeep/",
        ativo=True,
        status="ativa",
        ra_modo="padrao",
        ra_max_casos=250,
    )
    db_session.add(f)
    db_session.flush()
    db_session.commit()
    return f


# ── 1. O input pede a thread nos DOIS modos ────────────────────────────────────


@pytest.mark.parametrize("modo", ["padrao", "completo"])
def test_input_pede_a_thread_em_qualquer_modo(db_session, fonte_ra, monkeypatch, modo):
    """A flag era a causa do truncamento — e o custo é o mesmo com ou sem thread."""
    fonte_ra.ra_modo = modo
    db_session.commit()
    capturado = {}

    def _fake(actor, run_input, timeout=None):
        capturado.update(run_input)
        return []

    monkeypatch.setattr(ra, "run_and_collect", _fake)
    ra.coletar_threads(fonte_ra, force=True)
    assert capturado["includeInteractions"] is True
    assert capturado["descriptionFormat"] == "text"


def test_cap_alto_avisa_e_ainda_traz_a_thread(db_session, fonte_ra, monkeypatch, caplog):
    """Acima do teto seguro NÃO degradamos para texto truncado — avisamos (§9)."""
    fonte_ra.ra_max_casos = ra.RA_CAP_THREAD_SEGURO + 500
    db_session.commit()
    capturado = {}

    def _fake(actor, run_input, timeout=None):
        capturado.update(run_input)
        return []

    monkeypatch.setattr(ra, "run_and_collect", _fake)
    with caplog.at_level("WARNING"):
        ra.coletar_threads(fonte_ra, force=True)
    assert capturado["includeInteractions"] is True  # nunca volta ao truncado
    assert "risco de memória" in caplog.text


# ── 2. O guard do detalhe ──────────────────────────────────────────────────────


def test_guard_conta_item_sem_detalhe_aberto(db_session, fonte_ra, monkeypatch, caplog):
    """detailFetched=False → conta e grita. Antes passava em silêncio."""
    monkeypatch.setattr(ra, "run_and_collect", lambda *a, **k: [_item("s1", SNIPPET, detail=False)])
    with caplog.at_level("WARNING"):
        stats = ra.coletar_threads(fonte_ra, force=True)
    assert stats["sem_detalhe"] == 1
    assert "detailFetched=False" in caplog.text


def test_detalhe_aberto_nao_conta(db_session, fonte_ra, monkeypatch):
    monkeypatch.setattr(ra, "run_and_collect", lambda *a, **k: [_item("s2", INTEIRO, detail=True)])
    stats = ra.coletar_threads(fonte_ra, force=True)
    assert stats["sem_detalhe"] == 0


def test_detalhe_ausente_nao_e_tratado_como_falso(db_session, fonte_ra, monkeypatch):
    """Campo ausente (versão futura do actor) ≠ detalhe fechado.

    Ausência de sinal não é sinal de ausência — senão uma mudança de schema do
    actor viraria alarme falso em todas as coletas.
    """
    item = _item("s3", INTEIRO)
    del item["detailFetched"]
    monkeypatch.setattr(ra, "run_and_collect", lambda *a, **k: [item])
    stats = ra.coletar_threads(fonte_ra, force=True)
    assert stats["sem_detalhe"] == 0


# ── 3. O upgrade do texto em caso JÁ EXISTENTE ─────────────────────────────────


def test_recoleta_substitui_texto_truncado_e_invalida(db_session, fonte_ra, monkeypatch):
    """O caminho feliz da recuperação, ponta a ponta.

    1ª coleta grava o snippet (o estado dos 55 da BEXP); a 2ª, com o texto inteiro,
    substitui e devolve o verbatim para a fila de classificação.
    """
    monkeypatch.setattr(ra, "run_and_collect", lambda *a, **k: [_item("c9", SNIPPET)])
    ra.coletar_threads(fonte_ra, force=True)
    db_session.expire_all()
    vb = db_session.query(Verbatim).filter_by(review_id_externo="c9").one()
    assert len(vb.texto) == len(SNIPPET)
    vb.subpilar = "Pa2"  # simula o classificador tendo lido o trecho
    db_session.commit()

    monkeypatch.setattr(ra, "run_and_collect", lambda *a, **k: [_item("c9", INTEIRO)])
    stats = ra.coletar_threads(fonte_ra, force=True)
    assert stats["textos_atualizados"] == 1
    db_session.expire_all()
    vb2 = db_session.query(Verbatim).filter_by(review_id_externo="c9").one()
    assert vb2.texto == INTEIRO
    assert vb2.subpilar is None, "texto novo com classificação velha é fóssil (§12)"
    assert vb2.reclassificado_em is not None, "ratios.py:115 recomputa pelos meses tocados"


def test_texto_menor_nao_sobrescreve_o_integro(db_session, fonte_ra, monkeypatch):
    """Só SOBE. Uma coleta futura que venha pobre não pode rebaixar o que já é bom."""
    monkeypatch.setattr(ra, "run_and_collect", lambda *a, **k: [_item("c8", INTEIRO)])
    ra.coletar_threads(fonte_ra, force=True)
    db_session.expire_all()
    db_session.query(Verbatim).filter_by(review_id_externo="c8").one().subpilar = "Pa2"
    db_session.commit()

    monkeypatch.setattr(ra, "run_and_collect", lambda *a, **k: [_item("c8", SNIPPET)])
    stats = ra.coletar_threads(fonte_ra, force=True)
    assert stats["textos_atualizados"] == 0
    db_session.expire_all()
    vb = db_session.query(Verbatim).filter_by(review_id_externo="c8").one()
    assert vb.texto == INTEIRO
    assert vb.subpilar == "Pa2", "sem troca de texto, a classificação não se invalida"


def test_upgrade_de_texto_nao_pula_o_reset_do_desfecho(db_session, fonte_ra, monkeypatch):
    """⚠️ Regressão travada: o upgrade sinaliza, não retorna cedo.

    O bloco que zera ``caso.desfecho`` (para o classificador re-derivar a conduta)
    vem DEPOIS do upgrade. Um ``return`` antecipado no upgrade deixaria de pé
    justamente a conduta fabricada que esta frente veio corrigir.
    """
    from src.models.caso import Caso

    monkeypatch.setattr(ra, "run_and_collect", lambda *a, **k: [_item("c7", SNIPPET)])
    ra.coletar_threads(fonte_ra, force=True)
    db_session.expire_all()
    caso = db_session.query(Caso).filter_by(origem_id="c7").one()
    caso.desfecho = "nao_respondida"  # o fóssil determinístico
    caso.ultima_coleta = datetime(2020, 1, 1)
    db_session.commit()

    inter = [{"type": "ANSWER", "author": "company", "message": "<p>Olá</p>"}]
    monkeypatch.setattr(
        ra, "run_and_collect", lambda *a, **k: [_item("c7", INTEIRO, interactions=inter)]
    )
    stats = ra.coletar_threads(fonte_ra, force=True)
    assert stats["textos_atualizados"] == 1
    db_session.expire_all()
    c2 = db_session.query(Caso).filter_by(origem_id="c7").one()
    assert c2.interactions_count == 1, "o contador real volta com a thread"
    assert c2.desfecho is None, "desfecho zerado → classificador re-deriva a conduta"
