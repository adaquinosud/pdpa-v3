"""Probe read-only do HISTÓRICO temporal disponível pra anomalia-por-tema.

Decide se o eixo Y do Índice de Propagação (aceleração, exige >=3 meses de datas
distintas por tema — TREND_MIN_MESES) roda agora ou espera acumular histórico.
Read-only. Usa a MESMA contagem de meses do motor (fmt_ano_mes sobre
data_criacao_original, joins de _detectar_trend) pra bater exato.

Uso (linha curta no Shell do Render):
    PYTHONPATH=. python3 scripts/probe_hist_temas.py
    PYTHONPATH=. python3 scripts/probe_hist_temas.py 16 17 42
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import distinct, func  # noqa: E402

from src.anomalias.camada2 import TREND_MIN_MESES  # noqa: E402
from src.models.anomalia import AnomaliaDetectada, RatioMensal, TemaSnapshot  # noqa: E402
from src.models.empresa import Empresa  # noqa: E402
from src.models.temas import Tema, VerbatimTema  # noqa: E402
from src.models.verbatim import Verbatim  # noqa: E402
from src.utils.db import db_session  # noqa: E402
from src.utils.sql import fmt_ano_mes  # noqa: E402

IDS_DEFAULT = [16, 17]


def _por_empresa(s, eid: int) -> None:
    emp = s.get(Empresa, eid)
    print(f"\n===== {emp.nome if emp else '(não encontrada)'} (id {eid}) =====")
    if emp is None:
        return

    mes_col = fmt_ano_mes(Verbatim.data_criacao_original)

    # (1) meses distintos em ratios_mensais (span do histórico usado no eixo temporal)
    periodos_rm = sorted(
        p for (p,) in s.query(RatioMensal.periodo).filter(RatioMensal.empresa_id == eid).distinct()
    )
    print(
        f"(1) ratios_mensais: {len(periodos_rm)} mes(es) distinto(s)"
        + (f" [{periodos_rm[0]} .. {periodos_rm[-1]}]" if periodos_rm else "")
    )

    # (2) span das datas originais dos verbatins + nº de meses distintos
    mn, mx = (
        s.query(func.min(Verbatim.data_criacao_original), func.max(Verbatim.data_criacao_original))
        .filter(Verbatim.empresa_id == eid, Verbatim.data_criacao_original.isnot(None))
        .one()
    )
    n_meses_vb = (
        s.query(func.count(distinct(mes_col)))
        .filter(Verbatim.empresa_id == eid, Verbatim.data_criacao_original.isnot(None))
        .scalar()
    ) or 0
    print(
        f"(2) data_criacao_original: {n_meses_vb} mes(es) distinto(s)"
        f" | span {str(mn)[:10]} -> {str(mx)[:10]}"
    )

    # (3) temas ativos com >=TREND_MIN_MESES meses de datas distintas (elegíveis a trend)
    #     mesma query do _detectar_trend (Tema ativo + VerbatimTema.bucket_chave + data)
    rows = (
        s.query(Tema.id, mes_col)
        .join(VerbatimTema, VerbatimTema.tema_id == Tema.id)
        .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
        .filter(
            Tema.empresa_id == eid,
            Tema.ativo.is_(True),
            VerbatimTema.bucket_chave.isnot(None),
            Verbatim.data_criacao_original.isnot(None),
        )
        .distinct()
        .all()
    )
    meses_por_tema: dict = {}
    for tid, mes in rows:
        meses_por_tema.setdefault(tid, set()).add(mes)
    elegiveis = sum(1 for m in meses_por_tema.values() if len(m) >= TREND_MIN_MESES)
    rasos = len(meses_por_tema) - elegiveis
    print(
        f"(3) temas ativos com datas: {len(meses_por_tema)} | "
        f">= {TREND_MIN_MESES} meses (ELEGÍVEIS a trend): {elegiveis} | "
        f"< {TREND_MIN_MESES} meses (novo/→): {rasos}"
    )

    # (4) períodos distintos em temas_snapshot
    periodos_snap = sorted(
        p
        for (p,) in s.query(TemaSnapshot.periodo).filter(TemaSnapshot.empresa_id == eid).distinct()
    )
    print(
        f"(4) temas_snapshot: {len(periodos_snap)} período(s) distinto(s)"
        + (f" {periodos_snap}" if periodos_snap else "")
    )

    # (5) anomalias tipo=tema já gravadas (com tendencia/direcao)
    anoms = (
        s.query(AnomaliaDetectada.tendencia, AnomaliaDetectada.direcao)
        .filter(AnomaliaDetectada.empresa_id == eid, AnomaliaDetectada.tipo == "tema")
        .all()
    )
    print(f"(5) anomalias_detectadas tipo=tema: {len(anoms)}")
    if anoms:
        from collections import Counter

        dist = Counter((t or "—", d or "—") for t, d in anoms)
        for (tend, direc), n in sorted(dist.items(), key=lambda x: -x[1]):
            print(f"      tendencia={tend} · direcao={direc}: {n}")


def main(ids: list[int]) -> None:
    with db_session() as s:
        for eid in ids:
            _por_empresa(s, eid)


if __name__ == "__main__":
    args = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else IDS_DEFAULT
    main(args)
