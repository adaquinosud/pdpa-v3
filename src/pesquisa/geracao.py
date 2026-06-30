"""Geração assistida de pesquisa (Fase 1).

Orquestra: contexto SANEADO do diagnóstico (só tópico, nunca direção) → system
prompt com a régua-guia → chamada LLM (injetável/mockável) → normalização da
saída estruturada → **passa pelo validador** antes de devolver. Função pura: NÃO
persiste (a persistência do rascunho é da F1.5/UI) e NÃO toca o pipeline.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from src.models.agrupamento import Agrupamento
from src.models.local import Local
from src.pesquisa.contexto import render_contexto, topicos_saneados
from src.pesquisa.regua import FORMATO_SAIDA, REGUA_GUIA
from src.pesquisa.validador import validar_perguntas

_FORMATOS = ("aberta", "fechada", "mista")


def _opcoes_escopo(
    s, empresa_id: int, entidade_tipo: Optional[str], entidade_id: Optional[int]
) -> List[Dict[str, Any]]:
    """Opções de escopo da âncora "qual unidade?" (modo 'geral'). Cada opção
    carrega ``(entidade_tipo, entidade_id)`` — mesmo vocabulário do `Respondente`
    (P6) — para o submit gravar o escopo direto. Lista os `Local` do escopo; se o
    escopo é um agrupamento SEM locais, oferece o próprio agrupamento."""
    q = s.query(Local).filter(Local.empresa_id == empresa_id)
    if entidade_tipo == "agrupamento" and entidade_id is not None:
        q = q.filter(Local.agrupamento_id == entidade_id)
    locais = q.order_by(Local.nome).all()
    if locais:
        return [
            {"entidade_tipo": "local", "entidade_id": loc.id, "rotulo": loc.nome} for loc in locais
        ]
    # Agrupamento sem locais → o próprio agrupamento é a unidade.
    if entidade_tipo == "agrupamento" and entidade_id is not None:
        ag = s.get(Agrupamento, entidade_id)
        if ag is not None:
            return [{"entidade_tipo": "agrupamento", "entidade_id": ag.id, "rotulo": ag.nome}]
    return []


def _ancora_unidade(opcoes_escopo: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Pergunta-âncora "qual unidade?" do modo 'geral'.

    Gerada pelo sistema. Cada opção carrega ``(entidade_tipo, entidade_id, rotulo)``
    — o submit grava o escopo do `Respondente` direto. Sem opções (escopo vazio) →
    lista vazia (a UI/Fase 2 cuida do caso degenerado)."""
    opcoes = opcoes_escopo or []
    return {
        "ordem": 1,
        "enunciado": "Qual unidade você está avaliando?",
        "porque": "Resolve o escopo (entidade_tipo/entidade_id) por respondente.",
        "formato": "fechada",
        "subpilar_alvo": None,
        "opcoes_json": json.dumps({"tipo": "unidade", "opcoes": opcoes}),
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


def _normalizar(
    bruto: Dict[str, Any],
    escopo_local_modo: str,
    opcoes_escopo: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Converte a saída do LLM em perguntas internas (ordem, opcoes_json, âncora)."""
    perguntas: List[Dict[str, Any]] = []
    # âncora primeiro (modo geral) — ocupa a ordem 1.
    if escopo_local_modo == "geral":
        perguntas.append(_ancora_unidade(opcoes_escopo))
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

    opcoes_escopo = (
        _opcoes_escopo(s, empresa_id, entidade_tipo, entidade_id)
        if escopo_local_modo == "geral"
        else None
    )

    bruto = gerar_fn(system, user)
    perguntas = _normalizar(bruto, escopo_local_modo, opcoes_escopo)
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
