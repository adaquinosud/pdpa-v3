"""F3 — classificador de DESFECHO do Caso (ReclameAqui).

Eixo PARALELO à valência: a queixa inicial (verbatim) diz "quão ruim foi"; o
Caso diz "como terminou". Este módulo NÃO toca a valência do verbatim
(anti-dupla-contagem) — só preenche ``desfecho``/``causa_resolvida`` no Caso.

Determinístico primeiro (fatos crus do RA), LLM só pra desambiguar o caso
respondido-sem-avaliação (o consumidor não deu nota → é preciso ler a thread pra
saber se ficou em disputa ou não). Re-classifica quando ``desfecho IS NULL`` — o
coletor zera ``desfecho`` ao detectar mudança de thread (ver reclame_aqui.py).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from src.models.caso import Caso
from src.utils.db import db_session

DESFECHO_PROMPT_PATH = Path(__file__).parent / "prompts" / "caso_desfecho_v1.md"
VERSAO_LLM = "caso-desfecho-llm-v1"
VERSAO_DET = "caso-desfecho-det-v1"

# desfechos que o LLM pode devolver (subconjunto ambíguo); o resto é determinístico
_DESFECHOS_LLM = {"respondida_em_disputa", "respondida_sem_avaliacao"}


def _desfecho_deterministico(caso: Caso) -> Optional[str]:
    """Desfecho quando os fatos crus já bastam (sem LLM). ``None`` = ambíguo,
    precisa ler a thread.

    - avaliado (o consumidor fechou): ``solved`` decide resolvido/nao_resolvido.
    - sem resposta da empresa (thread vazia / status PENDING) → nao_respondida.
    - respondido mas não avaliado → None (LLM lê a thread).
    """
    if caso.evaluated:
        return "resolvido" if caso.solved else "nao_resolvido"
    if not caso.interactions_count:
        return "nao_respondida"
    return None


def _chamar_desfecho(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Chamada Sonnet padrão (reusa a máquina do editorial), prompt do desfecho."""
    from src.anomalias.editorial import _chamar_sonnet

    return _chamar_sonnet(payload, DESFECHO_PROMPT_PATH)


def classificar_caso(caso: Caso, *, gerar_fn: Optional[Callable] = None) -> Dict[str, Any]:
    """Classifica UM caso. Determinístico quando dá; senão chama ``gerar_fn(payload)``
    (default = Sonnet; injetável em teste). Devolve o dict do desfecho (não persiste).

    Nunca deixa ``desfecho`` inválido: se o LLM devolver fora do enum, cai em
    ``respondida_sem_avaliacao`` (o caso É respondido-não-avaliado)."""
    det = _desfecho_deterministico(caso)
    if det is not None:
        return {
            "desfecho": det,
            "causa_resolvida": det == "resolvido",
            "justificativa": None,
            "versao": VERSAO_DET,
            "_in": 0,
            "_out": 0,
        }
    gerar = gerar_fn or _chamar_desfecho
    payload = {
        "descricao": caso.titulo or "",  # título = proxy leve; a thread carrega o resto
        "status": caso.status,
        "solved": caso.solved,
        "thread": json.loads(caso.thread_json or "[]"),
    }
    data = gerar(payload)
    desfecho = data.get("desfecho")
    if desfecho not in _DESFECHOS_LLM:
        desfecho = "respondida_sem_avaliacao"
    return {
        "desfecho": desfecho,
        "causa_resolvida": bool(data.get("causa_resolvida")),
        "justificativa": data.get("justificativa"),
        "versao": VERSAO_LLM,
        "_in": int(data.get("_in", 0) or 0),
        "_out": int(data.get("_out", 0) or 0),
    }


def gerar_desfecho_pendentes(
    fonte_id: int, *, gerar_fn: Optional[Callable] = None
) -> Dict[str, Any]:
    """Classifica os casos com ``desfecho IS NULL`` de uma fonte. Persiste
    desfecho/causa_resolvida/justificativa/versao. Stats: analisados, det, llm,
    custo de tokens."""
    stats = {"analisados": 0, "deterministico": 0, "llm": 0, "in": 0, "out": 0}
    with db_session() as s:
        casos = s.query(Caso).filter(Caso.fonte_id == fonte_id, Caso.desfecho.is_(None)).all()
        for caso in casos:
            r = classificar_caso(caso, gerar_fn=gerar_fn)
            caso.desfecho = r["desfecho"]
            caso.causa_resolvida = r["causa_resolvida"]
            caso.desfecho_justificativa = r["justificativa"]
            caso.desfecho_versao = r["versao"]
            stats["analisados"] += 1
            stats["deterministico" if r["versao"] == VERSAO_DET else "llm"] += 1
            stats["in"] += r["_in"]
            stats["out"] += r["_out"]
    return stats
