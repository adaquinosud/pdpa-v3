"""Série mensal de ratio P/D por (loja × subpilar) — base da Camada 1.

Constrói/atualiza ``ratios_mensais`` a partir dos verbatins classificados da
empresa, dentro de uma JANELA de ``JANELA_RATIOS_MESES`` meses (os consumidores
mais fundos leem ≤12m — a janela é margem de 2×). INCREMENTAL: recomputa só os
meses TOCADOS (verbatim novo por ``data_coleta`` OU reclassificado por
``reclassificado_em``), não a série inteira a cada coleta. O incremental
AUTO-PODA o que passou de 24m (a janela desliza sozinha; o legado >24m é purgado
na 1ª coleta pós-deploy, sem ``--full`` manual). ``full=True`` (ou tabela vazia)
reconcilia: purga TODAS as linhas e recomputa a janela — só nos casos NÃO
rastreáveis por timestamp (delete de verbatim, move de local, reparo manual).

⚠️ ``ratio`` = P/D (conversível FORA do ratio, por método — Manual Cap. 4);
``total`` = volume (P+C+D). Denominadores diferentes DE PROPÓSITO — ``total``
NÃO é a base do ``ratio``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from src.api.painel import SUBPILARES_ORDEM, calcular_ratio

_SUBPILARES = set(SUBPILARES_ORDEM)
_TIPOS = ("promotor", "conversivel", "detrator")

# Janela de cálculo: 24 meses. Margem DELIBERADA de 2× sobre o consumidor mais
# fundo (Previsibilidade 12m), NÃO medida. Bounda o full-recompute e a tabela; o
# incremental bounda o trabalho por coleta (só meses tocados).
JANELA_RATIOS_MESES = 24


def _subtrai_meses(mes: str, n: int) -> str:
    """'YYYY-MM' menos ``n`` meses → 'YYYY-MM'."""
    ano, m = mes.split("-")
    tot = int(ano) * 12 + (int(m) - 1) - n
    return f"{tot // 12:04d}-{tot % 12 + 1:02d}"


def recomputar_ratios_mensais(
    empresa_id: int, *, meses: Optional[Set[str]] = None, full: bool = False
) -> int:
    """(Re)constrói ``ratios_mensais`` na janela de 24m. Devolve nº de linhas gravadas.

    Grão ``(local_id, subpilar, ano-mês)``; só subpilar válido (12) e com
    ``data_criacao_original``. ``local_id=NULL`` (voz da marca) vira sua própria
    linha, disjunta das de loja.

    - ``full=True`` ou tabela vazia → **reconcilia**: apaga TODAS as linhas da
      empresa e recomputa a janela inteira. Casos não rastreáveis por timestamp:
      delete de verbatim, move de local, reparo manual.
    - ``meses`` set de 'YYYY-MM' → recomputa só esses (clamp à janela).
    - ``meses=None`` (default incremental) → **auto-poda** o que passou de 24m e
      recomputa os meses TOCADOS: verbatins com ``data_coleta`` OU
      ``reclassificado_em`` > ``MAX(gerado_em)`` (coleta nova E reclassificação,
      sem coluna nova). A poda faz a 1ª coleta pós-deploy purgar o legado >24m.
    """
    from sqlalchemy import func, or_

    from src.models.anomalia import RatioMensal
    from src.models.local import Local
    from src.models.verbatim import Verbatim
    from src.utils.db import db_session
    from src.utils.sql import fmt_ano_mes

    periodo_expr = fmt_ano_mes(Verbatim.data_criacao_original)

    with db_session() as s:
        max_mes = (
            s.query(func.max(periodo_expr))
            .filter(
                Verbatim.empresa_id == empresa_id,
                Verbatim.data_criacao_original.isnot(None),
            )
            .scalar()
        )
        if not max_mes:  # empresa sem dado datado → limpa e sai
            s.query(RatioMensal).filter(RatioMensal.empresa_id == empresa_id).delete(
                synchronize_session=False
            )
            s.commit()
            return 0
        cutoff = _subtrai_meses(max_mes, JANELA_RATIOS_MESES - 1)  # início da janela

        tem_linhas = (
            s.query(RatioMensal.id).filter(RatioMensal.empresa_id == empresa_id).first() is not None
        )
        meses_alvo: Optional[Set[str]] = None
        if full or not tem_linhas:
            # reconcilia: purga tudo (inclui >24m) e recomputa a janela inteira
            s.query(RatioMensal).filter(RatioMensal.empresa_id == empresa_id).delete(
                synchronize_session=False
            )
        else:
            # Auto-mantém a janela: poda o que envelheceu além de 24m. Roda SEMPRE
            # (mesmo sem mês tocado) → a janela desliza sozinha e o legado >24m é
            # purgado na 1ª coleta pós-deploy, sem --full manual.
            s.query(RatioMensal).filter(
                RatioMensal.empresa_id == empresa_id,
                RatioMensal.periodo < cutoff,
            ).delete(synchronize_session=False)
            if meses is None:
                ult = (
                    s.query(func.max(RatioMensal.gerado_em))
                    .filter(RatioMensal.empresa_id == empresa_id)
                    .scalar()
                )
                q_toc = s.query(periodo_expr).filter(
                    Verbatim.empresa_id == empresa_id,
                    Verbatim.data_criacao_original.isnot(None),
                )
                if ult is not None:
                    q_toc = q_toc.filter(
                        or_(Verbatim.data_coleta > ult, Verbatim.reclassificado_em > ult)
                    )
                meses = {m for (m,) in q_toc.distinct().all() if m}
            meses_alvo = {m for m in meses if m >= cutoff}
            if not meses_alvo:
                s.commit()  # poda já aplicada
                return 0
            # delete escopado só dos meses tocados (idempotente, dentro da janela)
            s.query(RatioMensal).filter(
                RatioMensal.empresa_id == empresa_id,
                RatioMensal.periodo.in_(meses_alvo),
            ).delete(synchronize_session=False)

        locais = {
            loc.id: loc.agrupamento_id
            for loc in s.query(Local.id, Local.agrupamento_id).filter(
                Local.empresa_id == empresa_id
            )
        }
        q = s.query(
            Verbatim.local_id,
            Verbatim.subpilar,
            periodo_expr.label("periodo"),
            Verbatim.tipo,
            func.count(Verbatim.id),
        ).filter(
            Verbatim.empresa_id == empresa_id,
            Verbatim.subpilar.isnot(None),
            Verbatim.data_criacao_original.isnot(None),
            periodo_expr >= cutoff,  # janela de 24m
        )
        if meses_alvo is not None:
            q = q.filter(periodo_expr.in_(meses_alvo))
        rows = q.group_by(Verbatim.local_id, Verbatim.subpilar, "periodo", Verbatim.tipo).all()

        agg: Dict[Tuple[Optional[int], str, str], Dict[str, int]] = {}
        for local_id, sub, periodo, tipo, n in rows:
            if sub not in _SUBPILARES:
                continue
            cell = agg.setdefault(
                (local_id, sub, periodo),
                {"promotor": 0, "conversivel": 0, "detrator": 0, "total": 0},
            )
            cell["total"] += int(n)
            if tipo in _TIPOS:
                cell[tipo] += int(n)

        now = datetime.utcnow()
        mappings: List[Dict[str, Any]] = [
            {
                "empresa_id": empresa_id,
                "local_id": local_id,
                "agrupamento_id": locais.get(local_id),
                "subpilar": sub,
                "periodo": periodo,
                "promotor": c["promotor"],
                "conversivel": c["conversivel"],
                "detrator": c["detrator"],
                "total": c["total"],
                "ratio": calcular_ratio(c["promotor"], c["detrator"]),
                "gerado_em": now,  # bulk_insert NÃO aplica o default do modelo
            }
            for (local_id, sub, periodo), c in agg.items()
        ]
        if mappings:
            s.bulk_insert_mappings(RatioMensal, mappings)
        s.commit()
    return len(agg)
