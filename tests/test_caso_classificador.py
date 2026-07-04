"""F3 — classificador de desfecho do Caso: determinístico + LLM p/ o ambíguo,
gatilho desfecho IS NULL, e as interações com coletor (zera na mudança de thread)
e expiry (abandona classificado parado)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from src.coletor import caso_classificador as cc
from src.coletor import reclame_aqui as ra
from src.models.caso import Caso
from src.models.empresa import Empresa

# reusa fixtures/payloads do teste do coletor (mesmo domínio)
from tests.test_reclame_aqui import _THREAD, _empresa_fonte, _patch_actor, _reclamacao


def _boom(payload):
    raise AssertionError("LLM não deveria ser chamado (caso determinístico)")


def _caso(db_session, e, f, origem_id="D1", **kw):
    c = Caso(empresa_id=e.id, fonte_id=f.id, origem_id=origem_id, **kw)
    db_session.add(c)
    db_session.flush()
    return c


# ── Determinístico (sem LLM) ─────────────────────────────────────────────────


def test_det_resolvido(db_session):
    e, f = _empresa_fonte(db_session)
    c = _caso(db_session, e, f, evaluated=True, solved=True, interactions_count=2, thread_json="[]")
    r = cc.classificar_caso(c, gerar_fn=_boom)
    assert r["desfecho"] == "resolvido" and r["causa_resolvida"] is True
    assert r["versao"] == cc.VERSAO_DET


def test_det_nao_resolvido(db_session):
    e, f = _empresa_fonte(db_session)
    c = _caso(
        db_session, e, f, evaluated=True, solved=False, interactions_count=2, thread_json="[]"
    )
    r = cc.classificar_caso(c, gerar_fn=_boom)
    assert r["desfecho"] == "nao_resolvido" and r["causa_resolvida"] is False


def test_det_nao_respondida(db_session):
    e, f = _empresa_fonte(db_session)
    c = _caso(db_session, e, f, evaluated=False, interactions_count=0, thread_json="[]")
    r = cc.classificar_caso(c, gerar_fn=_boom)
    assert r["desfecho"] == "nao_respondida"


# ── LLM (respondido, não avaliado) ───────────────────────────────────────────


def test_llm_desambigua_disputa(db_session):
    e, f = _empresa_fonte(db_session)
    c = _caso(
        db_session,
        e,
        f,
        evaluated=False,
        solved=False,
        status="ANSWERED",
        interactions_count=2,
        thread_json=json.dumps(_THREAD),
    )

    def fake(payload):
        assert payload["thread"] and payload["status"] == "ANSWERED"  # recebe a thread
        return {
            "desfecho": "respondida_em_disputa",
            "causa_resolvida": False,
            "justificativa": "réplica insatisfeita",
            "_in": 120,
            "_out": 30,
        }

    r = cc.classificar_caso(c, gerar_fn=fake)
    assert r["desfecho"] == "respondida_em_disputa" and r["causa_resolvida"] is False
    assert r["versao"] == cc.VERSAO_LLM and r["_in"] == 120


def test_llm_desfecho_invalido_cai_no_fallback(db_session):
    e, f = _empresa_fonte(db_session)
    c = _caso(
        db_session,
        e,
        f,
        evaluated=False,
        status="ANSWERED",
        interactions_count=1,
        thread_json=json.dumps(_THREAD),
    )
    r = cc.classificar_caso(
        c, gerar_fn=lambda p: {"desfecho": "inventado", "causa_resolvida": True}
    )
    assert r["desfecho"] == "respondida_sem_avaliacao"  # nunca deixa enum inválido


# ── gerar_desfecho_pendentes (gatilho desfecho IS NULL) ──────────────────────


def test_pendentes_so_processa_null(db_session):
    e, f = _empresa_fonte(db_session)
    _caso(
        db_session,
        e,
        f,
        origem_id="A",
        evaluated=True,
        solved=True,
        interactions_count=1,
        thread_json="[]",
    )
    _caso(
        db_session, e, f, origem_id="B", desfecho="resolvido", evaluated=True, solved=True
    )  # já classificado
    db_session.commit()
    stats = cc.gerar_desfecho_pendentes(f.id, gerar_fn=_boom)
    assert stats["analisados"] == 1 and stats["deterministico"] == 1
    db_session.expire_all()
    assert db_session.query(Caso).filter_by(origem_id="A").one().desfecho == "resolvido"


def test_desfecho_resiliente_um_caso_falha(db_session):
    """Um caso que estoura no LLM NÃO derruba o lote (nem faz rollback dos outros)
    — a causa dos 204 do Club Med ficarem NULL."""
    e, f = _empresa_fonte(db_session)
    # 2 casos ambíguos (respondido, não avaliado → LLM)
    _caso(
        db_session,
        e,
        f,
        origem_id="X1",
        evaluated=False,
        status="ANSWERED",
        interactions_count=1,
        thread_json=json.dumps(_THREAD),
    )
    _caso(
        db_session,
        e,
        f,
        origem_id="X2",
        evaluated=False,
        status="ANSWERED",
        interactions_count=1,
        thread_json=json.dumps(_THREAD),
    )
    db_session.commit()
    chamadas = {"n": 0}

    def _flaky(payload):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            raise RuntimeError("LLM caiu")
        return {
            "desfecho": "respondida_sem_avaliacao",
            "causa_resolvida": True,
            "justificativa": "x",
            "_in": 1,
            "_out": 1,
        }

    stats = cc.gerar_desfecho_pendentes(f.id, gerar_fn=_flaky)
    assert stats["erros"] == 1 and stats["analisados"] == 1  # 1 falhou, 1 classificou
    db_session.expire_all()
    desf = {c.origem_id: c.desfecho for c in db_session.query(Caso).filter_by(fonte_id=f.id)}
    # o que falhou segue NULL (retomável); o outro persistiu (sem rollback)
    assert None in desf.values() and "respondida_sem_avaliacao" in desf.values()


# ── Interações com coletor e expiry ──────────────────────────────────────────


def test_coletor_zera_desfecho_ao_mudar_thread(db_session, monkeypatch):
    e, f = _empresa_fonte(db_session)
    _patch_actor(monkeypatch, [_reclamacao("T1")])
    ra.coletar(f)
    cc.gerar_desfecho_pendentes(f.id, gerar_fn=_boom)  # PENDING → nao_respondida (det)
    db_session.expire_all()
    assert db_session.query(Caso).filter_by(origem_id="T1").one().desfecho == "nao_respondida"
    # recoleta (force) com thread nova → desfecho volta a NULL (re-classificar)
    _patch_actor(monkeypatch, [_reclamacao("T1", status="ANSWERED", interactions=_THREAD)])
    ra.coletar(f, force=True)
    db_session.expire_all()
    assert db_session.query(Caso).filter_by(origem_id="T1").one().desfecho is None


def test_expiry_abandona_classificado_parado(db_session):
    """Caso já classificado pelo F3 (não-abandonado) parado 90d → abandonado."""
    e, f = _empresa_fonte(db_session)
    agora = datetime(2026, 7, 3, 12, 0, 0)
    velho = agora - timedelta(days=100)
    db_session.add(
        Caso(
            empresa_id=e.id,
            fonte_id=f.id,
            origem_id="C1",
            evaluated=False,
            desfecho="respondida_sem_avaliacao",
            primeira_coleta=velho,
            thread_mudou_em=velho,
        )
    )
    db_session.commit()
    n = ra.expirar_abandonados(db_session, f.id, dias=90, agora=agora)
    db_session.commit()
    assert n == 1
    db_session.expire_all()
    assert db_session.query(Caso).filter_by(origem_id="C1").one().desfecho == "abandonado"


# ── F3.1: fio da pós-coleta ──────────────────────────────────────────────────


def test_poscoleta_wire_classifica_casos_ra(db_session):
    from src.temas.pos_coleta import _classificar_casos_ra

    e, f = _empresa_fonte(db_session)
    _caso(
        db_session,
        e,
        f,
        origem_id="W",
        evaluated=True,
        solved=True,
        interactions_count=1,
        thread_json="[]",
    )
    db_session.commit()
    r = _classificar_casos_ra(e.id)
    assert r == {"in": 0, "out": 0}  # determinístico → $0
    db_session.expire_all()
    assert db_session.query(Caso).filter_by(origem_id="W").one().desfecho == "resolvido"


def test_poscoleta_wire_noop_sem_ra(db_session):
    """Empresa sem fonte RA → no-op ($0, nenhuma query de caso)."""
    from src.temas.pos_coleta import _classificar_casos_ra

    e = Empresa(nome=f"SemRA-{id(db_session)}")
    db_session.add(e)
    db_session.commit()
    assert _classificar_casos_ra(e.id) == {"in": 0, "out": 0}
