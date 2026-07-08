"""Cron MENSAL de threads RA por COORTE (Fatia 4). Cadência A (mensal + aposentadoria
por ``fechada``): refaz as coortes ativas (``ra_coortes_ativas``) de cada fonte RA de
empresa ligada, rebuscando a janela FECHADA por mês (dateFrom/dateTo) — matura a
coorte estável, preenche buracos da deslizante (até ``ra_coortes_ativas`` meses).

AÇÃO PAGA (Apify PPE ~US$0,025/reclamação). Idempotente por mês (o ledger
``FonteCoorteColeta`` pula coorte já coletada no mês). ``--dry-run`` lista o plano +
custo estimado SEM coletar — use antes do 1º run real.

Uso:
    PYTHONPATH=. python scripts/coleta_coortes_todas.py --dry-run   # lista, não coleta
    PYTHONPATH=. python scripts/coleta_coortes_todas.py             # coleta (PAGO)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.coletor.reclame_aqui import (  # noqa: E402
    CUSTO_POR_CASO_USD,
    CUSTO_START_USD,
    coletar_coorte,
    planejar_coortes,
)
from src.models.empresa import Empresa  # noqa: E402
from src.models.fonte import Fonte  # noqa: E402
from src.models.fonte_reputacao import FonteReputacao  # noqa: E402
from src.utils.db import db_session  # noqa: E402


def fontes_ra_elegiveis() -> List[int]:
    """fonte_ids RA ativas de empresas com ``coleta_noturna_ativa=TRUE``."""
    with db_session() as s:
        rows = (
            s.query(Fonte.id)
            .join(Empresa, Empresa.id == Fonte.empresa_id)
            .filter(
                Empresa.coleta_noturna_ativa.is_(True),
                Fonte.ativo.is_(True),
                Fonte.conector_tipo == "reclame_aqui",
            )
            .order_by(Fonte.id)
            .all()
        )
    return [r[0] for r in rows]


def _volume_mes(session, fonte_id: int):
    """complaints30Days do scorecard mais recente (proxy do volume por coorte-mês)."""
    rep = (
        session.query(FonteReputacao)
        .filter_by(fonte_id=fonte_id)
        .order_by(FonteReputacao.coletado_em.desc())
        .first()
    )
    if rep is None or not rep.raw_json:
        return None
    try:
        return json.loads(rep.raw_json).get("complaints30Days")
    except (ValueError, TypeError):
        return None


def _custo_coorte(volume) -> float:
    return (volume or 0) * CUSTO_POR_CASO_USD + CUSTO_START_USD


def main(dry_run: bool) -> None:
    fontes = fontes_ra_elegiveis()
    modo = "DRY-RUN (não coleta)" if dry_run else "REAL (PAGO)"
    print(f"[coortes] {modo} — {len(fontes)} fonte(s) RA elegível(is)")
    custo_total = 0.0
    for fonte_id in fontes:
        with db_session() as s:
            fonte = s.get(Fonte, fonte_id)
            if fonte is None:
                continue
            s.expunge(fonte)
            plano = planejar_coortes(s, fonte)
            vol = _volume_mes(s, fonte_id)
        a_coletar = [p for p in plano if p["acao"] == "coletar"]
        custo_fonte = sum(_custo_coorte(vol) for _ in a_coletar)
        custo_total += custo_fonte
        print(
            f"[coortes] fonte {fonte_id}: {len(a_coletar)} coorte(s) a coletar "
            f"(vol/mês={vol}) ~US${custo_fonte:.2f}"
        )
        for p in plano:
            if p["acao"] == "skip":
                print(f"    · {p['coorte']} SKIP ({p['motivo']})")
            else:
                print(
                    f"    · {p['coorte']} COLETAR [{p['date_from']}..{p['date_to']}] "
                    f"idade={p['idade_meses']}m nnt={p['n_nao_terminais']}"
                )
                if not dry_run:
                    st = coletar_coorte(fonte, p)
                    print(
                        f"        → novos={st['casos_novos']} atual={st['casos_atualizados']} "
                        f"aband={st['abandonados']} nao_rastr={st['nao_rastreado']} "
                        f"fechada={st['fechada']}"
                    )
    print(f"[coortes] fim — custo estimado do run: ~US${custo_total:.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Cron mensal de threads RA por coorte.")
    ap.add_argument("--dry-run", action="store_true", help="lista o plano + custo, sem coletar")
    args = ap.parse_args()
    main(dry_run=args.dry_run)
