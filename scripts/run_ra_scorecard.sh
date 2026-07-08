#!/bin/bash
# Cron DEDICADO do scorecard RA (Fatia 4.5b). BARATO (~US$0,055/fonte), gate 7d
# por-fonte → efetivamente semanal rodando diário. Wrapper fino do orquestrador.
#
# Uso:
#   bash scripts/run_ra_scorecard.sh             # coleta (barato)
#   bash scripts/run_ra_scorecard.sh --dry-run   # só lista
set +e
cd "$(dirname "$0")/.."
PY="$([ -x .venv/bin/python ] && echo .venv/bin/python || echo python)"
PYTHONPATH=. "$PY" scripts/coleta_scorecard_todas.py "$@"
