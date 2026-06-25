"""Geração assistida de pesquisa (Fase 1).

Orquestra: contexto SANEADO do diagnóstico (só tópico, nunca direção) → system
prompt com a régua-guia → chamada LLM (injetável/mockável) → normalização da
saída estruturada → **passa pelo validador** antes de devolver. Função pura: NÃO
persiste (a persistência do rascunho é da F1.5/UI) e NÃO toca o pipeline.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from src.pesquisa.contexto import render_contexto, topicos_saneados
from src.pesquisa.regua import FORMATO_SAIDA, REGUA_GUIA
from src.pesquisa.validador import validar_perguntas

_FORMATOS = ("aberta", "fechada", "mista")


def _ancora_unidade() -> Dict[str, Any]:
    """Pergunta-âncora "qual unidade?" do modo 'geral'.

    Gerada pelo sistema (não é pergunta de conteúdo). As opções (locais do
    escopo) são preenchidas na persistência/UI (F1.5) — aqui fica o esqueleto.
    """
    return {
        "ordem": 1,
        "enunciado": "Qual unidade você está avaliando?",
        "porque": "Resolve o local_id por respondente (modo de escopo 'geral').",
        "formato": "fechada",
        "subpilar_alvo": None,
        "opcoes_json": json.dumps({"tipo": "unidade", "rotulos": []}),
        "gerada_por_ancora": True,
    }


def _montar_user_prompt(topicos, natureza: str, n_perguntas: int, escopo_local_modo: str) -> str:
    publico = "colaboradores (autopercepção do time)" if natureza == "interna" else "clientes"
    nota_ancora = ""
    if escopo_local_modo == "geral":
        nota_ancora = (
            "\nO sistema adicionará automaticamente uma pergunta-âncora de unidade; " "não a gere."
        )
    return (
        f"Gere {n_perguntas} pergunta(s) de pesquisa para {publico}.\n"
        f"Tópicos (subpilares) a cobrir:\n{render_contexto(topicos)}\n"
        f"{nota_ancora}\n\n{FORMATO_SAIDA}"
    )


def _normalizar(bruto: Dict[str, Any], escopo_local_modo: str) -> List[Dict[str, Any]]:
    """Converte a saída do LLM em perguntas internas (ordem, opcoes_json, âncora)."""
    perguntas: List[Dict[str, Any]] = []
    # âncora primeiro (modo geral) — ocupa a ordem 1.
    if escopo_local_modo == "geral":
        perguntas.append(_ancora_unidade())
    base = len(perguntas)
    for i, p in enumerate(bruto.get("perguntas", []), start=1):
        formato = p.get("formato")
        if formato not in _FORMATOS:
            formato = "aberta"
        opcoes = p.get("opcoes")
        perguntas.append(
            {
                "ordem": base + i,
                "enunciado": (p.get("enunciado") or "").strip(),
                "porque": (p.get("porque") or "").strip() or None,
                "formato": formato,
                "subpilar_alvo": p.get("subpilar_alvo"),
                "opcoes_json": json.dumps(opcoes) if opcoes else None,
                "gerada_por_ancora": False,
            }
        )
    return perguntas


def gerar_pesquisa(
    s,
    empresa_id: int,
    *,
    natureza: str,
    subpilares_alvo: List[str],
    n_perguntas: int,
    titulo: str = "",
    objetivo: Optional[str] = None,
    entidade_tipo: Optional[str] = None,
    entidade_id: Optional[int] = None,
    escopo_local_modo: str = "local",
    canal: Optional[str] = None,
    anonima: bool = False,
    gerar_fn: Optional[Callable[[str, str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Gera uma proposta de pesquisa (não persistida) já validada.

    Args:
        s: sessão (lida só p/ o contexto saneado do diagnóstico).
        gerar_fn: chamada LLM ``(system, user) -> dict``. Default = ``gerar_via_llm``;
            em teste injeta-se um fake.

    Returns:
        ``{"pesquisa": {...meta...}, "perguntas": [...], "validacao": {...}}``.
    """
    if gerar_fn is None:
        from src.pesquisa.llm import gerar_via_llm

        gerar_fn = gerar_via_llm

    topicos = topicos_saneados(s, empresa_id, subpilares_alvo)
    system = REGUA_GUIA
    user = _montar_user_prompt(topicos, natureza, n_perguntas, escopo_local_modo)

    bruto = gerar_fn(system, user)
    perguntas = _normalizar(bruto, escopo_local_modo)
    veredito = validar_perguntas(perguntas)  # SEAM — sempre passa pelo validador

    return {
        "pesquisa": {
            "empresa_id": empresa_id,
            "natureza": natureza,
            "titulo": titulo,
            "objetivo": objetivo,
            "entidade_tipo": entidade_tipo,
            "entidade_id": entidade_id,
            "escopo_local_modo": escopo_local_modo,
            "canal": canal,
            "anonima": anonima,
            "status": "rascunho",
            "versao": 1,
        },
        "perguntas": perguntas,
        "validacao": veredito,
    }
