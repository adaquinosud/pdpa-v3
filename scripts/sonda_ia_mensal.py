"""Sonda de Reputação em IA — rodada MENSAL de TODAS as empresas alvo.

Encadeia, por empresa: ``sondar_empresa`` (3 modelos × 3 perguntas × N reps →
respostas raw) → ``processar_sonda`` (classifica avaliações na régua PDPA +
sintetiza a leitura identidade×ORIGEM/encaminhamentos + cruza a defasagem
IA×diagnóstico). Idempotente por competência (não re-cobra no mesmo mês).

  --competencia YYYY-MM : força a competência (default: mês atual).
  --dry-run             : lista as empresas alvo, SEM sondar (custo zero).

Roda no cron do Render (``run_sonda_ia.sh`` é o wrapper). Custo ~US$0,55/empresa.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.sonda_ia.sonda import _empresas_alvo, rodar_sonda_mensal  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Sonda de Reputação em IA (mensal).")
    ap.add_argument("--competencia", default=None, help="YYYY-MM (default: mês atual)")
    ap.add_argument("--dry-run", action="store_true", help="lista as empresas alvo, sem sondar")
    args = ap.parse_args()

    competencia = args.competencia or date.today().strftime("%Y-%m")
    alvo = _empresas_alvo()
    print(f"[sonda_ia] competência={competencia} · empresas alvo={len(alvo)}")

    if args.dry_run:
        print(f"[sonda_ia] DRY-RUN — sondaria {len(alvo)} empresa(s): {alvo}")
        return 0

    stats = rodar_sonda_mensal(competencia, empresa_ids=alvo)
    print(
        f"[sonda_ia] FIM: sondadas={stats['sondadas']} puladas={stats['puladas']} "
        f"respostas={stats['respostas']} custo=US${stats['custo_usd']} erros={stats['erros']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
