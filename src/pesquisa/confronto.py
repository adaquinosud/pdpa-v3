"""Base comum do confronto (Fase 2 · Passo 5a) — classifica a Resposta.

Classifica o comentário do colaborador (``Resposta.valor_texto`` de pesquisas
``proposito='confronto'``) no MESMO vocabulário dos verbatins, via ``classificar()``
(função PURA), e grava o resultado NA PRÓPRIA Resposta. **Fronteira inegociável:**
nenhum ``Verbatim`` é criado e o ratio/diagnóstico do cliente fica intocado — a
segregação é por ausência de ponte.

Em LOTE (não por submissão) — disparável pela noturna ou sob demanda.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from src.models.pesquisa import Pesquisa
from src.models.respondente import Respondente, Resposta


def classificar_respostas_confronto(
    s, *, pesquisa_id: Optional[int] = None, empresa_id: Optional[int] = None, limite: int = 500
) -> Dict[str, Any]:
    """Classifica em lote as Respostas de confronto ainda não classificadas.

    Filtra por ``pesquisa_id`` OU ``empresa_id`` (um dos dois). Só toca Respostas
    de pesquisas ``proposito='confronto'`` com ``valor_texto`` e sem
    ``classificado_em``. Grava subpilar/valência/confiança na própria Resposta —
    NUNCA cria Verbatim."""
    from src.classifier.classifier_v3 import classificar

    q = (
        s.query(Resposta)
        .join(Respondente, Respondente.id == Resposta.respondente_id)
        .join(Pesquisa, Pesquisa.id == Respondente.pesquisa_id)
        .filter(
            Pesquisa.proposito == "confronto",
            Resposta.valor_texto.isnot(None),
            Resposta.classificado_em.is_(None),
        )
    )
    if pesquisa_id is not None:
        q = q.filter(Pesquisa.id == pesquisa_id)
    if empresa_id is not None:
        q = q.filter(Pesquisa.empresa_id == empresa_id)

    stats = {"classificadas": 0, "erros": 0, "puladas": 0}
    for r in q.limit(limite).all():
        texto = (r.valor_texto or "").strip()
        if not texto:
            stats["puladas"] += 1
            continue
        try:
            res = classificar(texto)
        except Exception:  # noqa: BLE001 — uma resposta problemática não derruba o lote
            stats["erros"] += 1
            continue
        r.subpilar_classificado = res.subpilar
        r.valencia_classificada = res.tipo
        r.confianca_classificacao = res.confianca
        r.prompt_versao = res.prompt_versao
        r.classificado_em = datetime.utcnow()
        stats["classificadas"] += 1
    s.flush()
    return stats
