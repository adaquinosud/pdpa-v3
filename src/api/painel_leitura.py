"""Leitura textual sequencial do Lastro PDPA (Bloco 5 ext. CP-5).

Manual PDPA v3 Cap. 3: o Lastro é uma sequência evolutiva (P→D→Pa→A),
não 4 pilares paralelos. Esta função usa Claude Sonnet para produzir
2-3 frases identificando onde a relação travou e qual a alavanca de
intervenção, dado o estado atual do painel.

Sem cache no MVP — uma chamada por carregamento da página. Se volume
justificar, materializar via job + tabela painel_leitura_snapshot
(pendência em PENDENCIAS_TECNICAS.md).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional


PROMPT_PATH = Path(__file__).parent / "prompts" / "painel_leitura_sequencial.md"

SONNET_MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 300


_prompt_cache: Optional[str] = None


def _carregar_prompt() -> str:
    global _prompt_cache
    if _prompt_cache is None:
        _prompt_cache = PROMPT_PATH.read_text(encoding="utf-8")
    return _prompt_cache


def _strip_fence(s: str) -> str:
    s = re.sub(r"^\s*```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```\s*$", "", s)
    return s.strip()


def gerar_leitura_sequencial(n1_payload: Dict[str, Any]) -> str:
    """Devolve 2-3 frases interpretando o estado do Lastro.

    ``n1_payload`` é o JSON do endpoint /painel/nivel1 (com pilares +
    ratios + indice_geral + previsibilidade).

    Em caso de erro (Anthropic, parse, etc.), devolve mensagem placeholder
    em vez de levantar — UI sobrevive sem leitura.
    """
    if (n1_payload or {}).get("total_verbatins", 0) == 0:
        return (
            "Sem volume coletado no recorte atual — "
            "aprofunde a coleta para gerar leitura editorial."
        )

    try:
        from src.classifier.classifier_v3 import _get_client

        client = _get_client()
        system_prompt = _carregar_prompt()

        pilares_simples = {
            p["pilar"]: {
                "ratio": p["ratio"],
                "total": p["total"],
                "promotor": p["promotor"],
                "conversivel": p["conversivel"],
                "detrator": p["detrator"],
            }
            for p in n1_payload.get("pilares", [])
        }
        user_input = {
            "total_verbatins": n1_payload.get("total_verbatins", 0),
            "pilares": pilares_simples,
            "indice_geral": n1_payload.get("indice_geral", 0.0),
            "previsibilidade": n1_payload.get("previsibilidade", 0.0),
        }

        resposta = client.messages.create(
            model=SONNET_MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": json.dumps(user_input, ensure_ascii=False)}],
        )

        raw = "".join(
            block.text for block in resposta.content if getattr(block, "type", None) == "text"
        )
        raw = _strip_fence(raw)
        data = json.loads(raw)
        leitura = (data.get("leitura") or "").strip()
        if not leitura:
            return "Sem leitura editorial disponível neste momento."
        return leitura
    except Exception as exc:
        print(f"[painel_leitura] falha na geração: {type(exc).__name__}: {exc}")
        return "Sem leitura editorial disponível neste momento."
