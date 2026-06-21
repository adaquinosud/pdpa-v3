"""Fidelidade de métrica do fallback de parse no apply via Batch (passe 2 Sonnet).

A correção (escalar reroll-item pro Sonnet) já existia; aqui só travamos o
``motivo_escalada`` em ``classifier_metrics``, alinhando o apply ao dry-run
(``_fallback_parse_sonnet``). Um reroll (subpilar inválido no passe 1) NÃO pode
poluir o sinal de ``confianca_baixa``.

Forçamos o ramo de fila grande do passe 2 (``_passe2_batch_sonnet`` →
``_consumir_passe2_sonnet`` / ``_passe2_sem_sonnet``) com
``ANTHROPIC_BATCH_PASS2_SERIAL_MAX=0`` — senão 1 item cairia no passe-2 serial,
que reusa ``classificar()`` (caminho já coberto pelo fix no dry-run).

Mockam o client da Anthropic (``_get_client``) e capturam ``_registrar_metrica``
— zero chamada real, zero SQLite.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from src.models.verbatim import Verbatim
from src.temas.pos_coleta import MARCADOR_FALHA_CLASSIFICACAO, classificar_pendentes

# ── Fakes da Batch API (espelham tests/test_batch_classificar.py) ──────────

_USAGE = SimpleNamespace(
    input_tokens=10, output_tokens=5, cache_creation_input_tokens=0, cache_read_input_tokens=0
)


def _json(sub, tipo="conversivel", conf=0.8):
    return f'{{"subpilar":"{sub}","tipo":"{tipo}","confianca":{conf},"justificativa_curta":"ok"}}'


# subpilar = um TIPO ("conversivel") → _parse_response levanta → reroll no passe 1.
_INVALIDO = _json("conversivel")


def _entry(vid, type_, text=None):
    msg = None
    if type_ == "succeeded":
        msg = SimpleNamespace(content=[SimpleNamespace(text=text)], usage=_USAGE)
    return SimpleNamespace(custom_id=str(vid), result=SimpleNamespace(type=type_, message=msg))


class FakeBatches:
    """Batches scriptado: ids criados são 'batch_1', 'batch_2', ... em ordem."""

    def __init__(self, entries_by_id=None):
        self.entries_by_id = entries_by_id or {}
        self.created = []

    def create(self, requests):
        bid = f"batch_{len(self.created) + 1}"
        self.created.append(requests)
        return SimpleNamespace(id=bid)

    def retrieve(self, batch_id):
        return SimpleNamespace(processing_status="ended")

    def results(self, batch_id):
        return iter(self.entries_by_id.get(batch_id, []))


def _client(batches):
    return SimpleNamespace(messages=SimpleNamespace(batches=batches))


# ── Setup ──────────────────────────────────────────────────────────────────


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"EMet-{sfx}"}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ_m_{sfx}"},
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


def _forcar_passe2_batch(monkeypatch):
    """Liga o Batch e força o ramo de fila grande do passe 2 (Sonnet batch)."""
    monkeypatch.setenv("ANTHROPIC_BATCH_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_BATCH_PASS2_SERIAL_MAX", "0")


def _capturar_metricas(monkeypatch):
    """Captura (modelo, motivo) de cada _registrar_metrica. Retorna a lista."""
    capturas = []
    monkeypatch.setattr(
        "src.classifier.classifier_v3._registrar_metrica",
        lambda modelo, pv, r, esc, mot, custo, lat, th: capturas.append((modelo, mot)),
    )
    return capturas


def _gasto(monkeypatch, valor):
    monkeypatch.setattr("src.classifier.classifier_v3._obter_gasto_mensal_sonnet", lambda: valor)


# ── 1) reroll escala pro Sonnet, Sonnet válido → motivo "parse_fallback" ─────
def test_reroll_sonnet_valido_motivo_parse_fallback(client_loyall, db_session, monkeypatch):
    _forcar_passe2_batch(monkeypatch)
    _gasto(monkeypatch, 0.0)  # orçamento livre
    e, loc, f = _ctx(client_loyall, "ok")
    v = _verb(db_session, e["id"], f["id"], loc["id"], "estrutura boa mas atendimento")
    fb = FakeBatches(
        entries_by_id={
            "batch_1": [_entry(v.id, "succeeded", _INVALIDO)],  # Haiku põe TIPO no subpilar
            "batch_2": [_entry(v.id, "succeeded", _json("A2", "conversivel", 0.8))],  # Sonnet OK
        }
    )
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: _client(fb))
    capturas = _capturar_metricas(monkeypatch)

    stats = classificar_pendentes(e["id"])

    assert stats["classificados"] == 1
    db_session.expire_all()
    assert db_session.get(Verbatim, v.id).subpilar == "A2"
    motivos = [m for _, m in capturas]
    assert "parse_fallback" in motivos
    assert "confianca_baixa" not in motivos  # reroll NÃO polui o sinal de confiança


# ── 2) reroll, Sonnet TAMBÉM inválido → "parse_fallback_sonnet_invalido" ─────
def test_reroll_sonnet_invalido_motivo_sonnet_invalido(client_loyall, db_session, monkeypatch):
    _forcar_passe2_batch(monkeypatch)
    _gasto(monkeypatch, 0.0)
    e, loc, f = _ctx(client_loyall, "si")
    v = _verb(db_session, e["id"], f["id"], loc["id"], "texto ambíguo")
    fb = FakeBatches(
        entries_by_id={
            "batch_1": [_entry(v.id, "succeeded", _INVALIDO)],
            "batch_2": [_entry(v.id, "succeeded", _INVALIDO)],  # Sonnet também inválido
        }
    )
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: _client(fb))
    capturas = _capturar_metricas(monkeypatch)

    stats = classificar_pendentes(e["id"])

    assert stats["falhas"] == 1
    db_session.expire_all()
    vv = db_session.get(Verbatim, v.id)
    assert vv.prompt_versao == MARCADOR_FALHA_CLASSIFICACAO  # terminal
    motivos = [m for _, m in capturas]
    assert "parse_fallback_sonnet_invalido" in motivos


# ── 3) reroll, teto estourado → "parse_fallback_budget_estourado", sem Sonnet ─
def test_reroll_budget_estourado_motivo_budget_sem_sonnet(client_loyall, db_session, monkeypatch):
    _forcar_passe2_batch(monkeypatch)
    _gasto(monkeypatch, 999.0)  # teto mensal estourado (> default 50)
    e, loc, f = _ctx(client_loyall, "bud")
    v = _verb(db_session, e["id"], f["id"], loc["id"], "texto qualquer")
    fb = FakeBatches(entries_by_id={"batch_1": [_entry(v.id, "succeeded", _INVALIDO)]})
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: _client(fb))
    capturas = _capturar_metricas(monkeypatch)

    stats = classificar_pendentes(e["id"])

    assert stats["falhas"] == 1
    assert len(fb.created) == 1  # só o batch Haiku do passe 1 — NÃO submeteu Sonnet
    db_session.expire_all()
    assert db_session.get(Verbatim, v.id).prompt_versao == MARCADOR_FALHA_CLASSIFICACAO
    motivos = [m for _, m in capturas]
    assert "parse_fallback_budget_estourado" in motivos


# ── 4) Guard: kill-switch off ≠ teto → NÃO emite parse_fallback (espelha dry-run) ─
def test_reroll_killswitch_off_nao_emite_parse_fallback(client_loyall, db_session, monkeypatch):
    _forcar_passe2_batch(monkeypatch)
    _gasto(monkeypatch, 0.0)  # orçamento livre — o bloqueio é o kill-switch, não o teto
    monkeypatch.setattr(
        "src.config.get_config",
        lambda: SimpleNamespace(
            CLASSIFIER_ESCALATION_ENABLED=False,
            CLASSIFIER_MONTHLY_BUDGET_USD=50.0,
            CLASSIFIER_SONNET_MODEL="claude-sonnet-4-5-20250929",
        ),
    )
    e, loc, f = _ctx(client_loyall, "ks")
    v = _verb(db_session, e["id"], f["id"], loc["id"], "texto qualquer")
    fb = FakeBatches(entries_by_id={"batch_1": [_entry(v.id, "succeeded", _INVALIDO)]})
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: _client(fb))
    capturas = _capturar_metricas(monkeypatch)

    stats = classificar_pendentes(e["id"])

    assert stats["falhas"] == 1
    assert len(fb.created) == 1  # sem Sonnet
    db_session.expire_all()
    assert db_session.get(Verbatim, v.id).prompt_versao == MARCADOR_FALHA_CLASSIFICACAO
    motivos = [m for _, m in capturas]
    # kill-switch off NÃO gera métrica de parse_fallback (só o teto gera) — mirror do dry-run.
    assert not any(m and m.startswith("parse_fallback") for m in motivos)
