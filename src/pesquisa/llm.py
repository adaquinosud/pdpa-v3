"""Wrapper fino de LLM para a geração — reusa a infra do classificador.

Usa o client singleton, o retry (429/5xx) e o parser robusto (fence-strip +
reparo de JSON truncado) já endurecidos em ``classifier_v3``, com fallback para
o Sonnet quando o Haiku devolve JSON inválido. Mantém a geração isolada do
pipeline: só depende do classificador (LLM), nunca do coletor.

A geração injeta este ``gerar_via_llm`` como ``gerar_fn`` por padrão; em teste,
passa-se um fake (a chamada de rede nunca roda no CI).
"""

from __future__ import annotations

import json
from typing import Any, Dict

# Teto de saída da GERAÇÃO: N perguntas (enunciado+porque+opcoes) não cabem nos
# 2048 do classificador → JSON trunca (Unterminated string). 8192 dá folga p/ as
# até 20 perguntas do form (~250 tok/pergunta). O classificador segue em 2048.
_MAX_TOKENS_GERACAO = 8192


def _parse_json(raw: str) -> Dict[str, Any]:
    """Limpa fence de markdown e tenta json.loads; cai no reparo do classificador."""
    from src.classifier.classifier_v3 import (
        _FENCE_CLOSE,
        _FENCE_OPEN,
        _reparar_json_truncado,
    )

    cleaned = _FENCE_OPEN.sub("", raw)
    cleaned = _FENCE_CLOSE.sub("", cleaned).strip()
    try:
        return json.loads(cleaned)
    except (ValueError, TypeError):
        reparado = _reparar_json_truncado(cleaned)
        if reparado is None:
            raise
        return reparado


def _texto_da_resposta(resp) -> str:
    """Extrai o texto do primeiro bloco da Message do SDK."""
    return resp.content[0].text


def gerar_via_llm(system: str, user: str, temperature=None) -> Dict[str, Any]:
    """Chama o Haiku; em parse inválido, escala pro Sonnet. Devolve dict JSON.

    Reusa ``_call_claude_with_retry`` (retry 429/5xx) e os modelos do classifier.
    ``temperature`` (opcional): None = default do SDK; o ORIGEM passa um valor
    baixo p/ estabilizar a classificação de nível entre rodadas.
    """
    from src.classifier.classifier_v3 import HAIKU_MODEL, _call_claude_with_retry
    from src.config import get_config

    system_blocks = [{"type": "text", "text": system}]
    resp = _call_claude_with_retry(
        system_blocks, user, HAIKU_MODEL, _MAX_TOKENS_GERACAO, temperature=temperature
    )
    try:
        return _parse_json(_texto_da_resposta(resp))
    except (ValueError, TypeError):
        sonnet = getattr(get_config(), "CLASSIFIER_SONNET_MODEL", "claude-sonnet-4-5-20250929")
        resp = _call_claude_with_retry(
            system_blocks, user, sonnet, _MAX_TOKENS_GERACAO, temperature=temperature
        )
        return _parse_json(_texto_da_resposta(resp))
