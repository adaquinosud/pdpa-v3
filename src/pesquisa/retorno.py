"""Retorno de uma pesquisa (Fase 2 · Passo 4) — leitura/agregação das respostas.

Agrega ``Resposta`` (via ``Respondente``) por pergunta: nota → média +
distribuição na escala (lida de ``opcoes_json``); texto → comentários; mista →
ambos; múltipla → contagem por opção. Sem escrita, sem schema novo. Python puro.

Anonimato é por LINHA: lista respondentes só em pesquisa identificada, e cada
respondente sem Pessoa (ou Pessoa tokenizada) aparece como "anônimo".
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from src.models.agrupamento import Agrupamento
from src.models.local import Local
from src.models.pesquisa import Pesquisa
from src.models.pessoa import Pessoa
from src.models.respondente import Respondente, Resposta

Escopo = Tuple[str, Optional[int]]


def _escala(opcoes_json: Optional[str]) -> Dict[str, Any]:
    try:
        return json.loads(opcoes_json) if opcoes_json else {}
    except (ValueError, TypeError):
        return {}


def _rotulo_escopo(s, entidade_tipo: str, entidade_id: Optional[int], cache: dict) -> str:
    key = (entidade_tipo, entidade_id)
    if key in cache:
        return cache[key]
    if entidade_tipo == "empresa" or entidade_id is None:
        rot = "Empresa toda"
    elif entidade_tipo == "local":
        loc = s.get(Local, entidade_id)
        rot = loc.nome if loc else f"Local {entidade_id}"
    elif entidade_tipo == "agrupamento":
        ag = s.get(Agrupamento, entidade_id)
        rot = ag.nome if ag else f"Agrupamento {entidade_id}"
    else:
        rot = f"{entidade_tipo} {entidade_id}"
    cache[key] = rot
    return rot


def _agg_pergunta(p, respostas: List[Resposta]) -> Dict[str, Any]:
    """Agrega as respostas de UMA pergunta conforme o formato."""
    esc = _escala(p.opcoes_json)
    tipo = esc.get("tipo")
    item: Dict[str, Any] = {
        "id": p.id,
        "ordem": p.ordem,
        "enunciado": p.enunciado,
        "formato": p.formato,
        "n_respostas": len(respostas),
        "nota": None,
        "comentarios": None,
        "opcoes": None,
    }
    if tipo == "nota" or p.formato == "mista":
        notas = [r.valor_nota for r in respostas if r.valor_nota is not None]
        pontos = esc.get("pontos") if isinstance(esc.get("pontos"), int) else 5
        rotulos = esc.get("rotulos") or [str(i) for i in range(1, pontos + 1)]
        dist = Counter(notas)
        item["nota"] = {
            "media": round(statistics.mean(notas), 2) if notas else None,
            "pontos": pontos,
            "n": len(notas),
            "distribuicao": [
                {
                    "valor": v,
                    "rotulo": rotulos[v - 1] if 1 <= v <= len(rotulos) else str(v),
                    "n": dist.get(v, 0),
                }
                for v in range(1, pontos + 1)
            ],
        }
    if tipo == "multipla":
        cont = Counter(r.valor_opcao for r in respostas if r.valor_opcao)
        rotulos = esc.get("rotulos") or list(cont.keys())
        item["opcoes"] = [{"rotulo": rot, "n": cont.get(rot, 0)} for rot in rotulos]
    if p.formato in ("aberta", "mista"):
        item["comentarios"] = [r.valor_texto for r in respostas if r.valor_texto]
    return item


def retorno_pesquisa(
    s, pesquisa_id: int, escopo: Optional[Escopo] = None
) -> Optional[Dict[str, Any]]:
    """Agrega o retorno de uma pesquisa, opcionalmente filtrado por um ``escopo``
    (entidade_tipo, entidade_id). Devolve ``None`` se a pesquisa não existe."""
    pesq = s.get(Pesquisa, pesquisa_id)
    if pesq is None:
        return None
    cache_rot: dict = {}

    # Respondentes (filtrados por escopo, se dado).
    q_resp = s.query(Respondente).filter(Respondente.pesquisa_id == pesquisa_id)
    if escopo is not None:
        q_resp = q_resp.filter(
            Respondente.entidade_tipo == escopo[0], Respondente.entidade_id == escopo[1]
        )
    respondentes = q_resp.all()
    resp_ids = [r.id for r in respondentes]

    # Escopos PRESENTES (sem filtro — sempre todos, p/ o seletor da tela).
    todos = s.query(Respondente).filter(Respondente.pesquisa_id == pesquisa_id).all()
    escopo_cont = Counter((r.entidade_tipo, r.entidade_id) for r in todos)
    escopos = [
        {
            "entidade_tipo": et,
            "entidade_id": eid,
            "rotulo": _rotulo_escopo(s, et, eid, cache_rot),
            "n": n,
        }
        for (et, eid), n in escopo_cont.items()
    ]

    # Respostas dos respondentes filtrados → agrupa por pergunta.
    por_pergunta: Dict[int, List[Resposta]] = {}
    if resp_ids:
        for r in s.query(Resposta).filter(Resposta.respondente_id.in_(resp_ids)).all():
            por_pergunta.setdefault(r.pergunta_id, []).append(r)
    perguntas = [
        _agg_pergunta(p, por_pergunta.get(p.id, []))
        for p in pesq.perguntas
        if not p.gerada_por_ancora
    ]

    # Lista de respondentes — só em pesquisa identificada; anonimato POR LINHA.
    respondentes_out: Optional[List[Dict[str, Any]]] = None
    if not pesq.anonima:
        pessoa_ids = [r.pessoa_id for r in respondentes if r.pessoa_id]
        pessoas = (
            {p.id: p for p in s.query(Pessoa).filter(Pessoa.id.in_(pessoa_ids))}
            if pessoa_ids
            else {}
        )
        respondentes_out = []
        for r in respondentes:
            pp = pessoas.get(r.pessoa_id) if r.pessoa_id else None
            nome = pp.nome_display if (pp and pp.nome_display) else "anônimo"
            respondentes_out.append(
                {
                    "nome": nome,
                    "escopo": _rotulo_escopo(s, r.entidade_tipo, r.entidade_id, cache_rot),
                }
            )

    return {
        "pesquisa": {
            "id": pesq.id,
            "empresa_id": pesq.empresa_id,
            "titulo": pesq.titulo,
            "anonima": pesq.anonima,
            "proposito": pesq.proposito,
        },
        "total_respondentes": len(resp_ids),
        "escopos": escopos,
        "perguntas": perguntas,
        "respondentes": respondentes_out,
    }
