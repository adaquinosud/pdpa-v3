#!/bin/bash
# Cron MENSAL de threads RA por coorte (Fatia 4). Wrapper fino do orquestrador
# Python. AÇÃO PAGA — passe --dry-run pra listar o plano + custo sem coletar.
#
# Uso:
#   bash scripts/run_ra_coortes.sh --dry-run   # lista, não coleta
#   bash scripts/run_ra_coortes.sh             # coleta (PAGO)
set +e
cd "$(dirname "$0")/.."
PY="$([ -x .venv/bin/python ] && echo .venv/bin/python || echo python)"
PYTHONPATH=. "$PY" scripts/coleta_coortes_todas.py "$@"
