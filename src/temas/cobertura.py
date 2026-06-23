"""Cobertura de temas por bucket — régua LIVE (reconcilia as telas).

Antes, três números diferentes circulavam pelas telas para o "mesmo" tema/bucket
e não batiam: `temas_cache.volume` (snapshot do pipeline), `count(verbatim_temas)`
(vínculos vivos) e `count(Verbatim)` (classificação). Em especial, abrir um tema
mostrava o volume do cache e a lista de verbatins mostrava os vínculos vivos —
divergentes sempre que houve reprocessamento entre uma coisa e outra.

Régua oficial = **contagem LIVE**, no mesmo escopo (só verbatins COM TEXTO):

- ``total``       = verbatins do bucket (subpilar[+tipo]) com ``tem_texto=True``.
- ``em_temas``    = quantos DESSES têm ≥1 vínculo a um tema ATIVO (distinct).
- ``sem_tema``    = ``total - em_temas`` (ruído + descartados + não-cobertos).
  Sempre ≥ 0 e exato — ``em_temas + sem_tema == total`` por construção.
- ``cache_snapshot`` = ``sum(TemaCache.volume)`` do bucket (o número antigo do
  painel). Exibido só como referência "snapshot"; a diferença vs ``em_temas``
  vira o sinal de **cache defasado**.

Símbolos (``tem_texto=False``) ficam fora — não são tematizáveis.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import and_, func

from src.models.local import Local
from src.models.temas import Tema, TemaCache, VerbatimTema
from src.models.verbatim import Verbatim
from src.utils.db import db_session


def tripleto_bucket(
    empresa_id: int,
    subpilar: str,
    tipo: Optional[str] = None,
    agrupamento_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Tripleto de cobertura (total / em_temas / sem_tema) de um bucket, LIVE.

    Args:
        empresa_id: empresa.
        subpilar: subpilar do bucket (obrigatório).
        tipo: tipo do bucket (promotor/conversivel/detrator/inativo). ``None``
            agrega todos os tipos do subpilar.
        agrupamento_id: restringe a um agrupamento (via ``Local``). ``None`` =
            empresa-wide (todos os agrupamentos).

    Returns:
        ``{"total", "em_temas", "sem_tema", "cache_snapshot", "stale"}``.
    """
    with db_session() as s:
        base = s.query(Verbatim.id).filter(
            Verbatim.empresa_id == empresa_id,
            Verbatim.tem_texto.is_(True),
            Verbatim.subpilar == subpilar,
        )
        if tipo:
            base = base.filter(Verbatim.tipo == tipo)
        if agrupamento_id is not None:
            base = base.join(Local, Local.id == Verbatim.local_id).filter(
                Local.agrupamento_id == agrupamento_id
            )

        total = base.count()

        # em_temas: distinct verbatins do bucket com ≥1 vínculo a um tema ATIVO.
        em_q = base.join(VerbatimTema, VerbatimTema.verbatim_id == Verbatim.id).join(
            Tema, and_(Tema.id == VerbatimTema.tema_id, Tema.ativo.is_(True))
        )
        em_temas = em_q.distinct().count()

        # cache_snapshot: o número antigo do painel (sum do volume do snapshot).
        snap_q = s.query(func.coalesce(func.sum(TemaCache.volume), 0)).filter(
            TemaCache.empresa_id == empresa_id,
            TemaCache.subpilar == subpilar,
        )
        if tipo:
            snap_q = snap_q.filter(TemaCache.tipo == tipo)
        if agrupamento_id is not None:
            snap_q = snap_q.filter(TemaCache.agrupamento_id == agrupamento_id)
        cache_snapshot = int(snap_q.scalar() or 0)

    return {
        "total": total,
        "em_temas": em_temas,
        "sem_tema": max(0, total - em_temas),
        "cache_snapshot": cache_snapshot,
        "stale": cache_snapshot != em_temas,
    }


def temas_volume_live_subq(s):
    """Subquery LIVE espelhando as colunas-chave de ``temas_cache`` —
    ``(empresa_id, agrupamento_id, subpilar, tipo, tema_label, volume)`` — onde
    ``volume`` = verbatins DISTINTOS do bucket vinculados a um tema ATIVO.

    Drop-in para trocar ``TemaCache`` nos consumidores que só usam
    label/subpilar/tipo/agrupamento/volume (diagnóstico-narrativa, planos,
    anomalias, ia-chat): alinha-os à régua live das telas, sem depender da
    frescura do snapshot. NÃO traz ``percentual``/``exemplos``/``periodo`` (quem
    precisa desses fica no ``TemaCache``).
    """
    return (
        s.query(
            Verbatim.empresa_id.label("empresa_id"),
            Local.agrupamento_id.label("agrupamento_id"),
            Verbatim.subpilar.label("subpilar"),
            Verbatim.tipo.label("tipo"),
            Tema.nome.label("tema_label"),
            func.count(func.distinct(Verbatim.id)).label("volume"),
        )
        .select_from(VerbatimTema)
        .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
        .join(Tema, and_(Tema.id == VerbatimTema.tema_id, Tema.ativo.is_(True)))
        .outerjoin(Local, Local.id == Verbatim.local_id)
        .filter(
            Verbatim.tem_texto.is_(True),
            Verbatim.subpilar.isnot(None),
            Verbatim.tipo.isnot(None),
        )
        .group_by(
            Verbatim.empresa_id,
            Local.agrupamento_id,
            Verbatim.subpilar,
            Verbatim.tipo,
            Tema.nome,
        )
        .subquery()
    )
