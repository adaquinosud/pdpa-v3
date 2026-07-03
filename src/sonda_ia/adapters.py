"""Adapters por vendor da sonda de Reputação em IA — isolam cada SDK/API.

FRONTEIRA DE TROCA: trocar de modelo/vendor = mexer AQUI; o orquestrador
(sonda.py) não muda. Cada adapter recebe um ``prompt`` e devolve
``{vendor, modelo, texto, tokens_in, tokens_out}``.

CAP DE SAÍDA (``MAX_OUT_TOKENS``) + instrução de brevidade: o PoC G0 mostrou o
GPT-5 devolvendo ~4k tokens (reasoning verboso) — sem cap, custo e latência
explodem. O cap normaliza os 3 modelos e mantém as respostas comparáveis.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Dict

MAX_OUT_TOKENS = 500
BREVIDADE = "\n\nResponda de forma objetiva e concisa, em no máximo 120 palavras."

# Modelos consumer-facing (o que um usuário real recebe ao perguntar à IA).
CLAUDE_MODEL = "claude-sonnet-4-6"
GPT_MODEL = "gpt-5"
GEMINI_MODEL = "gemini-2.5-flash"

# preço por 1M tokens (in, out) — 2026 (ver docs da frente IA / PoC G0).
PRECO = {
    CLAUDE_MODEL: (3.0, 15.0),
    GPT_MODEL: (1.25, 10.0),
    GEMINI_MODEL: (0.30, 2.50),
}


def chamar_claude(prompt: str) -> Dict[str, Any]:
    from src.classifier.classifier_v3 import _get_client

    resp = _get_client().messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_OUT_TOKENS,
        messages=[{"role": "user", "content": prompt + BREVIDADE}],
    )
    texto = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    u = getattr(resp, "usage", None)
    return {
        "vendor": "claude",
        "modelo": CLAUDE_MODEL,
        "texto": texto,
        "tokens_in": int(getattr(u, "input_tokens", 0) or 0),
        "tokens_out": int(getattr(u, "output_tokens", 0) or 0),
    }


def chamar_gpt(prompt: str) -> Dict[str, Any]:
    # Via REST (o SDK openai 1.12 do projeto não conhece max_completion_tokens).
    # GPT-5 é reasoning: max_completion_tokens é o cap; reasoning_effort=low evita
    # o raciocínio consumir todo o cap e zerar o texto (achado do PoC G0).
    from src.config import get_config

    key = get_config().OPENAI_API_KEY
    if not key:
        raise ValueError("OPENAI_API_KEY não configurada (.env).")
    body = {
        "model": GPT_MODEL,
        "messages": [{"role": "user", "content": prompt + BREVIDADE}],
        "max_completion_tokens": MAX_OUT_TOKENS,
        "reasoning_effort": "low",
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    u = d.get("usage", {})
    return {
        "vendor": "gpt",
        "modelo": GPT_MODEL,
        "texto": (d["choices"][0]["message"].get("content") or ""),
        "tokens_in": int(u.get("prompt_tokens", 0) or 0),
        "tokens_out": int(u.get("completion_tokens", 0) or 0),
    }


def chamar_gemini(prompt: str) -> Dict[str, Any]:
    from src.config import get_config

    key = get_config().GOOGLE_API_KEY
    if not key:
        raise ValueError("GOOGLE_API_KEY não configurada (.env).")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={key}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt + BREVIDADE}]}],
        "generationConfig": {"maxOutputTokens": MAX_OUT_TOKENS},
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.load(r)
    cand = (d.get("candidates") or [{}])[0]
    parts = ((cand.get("content") or {}).get("parts")) or [{}]
    u = d.get("usageMetadata", {})
    return {
        "vendor": "gemini",
        "modelo": GEMINI_MODEL,
        "texto": parts[0].get("text", ""),
        "tokens_in": int(u.get("promptTokenCount", 0) or 0),
        "tokens_out": int(u.get("candidatesTokenCount", 0) or 0),
    }


ADAPTERS: Dict[str, Callable[[str], Dict[str, Any]]] = {
    "claude": chamar_claude,
    "gpt": chamar_gpt,
    "gemini": chamar_gemini,
}
