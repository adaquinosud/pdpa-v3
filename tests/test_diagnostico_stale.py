"""Régua canônica de staleness (Fatia 3) — dado stale conhecido, os consumidores concordam.

leitura_stale é a ÚNICA que recomputa o hash; aba Diagnóstico, impressos, IA e Plano
chamam-na. Testa a régua + o gate de bloqueio (impressos) + o selo (Plano).
"""

import pytest

from src.diagnostico.leituras import (
    _gargalo,
    agregar_subpilares,
    leitura_stale,
    montar_payload_subpilar,
    subpilares_stale,
)
from src.models.diagnostico import LeituraDiagnostico
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim
from src.utils.hashing import hash_payload


def _empresa(db_session):
    e = Empresa(nome="StaleCo")
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=1,
        conector_tipo="google",
        url="http://g",
    )
    db_session.add(f)
    db_session.flush()
    for _ in range(20):
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                texto="x",
                tem_texto=True,
                subpilar="Pa2",
                tipo="detrator",
                confianca=0.9,
            )
        )
    for _ in range(5):
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                texto="y",
                tem_texto=True,
                subpilar="Pa2",
                tipo="promotor",
                confianca=0.9,
            )
        )
    db_session.commit()
    return e


def _hash_vivo(db_session, e_id, sub):
    agg = agregar_subpilares(db_session, e_id)
    g = _gargalo(agg)
    return hash_payload(montar_payload_subpilar(db_session, e_id, None, sub, agg[sub], g))


def _leitura(db_session, e_id, sub, hash_val, acao="revisar a cobrança"):
    lt = LeituraDiagnostico(
        empresa_id=e_id, subpilar=sub, leitura="leitura antiga", acao=acao, dados_hash=hash_val
    )
    db_session.add(lt)
    db_session.commit()
    return lt


# ── A régua canônica ─────────────────────────────────────────────────────


def test_leitura_stale_canonica(db_session):
    e = _empresa(db_session)
    agg = agregar_subpilares(db_session, e.id)
    g = _gargalo(agg)
    lt = _leitura(db_session, e.id, "Pa2", _hash_vivo(db_session, e.id, "Pa2"))
    assert leitura_stale(db_session, lt, "Pa2", agg["Pa2"], g, e.id) is False  # hash bate
    lt.dados_hash = "hash_de_uma_base_antiga"
    db_session.commit()
    assert leitura_stale(db_session, lt, "Pa2", agg["Pa2"], g, e.id) is True  # diverge → stale
    assert leitura_stale(db_session, lt, "D1", None, g, e.id) is True  # órfã (sumiu do agg)
    lt.dados_hash = None
    db_session.commit()
    assert (
        leitura_stale(db_session, lt, "Pa2", agg["Pa2"], g, e.id) is False
    )  # sem hash → não comparável


def test_subpilares_stale_lista_ordenada(db_session):
    e = _empresa(db_session)
    _leitura(db_session, e.id, "Pa2", "hash_velho")
    assert subpilares_stale(db_session, e.id) == ["Pa2"]
    # com hash vivo, some da lista
    lt = db_session.query(LeituraDiagnostico).filter_by(empresa_id=e.id, subpilar="Pa2").first()
    lt.dados_hash = _hash_vivo(db_session, e.id, "Pa2")
    db_session.commit()
    assert subpilares_stale(db_session, e.id) == []


# ── Os consumidores concordam com a régua ────────────────────────────────


def test_impresso_bloqueia_com_leitura_stale(db_session):
    """Prioridade 1: o entregável impresso NÃO sai com leitura stale — bloqueia."""
    from src.relatorios.gates import bloquear_se_stale
    from src.relatorios.pdf import RelatorioBloqueado

    e = _empresa(db_session)
    _leitura(db_session, e.id, "Pa2", "hash_velho")
    with pytest.raises(RelatorioBloqueado) as exc:
        bloquear_se_stale(db_session, e.id, "StaleCo")
    msg = str(exc.value)
    assert "Pa2" in msg and "diagnostico-gerar" in msg  # quantos + comando de regen
    # tudo fresco → não bloqueia
    lt = db_session.query(LeituraDiagnostico).filter_by(empresa_id=e.id).first()
    lt.dados_hash = _hash_vivo(db_session, e.id, "Pa2")
    db_session.commit()
    bloquear_se_stale(db_session, e.id, "StaleCo")  # não levanta


