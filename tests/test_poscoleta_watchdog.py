"""CP-poscoleta-watchdog: detector de pendências + gate por pendência + watchdog
auto-retomável (lock + cooldown + status). LLM/pipeline stubado — zero gasto."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.models.caso import Caso
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.temas import VerbatimEmbedding
from src.models.verbatim import Verbatim
from src.temas import watchdog as wd


def _empresa(db_session, sfx):
    e = Empresa(nome=f"EWD-{sfx}-{id(db_session)}")
    db_session.add(e)
    db_session.flush()
    return e


def _fonte(db_session, e):
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="reclame_aqui",
        url="https://www.reclameaqui.com.br/x/",
        status="ativa",
    )
    db_session.add(f)
    db_session.flush()
    return f


def _verb(db_session, e, f, *, subpilar, hd, embedding=False):
    v = Verbatim(
        empresa_id=e.id,
        fonte_id=f.id,
        texto="t",
        tem_texto=True,
        subpilar=subpilar,
        tipo="detrator" if subpilar else None,
        hash_dedup=hd,
    )
    db_session.add(v)
    db_session.flush()
    if embedding:
        db_session.add(VerbatimEmbedding(verbatim_id=v.id, modelo=wd_MODELO(), vetor=b"\x00\x00"))
        db_session.flush()
    return v


def wd_MODELO():
    from src.temas.embeddings import MODELO_PADRAO

    return MODELO_PADRAO


# ── detector ──────────────────────────────────────────────────────────────


def test_pendencias_conta_certo(db_session):
    e = _empresa(db_session, "det")
    f = _fonte(db_session, e)
    _verb(db_session, e, f, subpilar=None, hd="a")  # subpilar_null + sem embedding
    _verb(db_session, e, f, subpilar="D2", hd="b", embedding=True)  # completo
    db_session.add(Caso(empresa_id=e.id, fonte_id=f.id, origem_id="C1", desfecho=None))
    db_session.add(Caso(empresa_id=e.id, fonte_id=f.id, origem_id="C2", desfecho="resolvido"))
    db_session.commit()

    p = wd.pendencias_pos_coleta(e.id)
    assert p["subpilar_null"] == 1
    assert p["desfecho_null"] == 1  # só o C1
    assert p["embeddings_faltando"] == 1  # só o verbatim sem embedding
    assert p["cache_defasado"] is False  # sem cache nem vínculos → 0 == 0


# ── threshold ───────────────────────────────────────────────────────────────


def test_deve_reprocessar_desfecho_excecao():
    assert wd.deve_reprocessar({"desfecho_null": 1}) is True  # ≥1 desfecho dispara


def test_deve_reprocessar_volume_threshold():
    assert wd.deve_reprocessar({"subpilar_null": 4, "embeddings_faltando": 0}) is False
    assert wd.deve_reprocessar({"subpilar_null": 3, "embeddings_faltando": 2}) is True  # =5
    assert wd.deve_reprocessar({}) is False


# ── watchdog ────────────────────────────────────────────────────────────────


def _stub_pipeline(monkeypatch):
    """Stub de executar_pos_coleta: registra chamadas, não roda LLM."""
    chamadas = []
    monkeypatch.setattr(
        "src.temas.pos_coleta.executar_pos_coleta",
        lambda eid, **k: chamadas.append(eid),
    )
    return chamadas


def test_watchdog_retoma_empresa_com_desfecho(db_session, monkeypatch):
    e = _empresa(db_session, "ret")
    f = _fonte(db_session, e)
    db_session.add(Caso(empresa_id=e.id, fonte_id=f.id, origem_id="R1", desfecho=None))
    db_session.commit()
    chamadas = _stub_pipeline(monkeypatch)

    stats = wd.pos_coleta_watchdog(empresa_ids=[e.id])
    assert chamadas == [e.id] and stats["retomadas"] == 1
    db_session.expire_all()
    assert db_session.get(Empresa, e.id).pos_coleta_status == "completo"


def test_watchdog_limpa_e_noop(db_session, monkeypatch):
    e = _empresa(db_session, "limpa")
    f = _fonte(db_session, e)
    _verb(db_session, e, f, subpilar="D2", hd="ok", embedding=True)  # nada pendente
    db_session.commit()
    chamadas = _stub_pipeline(monkeypatch)

    stats = wd.pos_coleta_watchdog(empresa_ids=[e.id])
    assert chamadas == [] and stats["limpas"] == 1
    db_session.expire_all()
    assert db_session.get(Empresa, e.id).pos_coleta_status == "completo"


def test_watchdog_cooldown_pula(db_session, monkeypatch):
    e = _empresa(db_session, "cd")
    f = _fonte(db_session, e)
    db_session.add(Caso(empresa_id=e.id, fonte_id=f.id, origem_id="CD1", desfecho=None))
    e.pos_coleta_status = "completo"
    e.pos_coleta_iniciado_em = datetime.utcnow()  # rodou agora → dentro do cooldown
    db_session.commit()
    chamadas = _stub_pipeline(monkeypatch)

    stats = wd.pos_coleta_watchdog(empresa_ids=[e.id])
    assert chamadas == [] and stats["puladas_cooldown"] == 1


def test_watchdog_marca_interrompido(db_session, monkeypatch):
    e = _empresa(db_session, "int")
    f = _fonte(db_session, e)
    db_session.add(Caso(empresa_id=e.id, fonte_id=f.id, origem_id="I1", desfecho=None))
    e.pos_coleta_status = "rodando"
    e.pos_coleta_iniciado_em = datetime.utcnow() - timedelta(hours=9)  # 'rodando' velho
    db_session.commit()
    chamadas = _stub_pipeline(monkeypatch)

    stats = wd.pos_coleta_watchdog(empresa_ids=[e.id])
    assert stats["interrompidas"] == 1 and chamadas == [e.id]  # marca e retoma


# ── gate por pendência em executar_pos_coleta ────────────────────────────────


class _Sentinel(Exception):
    pass


def test_gate_pula_quando_limpo(db_session, monkeypatch):
    """Empresa limpa, novos=0, sem force → PULA (nem chega na classificação)."""
    from src.temas import pos_coleta as pc

    e = _empresa(db_session, "gpula")
    db_session.commit()
    monkeypatch.setattr(
        pc, "classificar_pendentes", lambda *a, **k: (_ for _ in ()).throw(_Sentinel())
    )
    r = pc.executar_pos_coleta(e.id, limiar=5, force=False)
    assert not r.executou and "pulando" in r.motivo_skip


def test_gate_nao_pula_com_desfecho_pendente(db_session, monkeypatch):
    """Desfecho pendente (novos=0) → NÃO pula: passa do gate e chega na classificação."""
    from src.temas import pos_coleta as pc

    e = _empresa(db_session, "gnp")
    f = _fonte(db_session, e)
    db_session.add(Caso(empresa_id=e.id, fonte_id=f.id, origem_id="G1", desfecho=None))
    db_session.commit()
    monkeypatch.setattr(
        pc, "classificar_pendentes", lambda *a, **k: (_ for _ in ()).throw(_Sentinel())
    )
    with pytest.raises(_Sentinel):
        pc.executar_pos_coleta(e.id, limiar=5, force=False)
