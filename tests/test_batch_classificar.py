"""Testes do caminho BATCH de ``classificar_pendentes`` (Anthropic Message Batches).

Mockam o client da Anthropic (``_get_client``) — zero chamada real. Cobrem:
succeeded válido, succeeded-mas-inválido→Passe 2, errored→Passe 2, baixa-confiança→
Passe 2, timeout (persiste batch_id + NULL), chunk-commit, fila vazia, reatamento
(não resubmete), métrica com custo a 50%, e o fallback serial (ENABLED=false).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.models.verbatim import Verbatim
from src.temas.pos_coleta import classificar_pendentes

# ── Fakes da Batch API ────────────────────────────────────────────────────

_USAGE = SimpleNamespace(
    input_tokens=10, output_tokens=5, cache_creation_input_tokens=0, cache_read_input_tokens=0
)


def _ok(sub="Pa1", tipo="promotor", conf=0.9):
    return f'{{"subpilar":"{sub}","tipo":"{tipo}","confianca":{conf},"justificativa_curta":"ok"}}'


ARRAY = '[{"subpilar":"Pa1","tipo":"promotor","confianca":0.9}]'  # JSON válido mas NÃO é objeto


def _entry(vid, type_, text=None, usage=None):
    msg = None
    if type_ == "succeeded":
        msg = SimpleNamespace(content=[SimpleNamespace(text=text)], usage=usage or _USAGE)
    return SimpleNamespace(custom_id=str(vid), result=SimpleNamespace(type=type_, message=msg))


class FakeBatches:
    """Batches scriptado: ids criados são 'batch_1', 'batch_2', ... em ordem."""

    def __init__(self, entries_by_id=None, status_by_id=None):
        self.entries_by_id = entries_by_id or {}
        self.status_by_id = status_by_id or {}
        self.created = []  # listas de requests, na ordem de create()
        self._retr = {}

    def create(self, requests):
        bid = f"batch_{len(self.created) + 1}"
        self.created.append(requests)
        return SimpleNamespace(id=bid)

    def retrieve(self, batch_id):
        st = self.status_by_id.get(batch_id, "ended")
        if isinstance(st, list):
            i = self._retr.get(batch_id, 0)
            self._retr[batch_id] = i + 1
            st = st[min(i, len(st) - 1)]
        return SimpleNamespace(processing_status=st)

    def results(self, batch_id):
        return iter(self.entries_by_id.get(batch_id, []))


def _client(batches):
    return SimpleNamespace(messages=SimpleNamespace(batches=batches))


# ── Setup (espelha test_temas_pos_coleta) ─────────────────────────────────


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"EBatch-{sfx}"}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ_b_{sfx}"},
    ).get_json()
    return e, loc, f


def _verb(db_session, empresa_id, fonte_id, local_id, texto):
    v = Verbatim(
        empresa_id=empresa_id,
        fonte_id=fonte_id,
        local_id=local_id,
        texto=texto,
        data_criacao_original=datetime.utcnow() - timedelta(days=2),
        hash_dedup=f"h-{texto}-{datetime.utcnow().timestamp()}",
        tem_texto=True,
    )
    db_session.add(v)
    db_session.commit()
    return v


# ── Testes ────────────────────────────────────────────────────────────────


def test_batch_succeeded_salva(client_loyall, db_session, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BATCH_ENABLED", "true")
    e, loc, f = _ctx(client_loyall, "ok")
    v1 = _verb(db_session, e["id"], f["id"], loc["id"], "atendimento otimo")
    v2 = _verb(db_session, e["id"], f["id"], loc["id"], "demorou muito pra atender")
    fb = FakeBatches(
        entries_by_id={
            "batch_1": [
                _entry(v1.id, "succeeded", _ok("Pa1", "promotor", 0.9)),
                _entry(v2.id, "succeeded", _ok("D2", "detrator", 0.85)),
            ]
        }
    )
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: _client(fb))
    stats = classificar_pendentes(e["id"])
    assert stats == {"classificados": 2, "falhas": 0}
    assert len(fb.created) == 1  # 1 batch Haiku submetido
    db_session.expire_all()
    assert db_session.get(Verbatim, v1.id).subpilar == "Pa1"
    assert db_session.get(Verbatim, v2.id).subpilar == "D2"


def test_batch_succeeded_invalido_vai_passe2(client_loyall, db_session, monkeypatch):
    """succeeded mas o conteúdo é array (não objeto) → Passe 2 (não salva lixo)."""
    monkeypatch.setenv("ANTHROPIC_BATCH_ENABLED", "true")
    e, loc, f = _ctx(client_loyall, "inv")
    v = _verb(db_session, e["id"], f["id"], loc["id"], "texto vago")
    fb = FakeBatches(entries_by_id={"batch_1": [_entry(v.id, "succeeded", ARRAY)]})
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: _client(fb))
    chamadas = {"n": 0}

    def fake_cls(**kw):
        chamadas["n"] += 1
        return SimpleNamespace(
            subpilar="Pa2",
            tipo="conversivel",
            confianca=0.7,
            justificativa="p2",
            prompt_versao="v3.1",
        )

    monkeypatch.setattr("src.classifier.classifier_v3.classificar", fake_cls)
    stats = classificar_pendentes(e["id"])
    assert chamadas["n"] == 1  # roteado ao Passe 2 serial
    assert stats["classificados"] == 1
    db_session.expire_all()
    assert db_session.get(Verbatim, v.id).subpilar == "Pa2"


def test_batch_errored_vai_passe2(client_loyall, db_session, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BATCH_ENABLED", "true")
    e, loc, f = _ctx(client_loyall, "err")
    v = _verb(db_session, e["id"], f["id"], loc["id"], "texto qualquer")
    fb = FakeBatches(entries_by_id={"batch_1": [_entry(v.id, "errored")]})
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: _client(fb))
    chamadas = {"n": 0}

    def fake_cls(**kw):
        chamadas["n"] += 1
        return SimpleNamespace(
            subpilar="P1", tipo="promotor", confianca=0.8, justificativa="ok", prompt_versao="v3.1"
        )

    monkeypatch.setattr("src.classifier.classifier_v3.classificar", fake_cls)
    classificar_pendentes(e["id"])
    assert chamadas["n"] == 1
    db_session.expire_all()
    assert db_session.get(Verbatim, v.id).subpilar == "P1"


def test_batch_baixa_confianca_vai_passe2(client_loyall, db_session, monkeypatch):
    """succeeded mas confiança < threshold → Passe 2 (escalada)."""
    monkeypatch.setenv("ANTHROPIC_BATCH_ENABLED", "true")
    e, loc, f = _ctx(client_loyall, "lc")
    v = _verb(db_session, e["id"], f["id"], loc["id"], "mais ou menos")
    fb = FakeBatches(
        entries_by_id={"batch_1": [_entry(v.id, "succeeded", _ok("Pa1", "conversivel", 0.3))]}
    )
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: _client(fb))
    chamadas = {"n": 0}

    def fake_cls(**kw):
        chamadas["n"] += 1
        return SimpleNamespace(
            subpilar="D3",
            tipo="detrator",
            confianca=0.9,
            justificativa="sonnet",
            prompt_versao="v3.1",
        )

    monkeypatch.setattr("src.classifier.classifier_v3.classificar", fake_cls)
    classificar_pendentes(e["id"])
    assert chamadas["n"] == 1  # baixa-confiança escalou via Passe 2
    db_session.expire_all()
    assert db_session.get(Verbatim, v.id).subpilar == "D3"


def test_batch_timeout_persiste_e_deixa_null(client_loyall, db_session, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BATCH_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_BATCH_TIMEOUT_MIN", "0")  # timeout imediato (sem sleep)
    e, loc, f = _ctx(client_loyall, "to")
    v = _verb(db_session, e["id"], f["id"], loc["id"], "texto")
    fb = FakeBatches(status_by_id={"batch_1": "in_progress"})  # nunca termina
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: _client(fb))
    stats = classificar_pendentes(e["id"])
    assert stats == {"classificados": 0, "falhas": 0}
    assert len(fb.created) == 1
    db_session.expire_all()
    assert db_session.get(Verbatim, v.id).subpilar is None  # NULL p/ retry
    from src.models.classificacao_batch import ClassificacaoBatch

    row = db_session.query(ClassificacaoBatch).filter_by(empresa_id=e["id"]).first()
    assert row is not None and row.batch_id == "batch_1" and row.status == "timeout"


def test_batch_fila_vazia_nao_submete(client_loyall, db_session, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BATCH_ENABLED", "true")
    e, loc, f = _ctx(client_loyall, "vazia")  # sem verbatins pendentes
    fb = FakeBatches()
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: _client(fb))
    stats = classificar_pendentes(e["id"])
    assert stats == {"classificados": 0, "falhas": 0}
    assert len(fb.created) == 0  # não submeteu batch vazio


def test_batch_chunk_commit(client_loyall, db_session, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BATCH_ENABLED", "true")
    e, loc, f = _ctx(client_loyall, "chunk")
    vs = [_verb(db_session, e["id"], f["id"], loc["id"], f"t{i}") for i in range(3)]
    fb = FakeBatches(
        entries_by_id={
            "batch_1": [_entry(v.id, "succeeded", _ok("Pa1", "promotor", 0.9)) for v in vs]
        }
    )
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: _client(fb))
    stats = classificar_pendentes(e["id"], chunk=2)  # commit no meio
    assert stats["classificados"] == 3
    db_session.expire_all()
    assert all(db_session.get(Verbatim, v.id).subpilar == "Pa1" for v in vs)


def test_fallback_serial_quando_desabilitado(client_loyall, db_session, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BATCH_ENABLED", "false")
    e, loc, f = _ctx(client_loyall, "ser")
    v = _verb(db_session, e["id"], f["id"], loc["id"], "atendimento")

    def _boom():
        raise AssertionError("batch não deveria ser usado com ENABLED=false")

    monkeypatch.setattr("src.classifier.classifier_v3._get_client", _boom)
    fake = SimpleNamespace(
        subpilar="D2", tipo="detrator", confianca=0.9, justificativa="serial", prompt_versao="v3.1"
    )
    monkeypatch.setattr("src.classifier.classifier_v3.classificar", lambda **kw: fake)
    stats = classificar_pendentes(e["id"])
    assert stats == {"classificados": 1, "falhas": 0}
    db_session.expire_all()
    assert db_session.get(Verbatim, v.id).subpilar == "D2"


def test_reatamento_nao_resubmete(client_loyall, db_session, monkeypatch):
    """Batch 'submitted' pré-existente é reatado e consumido — sem novo create()."""
    monkeypatch.setenv("ANTHROPIC_BATCH_ENABLED", "true")
    from src.classifier.classifier_v3 import HAIKU_MODEL
    from src.models.classificacao_batch import ClassificacaoBatch

    e, loc, f = _ctx(client_loyall, "reat")
    v = _verb(db_session, e["id"], f["id"], loc["id"], "texto reatado")
    db_session.add(
        ClassificacaoBatch(
            empresa_id=e["id"],
            batch_id="batch_old",
            modelo=HAIKU_MODEL,
            passe=1,
            status="submitted",
        )
    )
    db_session.commit()
    fb = FakeBatches(
        entries_by_id={"batch_old": [_entry(v.id, "succeeded", _ok("Pa1", "promotor", 0.9))]},
        status_by_id={"batch_old": "ended"},
    )
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: _client(fb))
    classificar_pendentes(e["id"])
    assert len(fb.created) == 0  # reatou, NÃO resubmeteu
    db_session.expire_all()
    assert db_session.get(Verbatim, v.id).subpilar == "Pa1"
    row = db_session.query(ClassificacaoBatch).filter_by(batch_id="batch_old").first()
    assert row.status == "processed"


def test_batch_registra_metrica_custo_50pct(client_loyall, db_session, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BATCH_ENABLED", "true")
    from src.classifier.classifier_v3 import HAIKU_MODEL, _calcular_custo

    e, loc, f = _ctx(client_loyall, "met")
    v = _verb(db_session, e["id"], f["id"], loc["id"], "atendimento otimo")
    fb = FakeBatches(
        entries_by_id={"batch_1": [_entry(v.id, "succeeded", _ok("Pa1", "promotor", 0.9))]}
    )
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: _client(fb))
    capturas = []
    monkeypatch.setattr(
        "src.classifier.classifier_v3._registrar_metrica",
        lambda modelo, pv, r, esc, mot, custo, lat, th: capturas.append((modelo, custo)),
    )
    classificar_pendentes(e["id"])
    assert len(capturas) == 1
    modelo, custo = capturas[0]
    assert modelo == HAIKU_MODEL
    esperado_batch = _calcular_custo(_USAGE, HAIKU_MODEL, batch=True)
    esperado_full = _calcular_custo(_USAGE, HAIKU_MODEL, batch=False)
    assert custo == pytest.approx(esperado_batch) and custo == pytest.approx(esperado_full * 0.5)
    assert custo > 0
