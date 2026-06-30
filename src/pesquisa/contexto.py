"""Contexto SANEADO do diagnóstico para a geração.

Regra 1 nasce no input: o gerador recebe **só o tópico** (quais subpilares
perguntar, pelo nome legível), **nunca a direção** (faixa/ratio/valência). Esta
camada lê o diagnóstico (que TEM a direção) e descarta-a deliberadamente — a
sanitização é explícita e testável.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def topicos_saneados(
    s, empresa_id: int, subpilares_alvo: List[str], local_ids: Optional[List[int]] = None
) -> List[Dict[str, Any]]:
    """Lista de tópicos neutros para os ``subpilares_alvo`` pedidos.

    Cada item: ``{"subpilar", "nome", "pilar"}`` — **sem** ratio/faixa/direção.
    Lê ``agregar_subpilares`` apenas para registrar quais têm dado no escopo
    (``tem_dado``), descartando todo o resto. Subpilar pedido sem dado ainda
    entra como tópico (a escolha é do usuário). ``local_ids`` (P2.E) restringe o
    ``tem_dado`` ao escopo selecionado; None = empresa toda."""
    from src.api.painel import NOME_SUBPILAR, PILAR_DE_SUBPILAR
    from src.diagnostico.leituras import agregar_subpilares

    agg = agregar_subpilares(s, empresa_id, local_ids=local_ids)  # ratio/faixa DESCARTADOS
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


def render_focos(focos: List[Dict[str, Any]]) -> str:
    """Bloco de FOCOS prioritários para o user prompt (P2.D). No foco-tema, dá ao
    LLM o assunto concreto (``tema_label``) + os subpilares secundários — perguntas
    tema-aware, mas ancoradas no subpilar dominante. SEM direção/valência (régua 1):
    o tema é o assunto, não o juízo."""
    linhas = []
    for f in focos or []:
        if f.get("tipo") == "tema" and f.get("tema_label"):
            secundarios = [c["subpilar"] for c in f.get("tema_contexto", [])][1:4]
            extra = f" (também toca {', '.join(secundarios)})" if secundarios else ""
            linhas.append(
                f'- Tema "{f["tema_label"]}" → foco no subpilar {f.get("subpilar_alvo")}{extra}'
            )
    if not linhas:
        return ""
    return "Focos prioritários (faça perguntas sobre estes assuntos concretos):\n" + "\n".join(
        linhas
    )
