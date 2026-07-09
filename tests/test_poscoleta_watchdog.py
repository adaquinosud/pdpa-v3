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


# ── regressão do self-deadlock: watchdog SEM wrap externo classifica subpilar ──
#
# O wrap externo `with _lock_empresa(eid)` no watchdog fazia a reaquisição interna
# do MESMO advisory lock (dentro de _classificar_pendentes_batch, sessão diferente)
# retornar False → o batch-classify pulava e subpilar ficava NULL (só no caminho
# batch; em SQLite o lock real é no-op, por isso a suíte não pegava). O stub abaixo
# emula a semântica sessão-escopada do Postgres p/ tornar a regressão observável.

from contextlib import contextmanager  # noqa: E402
from types import SimpleNamespace  # noqa: E402

_USAGE_B = SimpleNamespace(
    input_tokens=10, output_tokens=5, cache_creation_input_tokens=0, cache_read_input_tokens=0
)


def _entry_b(vid):
    text = '{"subpilar":"D2","tipo":"detrator","confianca":0.9,"justificativa_curta":"ok"}'
    msg = SimpleNamespace(content=[SimpleNamespace(text=text)], usage=_USAGE_B)
    return SimpleNamespace(
        custom_id=str(vid), result=SimpleNamespace(type="succeeded", message=msg)
    )


class _FakeBatchesB:
    def __init__(self, entries):
        self.entries = entries
        self.created = []

    def create(self, requests):
        self.created.append(requests)
        return SimpleNamespace(id=f"batch_{len(self.created)}")

    def retrieve(self, bid):
        return SimpleNamespace(processing_status="ended")

    def results(self, bid):
        return iter(self.entries.get(bid, []))


def _client_b(fb):
    return SimpleNamespace(messages=SimpleNamespace(batches=fb))


def _lock_reentrante():
    """Stub de _lock_empresa com a semântica sessão-escopada do Postgres: reaquisição
    da MESMA chave enquanto ainda retida → False (é o que o wrap externo do watchdog
    fazia ao batch-classify interno)."""
    held: set[int] = set()

    @contextmanager
    def _cm(empresa_id):
        key = int(empresa_id)
        if key in held:
            yield False
            return
        held.add(key)
        try:
            yield True
        finally:
            held.discard(key)

    return _cm


def test_watchdog_sem_lock_externo_classifica_subpilar(client_loyall, db_session, monkeypatch):
    """Com o wrap externo REMOVIDO, o watchdog classifica subpilar no caminho batch.

    Guarda a regressão: se alguém re-adicionar o `with _lock_empresa(eid)` no
    watchdog, o stub reentrante faz o batch-classify interno pegar False → subpilar
    fica NULL → este teste falha.
    """
    monkeypatch.setenv("ANTHROPIC_BATCH_ENABLED", "true")
    e = _empresa(db_session, "nolock")
    f = _fonte(db_session, e)
    # Caso desfecho NULL → trip do gate (deve_reprocessar) …
    db_session.add(Caso(empresa_id=e.id, fonte_id=f.id, origem_id="NL1", desfecho=None))
    # … e o verbatim de valência subpilar NULL que queremos ver classificado.
    v = _verb(db_session, e, f, subpilar=None, hd="nl-1")
    db_session.commit()

    monkeypatch.setattr("src.temas.pos_coleta._lock_empresa", _lock_reentrante())
    fb = _FakeBatchesB({"batch_1": [_entry_b(v.id)]})
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: _client_b(fb))
    # executar_pos_coleta REAL rodaria o pipeline inteiro; isolamos o passo que
    # deadlockava — delega à classificação real.
    from src.temas.pos_coleta import classificar_pendentes as _real_cp

    monkeypatch.setattr("src.temas.pos_coleta.executar_pos_coleta", lambda eid, **k: _real_cp(eid))

    wd.pos_coleta_watchdog(empresa_ids=[e.id])

    db_session.expire_all()
    assert db_session.get(Verbatim, v.id).subpilar == "D2"  # classificado no mesmo run
    assert len(fb.created) == 1
