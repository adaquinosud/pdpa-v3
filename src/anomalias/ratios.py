"""Série mensal de ratio P/D por (loja × subpilar) — base da Camada 1.

Constrói/atualiza ``ratios_mensais`` a partir dos verbatins classificados da
empresa (histórico COMPLETO, não a janela 180d). Idempotente: zera as linhas
da empresa antes de regravar.
"""

from __future__ import annotations

from typing import Dict, Tuple

from src.api.painel import SUBPILARES_ORDEM, calcular_ratio

_SUBPILARES = set(SUBPILARES_ORDEM)
_TIPOS = ("promotor", "conversivel", "detrator")


def recomputar_ratios_mensais(empresa_id: int) -> int:
    """(Re)constrói ``ratios_mensais`` da empresa. Devolve nº de linhas gravadas.

    Granularidade: ``(local_id, subpilar, ano-mês)``. Só verbatins com
    ``subpilar`` válido (12 subpilares), ``data_criacao_original`` e
    ``local_id`` (a anomalia de indicador é por loja, como no v2).
    """
    from sqlalchemy import func

    from src.models.anomalia import RatioMensal
    from src.models.local import Local
    from src.utils.sql import fmt_ano_mes
    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    with db_session() as s:
        s.query(RatioMensal).filter(RatioMensal.empresa_id == empresa_id).delete(
            synchronize_session=False
        )

    with db_session() as s:
        locais = {
            loc.id: loc.agrupamento_id
            for loc in s.query(Local.id, Local.agrupamento_id)
            .filter(Local.empresa_id == empresa_id)
            .all()
        }
        rows = (
            s.query(
                Verbatim.local_id,
                Verbatim.subpilar,
                fmt_ano_mes(Verbatim.data_criacao_original).label("periodo"),
                Verbatim.tipo,
                func.count(Verbatim.id),
            )
            .filter(
                Verbatim.empresa_id == empresa_id,
                Verbatim.local_id.isnot(None),
                Verbatim.subpilar.isnot(None),
                Verbatim.data_criacao_original.isnot(None),
            )
            .group_by(
                Verbatim.local_id,
                Verbatim.subpilar,
                "periodo",
                Verbatim.tipo,
            )
            .all()
        )

        agg: Dict[Tuple[int, str, str], Dict[str, int]] = {}
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

        n_linhas = 0
        for (local_id, sub, periodo), c in agg.items():
            s.add(
                RatioMensal(
                    empresa_id=empresa_id,
                    local_id=local_id,
                    agrupamento_id=locais.get(local_id),
                    subpilar=sub,
                    periodo=periodo,
                    promotor=c["promotor"],
                    conversivel=c["conversivel"],
                    detrator=c["detrator"],
                    total=c["total"],
                    ratio=calcular_ratio(c["promotor"], c["detrator"]),
                )
            )
            n_linhas += 1
    return n_linhas
