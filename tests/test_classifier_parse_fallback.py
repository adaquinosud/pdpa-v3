"""Testes do fallback de parse Haiku→Sonnet (fix/parse-fallback-sonnet).

Cenário de produção: na reclassificação (empresa 16, dry-run v3.2→v3.3) o Haiku
devolvia o TIPO ``conversivel`` dentro do campo ``subpilar`` (que só aceita
A1..Pa3/sem_lastro). É modo de falha SISTEMÁTICO — rerolar o Haiku falha igual as
3 vezes — então o verbatim dava ``ValueError`` total (~15/831 no lote do Club Med).

Fix: quando o loop de parse/validação do Haiku esgota, escala pro Sonnet UMA vez
como fallback, antes de levantar. Sob os mesmos guard-rails da escalada-por-
confiança (kill-switch + teto de custo mensal).

Determinísticos e gratuitos: NÃO chamam a API. Mockam ``_classificar_com_modelo``
(a fronteira de 1 call por modelo) para simular Haiku inválido / Sonnet válido, e
``get_config`` para os knobs de escalada. Métricas (SQLite) são best-effort e
viram no-op fora de um banco real.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.classifier import classifier_v3
from src.classifier.classifier_v3 import (
    HAIKU_MODEL,
    ResultadoClassificacao,
    classificar,
)

SONNET_MODEL = "claude-sonnet-4-5-20250929"


def _config(*, escalada=True, budget=50.0, threshold=0.6):
    """Config-stub com os knobs de escalada que ``classificar`` consulta."""
    return SimpleNamespace(
        CLASSIFIER_ESCALATION_ENABLED=escalada,
        CLASSIFIER_ESCALATION_THRESHOLD=threshold,
        CLASSIFIER_MONTHLY_BUDGET_USD=budget,
        CLASSIFIER_SONNET_MODEL=SONNET_MODEL,
    )


def _resultado(modelo, subpilar="Pa1", tipo="promotor", confianca=0.9):
    return ResultadoClassificacao(
        subpilar=subpilar,
        tipo=tipo,
        confianca=confianca,
        justificativa="ok",
        modelo=modelo,
    )


@pytest.fixture(autouse=True)
def _isola(monkeypatch):
    """Desliga métrica/orçamento por padrão; cada teste sobrescreve o que precisa.

    ``_obter_gasto_mensal_sonnet=0`` (orçamento livre) e ``_registrar_metrica``
    no-op evitam tocar SQLite. ``get_config`` default = escalada ligada.
    """
    monkeypatch.setattr(classifier_v3, "_registrar_metrica", lambda **k: None)
    monkeypatch.setattr(classifier_v3, "_obter_gasto_mensal_sonnet", lambda: 0.0)
    monkeypatch.setattr(classifier_v3, "get_config", lambda: _config())


def _mock_por_modelo(monkeypatch, haiku_fn, sonnet_fn):
    """Roteia ``_classificar_com_modelo`` por modelo e conta chamadas.

    ``haiku_fn``/``sonnet_fn`` recebem o nº da chamada (1-based) àquele modelo e
    devolvem ``(resultado, custo, latencia)`` OU levantam (simulando parse inválido).
    Retorna o dict de contadores para asserção (ex.: garantir que Sonnet NÃO rodou).
    """
    chamadas = {HAIKU_MODEL: 0, SONNET_MODEL: 0}

    def fake(system_blocks, user_msg, modelo):
        chamadas[modelo] += 1
        fn = haiku_fn if modelo == HAIKU_MODEL else sonnet_fn
        return fn(chamadas[modelo])

    monkeypatch.setattr(classifier_v3, "_classificar_com_modelo", fake)
    return chamadas


def _haiku_sempre_invalido(_n):
    # Reproduz o bug: subpilar inválido → _parse_response levanta ValueError.
    raise ValueError("subpilar inválido: 'conversivel'. Esperado um de [...]")


# ── 1) Haiku esgota + Sonnet válido → usa Sonnet, escalado=True ──────────────
def test_haiku_esgota_sonnet_valido_usa_sonnet(monkeypatch):
    chamadas = _mock_por_modelo(
        monkeypatch,
        haiku_fn=_haiku_sempre_invalido,
        sonnet_fn=lambda _n: (
            _resultado(SONNET_MODEL, subpilar="A2", tipo="conversivel"),
            0.01,
            120,
        ),
    )
    r = classificar(texto="comida boa mas o preço subiu")

    assert r.modelo == SONNET_MODEL
    assert r.subpilar == "A2"
    assert r.escalado is True
    # Haiku rerolou as 3 vezes (modo sistemático); Sonnet rodou exatamente 1×.
    assert chamadas[HAIKU_MODEL] == classifier_v3.HAIKU_PARSE_RETRIES
    assert chamadas[SONNET_MODEL] == 1


# ── 2) Haiku esgota + Sonnet também inválido → raise sonnet_invalido ─────────
def test_haiku_esgota_sonnet_invalido_levanta(monkeypatch):
    chamadas = _mock_por_modelo(
        monkeypatch,
        haiku_fn=_haiku_sempre_invalido,
        sonnet_fn=lambda _n: (_ for _ in ()).throw(
            ValueError("subpilar inválido: 'conversivel'. Esperado um de [...]")
        ),
    )
    with pytest.raises(ValueError) as exc:
        classificar(texto="qualquer coisa ambígua")

    assert "parse_fallback_sonnet_invalido" in str(exc.value)
    assert chamadas[SONNET_MODEL] == 1  # tentou o Sonnet 1×


# ── 3) Haiku esgota + budget estourado → raise budget, SEM chamar Sonnet ─────
def test_haiku_esgota_budget_estourado_nao_chama_sonnet(monkeypatch):
    monkeypatch.setattr(classifier_v3, "_obter_gasto_mensal_sonnet", lambda: 999.0)
    chamadas = _mock_por_modelo(
        monkeypatch,
        haiku_fn=_haiku_sempre_invalido,
        sonnet_fn=lambda _n: pytest.fail("Sonnet NÃO deveria ser chamado com budget estourado"),
    )
    with pytest.raises(ValueError) as exc:
        classificar(texto="texto qualquer")

    assert "parse_fallback_budget_estourado" in str(exc.value)
    assert chamadas[SONNET_MODEL] == 0


# ── 4) Kill-switch off → raise, SEM chamar Sonnet (comportamento preservado) ─
def test_haiku_esgota_escalada_desligada_nao_chama_sonnet(monkeypatch):
    monkeypatch.setattr(classifier_v3, "get_config", lambda: _config(escalada=False))
    chamadas = _mock_por_modelo(
        monkeypatch,
        haiku_fn=_haiku_sempre_invalido,
        sonnet_fn=lambda _n: pytest.fail("Sonnet NÃO deveria ser chamado com escalada off"),
    )
    with pytest.raises(ValueError) as exc:
        classificar(texto="texto qualquer")

    assert "escalada desligada" in str(exc.value)
    assert chamadas[SONNET_MODEL] == 0


# ── 5) Caso transiente: reroll Haiku resolve, NÃO escala (caminho barato) ────
def test_transiente_reroll_haiku_resolve_sem_escalar(monkeypatch):
    """1ª chamada Haiku falha (JSON truncado), 2ª já volta válida — não escala."""

    def haiku_falha_uma_vez(n):
        if n == 1:
            raise ValueError("Resposta do classificador não é JSON válido: '{...'")
        return (_resultado(HAIKU_MODEL, subpilar="Pa1", tipo="promotor"), 0.001, 80)

    chamadas = _mock_por_modelo(
        monkeypatch,
        haiku_fn=haiku_falha_uma_vez,
        sonnet_fn=lambda _n: pytest.fail("Sonnet NÃO deveria rodar num caso transiente"),
    )
    r = classificar(texto="atendimento excelente")

    assert r.modelo == HAIKU_MODEL
    assert r.escalado is False
    assert chamadas[HAIKU_MODEL] == 2  # falhou 1×, resolveu na 2ª
    assert chamadas[SONNET_MODEL] == 0
