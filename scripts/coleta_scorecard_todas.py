"""Cron DEDICADO do scorecard RA (Fatia 4.5b). BARATO (~US$0,055/fonte) e
INDEPENDENTE do coleta_noturna_ativa: enumera fontes RA ATIVAS de empresas com
``scorecard_ra_ativo=TRUE`` e roda ``coletar_scorecard`` (gate 7d por-fonte via
FonteReputacao.coletado_em → efetivamente semanal, rodando o cron diário).

Alimenta a Vitrine (Bloco A) + popula ``complaints30Days`` — o que faz o dry-run de
threads mostrar custo REAL (não placeholder). RA saiu do noturno; o scorecard vive
aqui, as threads no cron de coorte.

Uso:
    PYTHONPATH=. python scripts/coleta_scorecard_todas.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.coletor.reclame_aqui import coletar_scorecard  # noqa: E402
from src.models.empresa import Empresa  # noqa: E402
from src.models.fonte import Fonte  # noqa: E402
from src.utils.db import db_session  # noqa: E402


def fontes_scorecard_elegiveis() -> List[int]:
    """fonte_ids RA ativas de empresas com ``scorecard_ra_ativo=TRUE`` — INDEPENDENTE
    de coleta_noturna_ativa (o scorecard é barato e alimenta a Vitrine sempre)."""
    with db_session() as s:
        rows = (
            s.query(Fonte.id)
            .join(Empresa, Empresa.id == Fonte.empresa_id)
            .filter(
                Empresa.scorecard_ra_ativo.is_(True),
                Fonte.ativo.is_(True),
                Fonte.conector_tipo == "reclame_aqui",
            )
            .order_by(Fonte.id)
            .all()
        )
    return [r[0] for r in rows]


def main(dry_run: bool) -> None:
    # Instrumentação (frente Fatia 1): cada coleta REAL vira ColetaExecucao (falha
    # Apify → status='erro' → visível no Monitoramento). O pré-gate de cadência 7d fica
    # FORA: só instrumenta o que de fato coleta — senão o cron diário encheria o painel
    # de 'concluido' vazio (skip diário) e esconderia o sinal.
    from src.coletor.orquestrador import _coletar_fonte_direto
    from src.coletor.reclame_aqui import em_cadencia_scorecard

    fontes = fontes_scorecard_elegiveis()
    modo = "DRY-RUN (não coleta)" if dry_run else "REAL"
    print(f"[scorecard] {modo} — {len(fontes)} fonte(s) RA com scorecard_ra_ativo")
    for fonte_id in fontes:
        with db_session() as s:
            fonte = s.get(Fonte, fonte_id)
            if fonte is None:
                continue
            em_cadencia = (not dry_run) and em_cadencia_scorecard(s, fonte_id)
        if em_cadencia:  # gate 7d → não coleta, não registra
            print(f"    · fonte {fonte_id} → pulado(cadência)")
            continue
        if dry_run:
            print(f"    · fonte {fonte_id} → coletar_scorecard (gate 7d) ~US$0,055")
            continue
        # force=True: pula o re-check interno de cadência (já checado acima).
        st = _coletar_fonte_direto(
            fonte_id, coletor_override=lambda f: coletar_scorecard(f, force=True)
        )
        tag = "erro" if st.get("falhou_apify") else f"reputacao={st.get('reputacao')}"
        print(f"    · fonte {fonte_id} → {tag}")
    print("[scorecard] fim")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Cron dedicado do scorecard RA (barato).")
    ap.add_argument("--dry-run", action="store_true", help="lista as fontes, sem coletar")
    args = ap.parse_args()
    main(dry_run=args.dry_run)
