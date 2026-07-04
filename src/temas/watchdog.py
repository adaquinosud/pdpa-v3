"""CP-poscoleta-watchdog: pós-coleta resiliente a redeploy.

O pós-coleta roda numa daemon-thread (UX rápida) que **morre no redeploy** — se
morre no meio, deixa estado parcial silencioso (foi a causa dos 204 casos sem
desfecho e da sonda meia-boca). Este módulo fecha o buraco SEM infra nova:

- ``pendencias_pos_coleta`` — detector único do estado derivado incompleto
  (subpilar NULL, desfecho NULL, embeddings faltando, cache defasado).
- ``deve_reprocessar`` — gate por PENDÊNCIA (não por "novos"): dispara se
  ``desfecho_null >= 1`` (exceção — dor aguda) OU volume de pendências
  (subpilar + embeddings) ``>= THRESHOLD``.
- ``pos_coleta_watchdog`` — varre TODAS as empresas (não só as da noturna), com
  lock por-empresa (anti-concorrência) + cooldown (não re-roda a mesma empresa
  dentro da janela). Roda no cron (container que sobrevive a redeploy) → self-heal
  automático. Marca ``pos_coleta_status`` (rodando/completo/interrompido) p/ o
  banner admin — interrupção nunca mais silenciosa.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

THRESHOLD_VOLUME = 5  # subpilar_null + embeddings_faltando p/ disparar
COOLDOWN_HORAS = 6


def pendencias_pos_coleta(empresa_id: int) -> Dict[str, Any]:
    """Snapshot do estado derivado INCOMPLETO da empresa. Tudo por contagem barata
    (sem gerar nada). ``cache_defasado`` = ``sum(TemaCache.volume) != nº de
    verbatins distintos vinculados a temas ATIVOS`` (o mesmo sinal do badge)."""
    from sqlalchemy import and_, func

    from src.models.caso import Caso
    from src.models.temas import Tema, TemaCache, VerbatimEmbedding, VerbatimTema
    from src.models.verbatim import Verbatim
    from src.temas.embeddings import MODELO_PADRAO
    from src.utils.db import db_session

    with db_session() as s:
        subpilar_null = (
            s.query(func.count(Verbatim.id))
            .filter(
                Verbatim.empresa_id == empresa_id,
                Verbatim.tem_texto.is_(True),
                Verbatim.subpilar.is_(None),
            )
            .scalar()
            or 0
        )
        desfecho_null = (
            s.query(func.count(Caso.id))
            .filter(Caso.empresa_id == empresa_id, Caso.desfecho.is_(None))
            .scalar()
            or 0
        )
        sub_ja = s.query(VerbatimEmbedding.verbatim_id).filter(
            VerbatimEmbedding.modelo == MODELO_PADRAO
        )
        embeddings_faltando = (
            s.query(func.count(Verbatim.id))
            .filter(
                Verbatim.empresa_id == empresa_id,
                Verbatim.tem_texto.is_(True),
                ~Verbatim.id.in_(sub_ja),
            )
            .scalar()
            or 0
        )
        cache_snapshot = (
            s.query(func.coalesce(func.sum(TemaCache.volume), 0))
            .filter(TemaCache.empresa_id == empresa_id)
            .scalar()
            or 0
        )
        cache_live = (
            s.query(func.count(func.distinct(Verbatim.id)))
            .select_from(VerbatimTema)
            .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
            .join(Tema, and_(Tema.id == VerbatimTema.tema_id, Tema.ativo.is_(True)))
            .filter(Verbatim.empresa_id == empresa_id, Verbatim.tem_texto.is_(True))
            .scalar()
            or 0
        )

    return {
        "subpilar_null": int(subpilar_null),
        "desfecho_null": int(desfecho_null),
        "embeddings_faltando": int(embeddings_faltando),
        "cache_defasado": bool(cache_snapshot != cache_live),
        "cache_snapshot": int(cache_snapshot),
        "cache_live": int(cache_live),
    }


def deve_reprocessar(pend: Dict[str, Any]) -> bool:
    """Gate por pendência: desfecho é exceção (≥1 dispara — foi a dor dos 204);
    o resto é por volume (subpilar + embeddings ≥ THRESHOLD)."""
    if pend.get("desfecho_null", 0) >= 1:
        return True
    volume = pend.get("subpilar_null", 0) + pend.get("embeddings_faltando", 0)
    return volume >= THRESHOLD_VOLUME


def _tem_pendencia(pend: Dict[str, Any]) -> bool:
    """Qualquer pendência (inclui cache defasado) — p/ o banner."""
    return deve_reprocessar(pend) or bool(pend.get("cache_defasado"))


def pos_coleta_watchdog(
    *,
    cooldown_horas: int = COOLDOWN_HORAS,
    agora: Optional[datetime] = None,
    empresa_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Varre empresas e retoma o pós-coleta das que têm pendência acionável, com
    lock por-empresa + cooldown. Idempotente: empresa limpa = no-op instantâneo.

    - ``desfecho``/volume acima do gate → ``executar_pos_coleta(force=True)``.
    - só ``cache_defasado`` → regen leve dos vínculos (``$0``, sem LLM).
    Marca ``pos_coleta_status`` p/ o banner (rodando→completo; 'rodando' velho que
    reaparece = interrompido).
    """
    from src.models.empresa import Empresa
    from src.temas.limpeza import _regenerar_cache_por_vinculos
    from src.temas.pos_coleta import _lock_empresa, _marcar_pos_coleta_status, executar_pos_coleta
    from src.utils.db import db_session

    agora = agora or datetime.utcnow()
    limite_cooldown = agora - timedelta(hours=cooldown_horas)
    stats = {
        "varridas": 0,
        "retomadas": 0,
        "cache_alinhado": 0,
        "limpas": 0,
        "puladas_cooldown": 0,
        "puladas_lock": 0,
        "interrompidas": 0,
    }

    if empresa_ids is None:
        with db_session() as s:
            empresa_ids = [row[0] for row in s.query(Empresa.id).all()]

    for eid in empresa_ids:
        stats["varridas"] += 1
        pend = pendencias_pos_coleta(eid)

        if not _tem_pendencia(pend):
            _marcar_pos_coleta_status(eid, "completo", pend, agora=agora)
            stats["limpas"] += 1
            continue

        # 'rodando' que sobreviveu ao cooldown = processo morreu no meio.
        with db_session() as s:
            emp = s.get(Empresa, eid)
            if emp is None:
                continue
            iniciado, status = emp.pos_coleta_iniciado_em, emp.pos_coleta_status
        if status == "rodando" and iniciado and iniciado <= limite_cooldown:
            _marcar_pos_coleta_status(eid, "interrompido", pend, agora=agora)
            stats["interrompidas"] += 1
        elif iniciado and iniciado > limite_cooldown:
            stats["puladas_cooldown"] += 1
            continue

        with _lock_empresa(eid) as adquiriu:
            if not adquiriu:
                stats["puladas_lock"] += 1
                continue
            _marcar_pos_coleta_status(eid, "rodando", pend, agora=agora)
            if deve_reprocessar(pend):
                executar_pos_coleta(eid, limiar=1, force=True)
                stats["retomadas"] += 1
            else:  # só cache defasado → alinhamento leve, sem LLM
                _regenerar_cache_por_vinculos(eid)
                stats["cache_alinhado"] += 1
            _marcar_pos_coleta_status(eid, "completo", pendencias_pos_coleta(eid), agora=agora)

    return stats
