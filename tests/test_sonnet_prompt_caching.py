"""Prova da trava do prompt caching (perf/sonnet-prompt-caching).

Mocka o client Anthropic, captura o payload enviado ao `messages.create`, e prova
que o TEXTO de system e user é BYTE-IDÊNTICO ao original — a única diferença permitida
é a presença de `cache_control`. Cobre cada call-path tocado (sugestões, anomalia,
parecer) E confirma que os deixados de fora (diagnóstico, casos, relatórios) seguem
com `system=<string>` pura, sem cache_control.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def rec(monkeypatch):
    """Captura os kwargs do messages.create; devolve o dict capturado (por chamada)."""
    captured: dict = {}

    def _create(**kwargs):
        captured.clear()
        captured.update(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"x": 1}')],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )

    client = SimpleNamespace(messages=SimpleNamespace(create=_create))
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: client)
    return captured


def _bloco_cacheado(sysarg, md_path):
    """Assert: system é UM bloco de texto com cache_control ephemeral e TEXTO ==
    conteúdo byte-idêntico do .md."""
    assert isinstance(sysarg, list) and len(sysarg) == 1
    blk = sysarg[0]
    assert blk["type"] == "text"
    assert blk["cache_control"] == {"type": "ephemeral"}
    assert blk["text"] == Path(md_path).read_text(encoding="utf-8")  # byte-idêntico


# ── cacheados (system ≥1024 tok) ──────────────────────────────────────


def test_sugestoes_cacheia_byte_identico(rec):
    from src.planos import sugestoes

    sugestoes._chamar_sonnet({"a": 1})
    _bloco_cacheado(rec["system"], sugestoes.PROMPT_PATH)
    # user inalterado (payload JSON), modelo e max_tokens inalterados
    assert rec["messages"][0]["content"] == json.dumps({"a": 1}, ensure_ascii=False)
    assert rec["model"] == sugestoes.SONNET_MODEL and rec["max_tokens"] == sugestoes.MAX_TOKENS


def test_editorial_anomalia_cacheia_byte_identico(rec):
    from src.anomalias import editorial

    editorial._chamar_sonnet({"a": 1}, cachear=True)  # default = leitura_anomalia_v1.md
    _bloco_cacheado(rec["system"], editorial.LEITURA_PROMPT_PATH)
    assert rec["messages"][0]["content"] == json.dumps({"a": 1}, ensure_ascii=False)


def test_editorial_parecer_prompt_cacheia_byte_identico(rec):
    from src.anomalias import editorial
    from src.relatorios.parecer import PROMPT_SINTESE

    editorial._chamar_sonnet({"a": 1}, PROMPT_SINTESE, cachear=True)
    _bloco_cacheado(rec["system"], PROMPT_SINTESE)


# ── deixados de fora (system < 1024 tok) — string pura, sem cache_control ──


def test_editorial_diagnostico_cacheia_byte_identico(rec):
    # medido em 1362 tok (count_tokens) → cacheável; o caller passa cachear=True.
    from src.anomalias import editorial
    from src.diagnostico.leituras import PROMPT_PATH as DIAG

    editorial._chamar_sonnet({"a": 1}, prompt_path=DIAG, cachear=True)
    _bloco_cacheado(rec["system"], DIAG)
    assert rec["messages"][0]["content"] == json.dumps({"a": 1}, ensure_ascii=False)


def test_editorial_casos_default_nao_cacheia(rec):
    from src.anomalias import editorial
    from src.coletor.caso_classificador import DESFECHO_PROMPT_PATH

    editorial._chamar_sonnet({"a": 1}, DESFECHO_PROMPT_PATH)  # cachear default False
    assert isinstance(rec["system"], str)
    assert rec["system"] == Path(DESFECHO_PROMPT_PATH).read_text(encoding="utf-8")


def test_llm_secoes_nao_cacheia(rec):
    from src.relatorios import llm_secoes

    llm_secoes._chamar_sonnet("RUBRICA FIXA DE RELATORIO", "payload", max_tokens=100)
    assert rec["system"] == "RUBRICA FIXA DE RELATORIO"  # string pura, intocada


# ── a diferença é SÓ o cache_control (mesmo prompt, texto idêntico) ────


def test_unica_diferenca_e_cache_control(rec):
    from src.anomalias import editorial

    editorial._chamar_sonnet({"a": 1}, editorial.LEITURA_PROMPT_PATH, cachear=True)
    cacheado = rec["system"]
    editorial._chamar_sonnet({"a": 1}, editorial.LEITURA_PROMPT_PATH, cachear=False)
    plano = rec["system"]
    assert cacheado[0]["text"] == plano  # TEXTO byte-idêntico
    assert "cache_control" in cacheado[0] and isinstance(plano, str)
