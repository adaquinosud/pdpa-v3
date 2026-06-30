"""Tests do wrapper LLM da geração (sem rede): garante o teto de saída maior
(8192) — N perguntas estouravam os 2048 do classificador → JSON truncado."""

from __future__ import annotations

import json
from types import SimpleNamespace

from src.pesquisa.llm import _MAX_TOKENS_GERACAO, gerar_via_llm


def _fake_resp(texto):
    return SimpleNamespace(content=[SimpleNamespace(text=texto)])


def test_geracao_passa_max_tokens_maior(monkeypatch):
    capturado = {}

    def _fake_call(system_blocks, user_msg, modelo, max_tokens=2048):
        capturado["max_tokens"] = max_tokens
        return _fake_resp(json.dumps({"perguntas": []}))

    monkeypatch.setattr("src.classifier.classifier_v3._call_claude_with_retry", _fake_call)
    gerar_via_llm("sys", "user")
    assert capturado["max_tokens"] == _MAX_TOKENS_GERACAO == 8192


def test_classificador_segue_em_2048():
    """O default de _call_claude_with_retry continua 2048 (classificação intocada)."""
    import inspect

    from src.classifier.classifier_v3 import MAX_TOKENS, _call_claude_with_retry

    assert MAX_TOKENS == 2048
    sig = inspect.signature(_call_claude_with_retry)
    assert sig.parameters["max_tokens"].default == MAX_TOKENS
