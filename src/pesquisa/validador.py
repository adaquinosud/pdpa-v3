"""Validador da régua de neutralidade — SEAM (F1.2) + contrato.

Nesta sub-CP (F1.2) só existe o **encaixe** e o **contrato de retorno**: a
geração já passa pelo validador antes de exibir. As checagens reais entram nas
próximas sub-CPs, sem mudar a assinatura:
 - F1.3: camada determinística (R5 blocklist, R3 pré-filtro, R4 schema da escala).
 - F1.4: camada LLM-juiz (R1, R2, R7) reusando a infra do classificador.

Contrato (estável) — uma entrada por pergunta, chaveada por ``ordem``:
    {"perguntas": [
       {"ordem": 1, "regras": [
          {"regra": 1, "passou": false, "severidade": "avisa",
           "motivo": "...", "reescrita": "..."}]}]}
``regras`` vazio = nenhuma violação. ``severidade`` ∈ {"bloqueia","avisa"}.
"""

from __future__ import annotations

from typing import Any, Dict, List


def validar_perguntas(perguntas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Valida a lista de perguntas (gerada OU editada) contra a régua.

    F1.2: SEAM — devolve o veredito no formato estável com ``regras`` vazio por
    pergunta (nenhuma violação ainda). F1.3/F1.4 preenchem as checagens.
    """
    return {
        "perguntas": [
            {"ordem": p.get("ordem"), "regras": []}  # TODO F1.3/F1.4: checagens reais
            for p in perguntas
        ]
    }


def tem_bloqueio(veredito: Dict[str, Any]) -> bool:
    """True se algum veredito tem violação de severidade 'bloqueia' (trava o aprovar)."""
    return any(
        r.get("severidade") == "bloqueia"
        for p in veredito.get("perguntas", [])
        for r in p.get("regras", [])
    )