def test_plano_marca_selo_stale(db_session):
    """Plano de Ação: a ação de diagnóstico com leitura defasada leva o selo."""
    from src.planos.consolidar import _itens_diagnostico

    e = _empresa(db_session)
    _leitura(db_session, e.id, "Pa2", "hash_velho", acao="revisar cobrança")
    itens = _itens_diagnostico(db_session, e.id)
    pa2 = next(i for i in itens if i.subpilar == "Pa2")
    assert pa2.stale is True
    # fresco → selo apaga
    lt = db_session.query(LeituraDiagnostico).filter_by(empresa_id=e.id).first()
    lt.dados_hash = _hash_vivo(db_session, e.id, "Pa2")
    db_session.commit()
    pa2b = next(i for i in _itens_diagnostico(db_session, e.id) if i.subpilar == "Pa2")
    assert pa2b.stale is False


def test_gate_por_acao_le_escopo_do_entregavel(db_session):
    """Fatia 3B: Plano Executivo e Parecer bloqueiam pelos PRÓPRIOS itens (consolidar),
    não por um escopo global. bloquear_se_acao_stale usa o item.stale já computado."""
    from src.planos.consolidar import _itens_diagnostico
    from src.relatorios.gates import bloquear_se_acao_stale
    from src.relatorios.pdf import RelatorioBloqueado

    e = _empresa(db_session)
    _leitura(db_session, e.id, "Pa2", "hash_velho", acao="revisar cobrança")
    itens = _itens_diagnostico(db_session, e.id)  # o que Plano Executivo/Parecer montam
    with pytest.raises(RelatorioBloqueado) as exc:
        bloquear_se_acao_stale(itens, e.id, "StaleCo")
    assert "Pa2" in str(exc.value) and "diagnostico-gerar" in str(exc.value)
    # fresco → não bloqueia (mesmo conjunto de itens)
    lt = db_session.query(LeituraDiagnostico).filter_by(empresa_id=e.id).first()
    lt.dados_hash = _hash_vivo(db_session, e.id, "Pa2")
    db_session.commit()
    bloquear_se_acao_stale(_itens_diagnostico(db_session, e.id), e.id, "StaleCo")  # não levanta


def test_consumidores_concordam_num_dado_stale(db_session):
    """O mesmo dado stale: régua True, lista o inclui, DOIS gates bloqueiam (leitura e
    ação), Plano marca. Nenhum consumidor de .acao que imprima/escreva fica de fora."""
    from src.planos.consolidar import _itens_diagnostico
    from src.relatorios.gates import bloquear_se_acao_stale, bloquear_se_stale
    from src.relatorios.pdf import RelatorioBloqueado

    e = _empresa(db_session)
    _leitura(db_session, e.id, "Pa2", "hash_velho", acao="revisar cobrança")
    agg = agregar_subpilares(db_session, e.id)
    lt = db_session.query(LeituraDiagnostico).filter_by(empresa_id=e.id).first()
    itens = _itens_diagnostico(db_session, e.id)
    # a régua (todos chamam a mesma)
    assert leitura_stale(db_session, lt, "Pa2", agg["Pa2"], _gargalo(agg), e.id) is True
    assert "Pa2" in subpilares_stale(db_session, e.id)
    assert next(i for i in itens if i.subpilar == "Pa2").stale  # Plano (selo)
    # gate dos que leem .leitura direto (Resumo Executivo, Diagnóstico Pontual)
    with pytest.raises(RelatorioBloqueado):
        bloquear_se_stale(db_session, e.id, "StaleCo")
    # gate dos que consomem via consolidar (Plano Executivo, Parecer)
    with pytest.raises(RelatorioBloqueado):
        bloquear_se_acao_stale(itens, e.id, "StaleCo")
