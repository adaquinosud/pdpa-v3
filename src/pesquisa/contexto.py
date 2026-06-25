"""Contexto SANEADO do diagnóstico para a geração.

Regra 1 nasce no input: o gerador recebe **só o tópico** (quais subpilares
perguntar, pelo nome legível), **nunca a direção** (faixa/ratio/valência). Esta
camada lê o diagnóstico (que TEM a direção) e descarta-a deliberadamente — a
sanitização é explícita e testável.
"""

from __future__ import annotations

from typing import Any, Dict, List


def topicos_saneados(s, empresa_id: int, subpilares_alvo: List[str]) -> List[Dict[str, Any]]:
    """Lista de tópicos neutros para os ``subpilares_alvo`` pedidos.

    Cada item: ``{"subpilar", "nome", "pilar"}`` — **sem** ratio/faixa/direção.
    Lê ``agregar_subpilares`` apenas para registrar quais têm dado no escopo
    (``tem_dado``), descartando todo o resto. Subpilar pedido sem dado ainda
    entra como tópico (a escolha é do usuário).
    """
    from src.api.painel import NOME_SUBPILAR, PILAR_DE_SUBPILAR
    from src.diagnostico.leituras import agregar_subpilares

    agg = agregar_subpilares(s, empresa_id)  # tem ratio/faixa — DESCARTADOS aqui
    topicos: List[Dict[str, Any]] = []
    for sub in subpilares_alvo:
        topicos.append(
            {
                "subpilar": sub,
                "nome": NOME_SUBPILAR.get(sub, sub),
                "pilar": PILAR_DE_SUBPILAR.get(sub),
                "tem_dado": sub in agg,  # só presença, nunca o valor/direção
            }
        )
    return topicos


def render_contexto(topicos: List[Dict[str, Any]]) -> str:
    """Renderiza os tópicos para o user prompt — só nome legível + código.

    Por construção não contém faixa/ratio/direção (a régua 1 depende disso).
    """
    linhas = [f"- {t['nome']} (subpilar {t['subpilar']})" for t in topicos]
    return "\n".join(linhas)
