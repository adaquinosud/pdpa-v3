"""Geração assistida de pesquisa (Fase 1).

Orquestra: contexto SANEADO do diagnóstico (só tópico, nunca direção) → system
prompt com a régua-guia → chamada LLM (injetável/mockável) → normalização da
saída estruturada → **ciclo AUTO-VALIDANTE** (a régua entra na geração, não só na
conferência) → devolve. Função pura: NÃO persiste (a persistência do rascunho é da
F1.5/UI) e NÃO toca o pipeline.

Ciclo auto-validante (fatia 2): gerar → determinística ($0) regenera só as
reprovadas (até MAX_DET_REGEN×) → semântica (juiz, 1 lote) regenera as reprovadas
+ 1 retry → devolve. TRAVA: nunca esconde falha — o que sobra reprovado volta COM o
veredito visível (o usuário conserta o resíduo raro). Aviso do juiz NÃO escala para
bloqueio (a régua é uma só; o juiz é LLM e erra — falso-positivo não trava aprovação).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from src.models.agrupamento import Agrupamento
from src.models.local import Local
from src.pesquisa.contexto import render_contexto, render_focos, topicos_saneados
from src.pesquisa.juiz import avaliar_perguntas
from src.pesquisa.regua import FORMATO_SAIDA, REGUA_GUIA
from src.pesquisa.validador import validar_perguntas

_FORMATOS = ("aberta", "fechada", "mista")
_LOG = logging.getLogger(__name__)

# Ciclo auto-validante: quantas vezes regenerar as reprovadas em cada camada.
MAX_DET_REGEN = 2  # determinística ($0 o check; cada regen = 1 chamada LLM)
MAX_SEM_ITER = 2  # semântica: 1 check inicial + 1 retry (2 chamadas ao juiz no máx)


def _opcoes_escopo(
    s,
    empresa_id: int,
    entidade_tipo: Optional[str],
    entidade_id: Optional[int],
    local_ids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """Opções de escopo da âncora "qual unidade?" (modo 'geral'). Cada opção
    carrega ``(entidade_tipo, entidade_id)`` — mesmo vocabulário do `Respondente`
    (P6) — para o submit gravar o escopo direto. Lista os `Local` do escopo;
    ``local_ids`` (P2.E) restringe à união de locais do escopo; se o escopo é um
    agrupamento SEM locais, oferece o próprio agrupamento."""
    q = s.query(Local).filter(Local.empresa_id == empresa_id)
    if local_ids is not None:
        q = q.filter(Local.id.in_(local_ids))
    elif entidade_tipo == "agrupamento" and entidade_id is not None:
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


def _montar_user_prompt(
    topicos, natureza: str, n_perguntas: int, escopo_local_modo: str, focos=None
) -> str:
    publico = "colaboradores (autopercepção do time)" if natureza == "interna" else "clientes"
    nota_ancora = ""
    if escopo_local_modo == "geral":
        nota_ancora = (
            "\nO sistema adicionará automaticamente uma pergunta-âncora de unidade; " "não a gere."
        )
    bloco_focos = render_focos(focos)
    bloco_focos = f"\n{bloco_focos}\n" if bloco_focos else ""
    return (
        f"Gere {n_perguntas} pergunta(s) de pesquisa para {publico}.\n"
        f"Gere as perguntas APENAS nestes subpilares. O subpilar_alvo de TODA "
        f"pergunta deve ser um dos listados abaixo; NÃO use outros subpilares. "
        f"Divida as {n_perguntas} pergunta(s) entre os subpilares-alvo listados:\n"
        f"{render_contexto(topicos)}\n"
        f"{bloco_focos}{nota_ancora}\n\n{FORMATO_SAIDA}"
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


def _reprovadas(veredito: Dict[str, Any], por_ordem: Dict[int, Dict[str, Any]]):
    """Perguntas com veredito não-vazio (qualquer regra, bloqueio OU aviso) → gatilho de
    regen. Junta o motivo (do veredito) ao estado atual da pergunta (subpilar/enunciado).
    Marca ``tem_escopo`` (a única regra em que o subpilar-alvo é o errado)."""
    out = []
    for entry in veredito.get("perguntas", []):
        regras = entry.get("regras") or []
        if not regras:
            continue
        p = por_ordem.get(entry.get("ordem"))
        if p is None:
            continue
        out.append(
            {
                "ordem": entry["ordem"],
                "subpilar_alvo": p.get("subpilar_alvo"),
                "enunciado": p.get("enunciado"),
                "motivos": [r["motivo"] for r in regras if r.get("motivo")],
                "tem_escopo": any(r.get("regra") == "escopo" for r in regras),
            }
        )
    return out


def _montar_user_regen(reprovadas, subpilares_alvo: List[str]) -> str:
    """Prompt de regeneração: o motivo LITERAL da reprova por pergunta. Falha de wording
    (R1/R3/R4/R5…) → mantém o subpilar; falha de ESCOPO → escolhe um do conjunto (não
    força subpilar à revelia do enunciado — se persistir, o veredito mostra o 🔴)."""
    linhas = []
    for i, r in enumerate(reprovadas, start=1):
        motivo = "; ".join(r["motivos"]) or "reprovada pela régua"
        if r["tem_escopo"]:
            alvo = f"escolha o subpilar_alvo dentre: {', '.join(subpilares_alvo)}"
        else:
            alvo = f"mantenha o subpilar_alvo '{r['subpilar_alvo']}'"
        linhas.append(f'{i}) [{alvo}] "{r["enunciado"]}"\n   PROBLEMA: {motivo}')
    corpo = "\n".join(linhas)
    return (
        "As perguntas abaixo foram REPROVADAS pela régua. Reescreva CADA uma corrigindo "
        "EXATAMENTE o problema, mantendo o mesmo assunto. Não repita o erro. Devolva "
        f"{len(reprovadas)} pergunta(s), na MESMA ordem.\n\n{corpo}\n\n{FORMATO_SAIDA}"
    )


def _aplicar_regen(gerar_fn, reprovadas, perguntas, subpilares_alvo):
    """Regenera SÓ as reprovadas e faz merge por ordem. Robusto: erro de LLM ou nº de
    perguntas ≠ reprovadas → mantém as originais (nunca dropa/mismapeia)."""
    try:
        bruto = gerar_fn(REGUA_GUIA, _montar_user_regen(reprovadas, subpilares_alvo))
        novas = _normalizar(bruto, "local", None)  # sem âncora; ordem 1..N provisória
    except Exception:  # noqa: BLE001 — regen que falha degrada, não derruba a geração
        _LOG.exception("regen falhou; mantendo perguntas reprovadas (veredito as expõe)")
        return perguntas
    if len(novas) != len(reprovadas):
        _LOG.warning(
            "regen devolveu %d ≠ %d reprovadas; mantendo originais", len(novas), len(reprovadas)
        )
        return perguntas
    subst = {}
    for nova, rep in zip(novas, reprovadas):
        nova["ordem"] = rep["ordem"]
        if not rep["tem_escopo"]:  # wording: preserva o alvo já atribuído (não deriva)
            nova["subpilar_alvo"] = rep["subpilar_alvo"]
        nova["gerada_por_ancora"] = False
        subst[rep["ordem"]] = nova
    return [subst.get(p["ordem"], p) for p in perguntas]


def _fundir(vd: Dict[str, Any], vs: Dict[str, Any]) -> Dict[str, Any]:
    """Funde veredito determinístico + semântico por ordem (sem chamar o juiz de novo)."""
    sem = {e["ordem"]: e.get("regras") or [] for e in vs.get("perguntas", [])}
    return {
        "perguntas": [
            {"ordem": e["ordem"], "regras": (e.get("regras") or []) + sem.get(e["ordem"], [])}
            for e in vd.get("perguntas", [])
        ]
    }


def gerar_pesquisa(
    s,
    empresa_id: int,
    *,
    natureza: str,
    subpilares_alvo: List[str],
    n_perguntas: int,
    titulo: str = "",
    objetivo: Optional[str] = None,
    proposito: str = "coleta",
    entidade_tipo: Optional[str] = None,
    entidade_id: Optional[int] = None,
    escopo_local_modo: str = "local",
    canal: Optional[str] = None,
    anonima: bool = False,
    focos: Optional[List[Dict[str, Any]]] = None,
    local_ids: Optional[List[int]] = None,
    gerar_fn: Optional[Callable[[str, str], Dict[str, Any]]] = None,
    juiz_fn: Optional[Callable[[str, str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Gera uma proposta de pesquisa (não persistida) já validada pela régua NO CICLO.

    Args:
        s: sessão (lida só p/ o contexto saneado do diagnóstico).
        gerar_fn: chamada LLM ``(system, user) -> dict``. Default = ``gerar_via_llm``;
            em teste injeta-se um fake.
        juiz_fn: chamada LLM do juiz semântico (R1/R2/R7). Default = juiz real; em teste
            injeta-se um fake. Repassado a ``avaliar_perguntas``.

    Returns:
        ``{"pesquisa": {...meta...}, "perguntas": [...], "validacao": {...}}`` — o
        ``validacao`` reflete o ESTADO FINAL (det + sem), com qualquer resíduo visível.
    """
    if gerar_fn is None:
        from src.pesquisa.llm import gerar_via_llm

        gerar_fn = gerar_via_llm

    topicos = topicos_saneados(s, empresa_id, subpilares_alvo, local_ids)
    system = REGUA_GUIA
    user = _montar_user_prompt(topicos, natureza, n_perguntas, escopo_local_modo, focos)

    opcoes_escopo = (
        _opcoes_escopo(s, empresa_id, entidade_tipo, entidade_id, local_ids)
        if escopo_local_modo == "geral"
        else None
    )

    bruto = gerar_fn(system, user)
    perguntas = _normalizar(bruto, escopo_local_modo, opcoes_escopo)

    # ── Ciclo auto-validante ─────────────────────────────────────────────────
    # 2a. determinística ($0 o check). Regenera só as reprovadas, até MAX_DET_REGEN×.
    vd = validar_perguntas(perguntas, subpilares_alvo)
    for _ in range(MAX_DET_REGEN):
        repro = _reprovadas(vd, {p["ordem"]: p for p in perguntas})
        if not repro:
            break
        perguntas = _aplicar_regen(gerar_fn, repro, perguntas, subpilares_alvo)
        vd = validar_perguntas(perguntas, subpilares_alvo)

    # 2b. semântica (juiz, 1 lote) + 1 retry. Aviso NÃO escala p/ bloqueio.
    vs = avaliar_perguntas(perguntas, juiz_fn)
    for _ in range(MAX_SEM_ITER - 1):
        repro = _reprovadas(vs, {p["ordem"]: p for p in perguntas})
        if not repro:
            break
        perguntas = _aplicar_regen(gerar_fn, repro, perguntas, subpilares_alvo)
        vd = validar_perguntas(perguntas, subpilares_alvo)  # re-check det pós-regen ($0)
        vs = avaliar_perguntas(perguntas, juiz_fn)

    # Veredito final = estado final (det + sem). Resíduo reprovado volta VISÍVEL.
    veredito = _fundir(vd, vs)

    return {
        "pesquisa": {
            "empresa_id": empresa_id,
            "natureza": natureza,
            "proposito": proposito,
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
