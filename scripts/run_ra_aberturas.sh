#!/bin/bash
# Cron SEMANAL de ABERTURAS RA (modo padrão) — frente ra-cron-aberturas. Wrapper fino
# do orquestrador Python. AÇÃO PAGA — passe --dry-run pra listar o plano + custo sem coletar.
#
# Uso:
#   bash scripts/run_ra_aberturas.sh --dry-run   # lista, não coleta
#   bash scripts/run_ra_aberturas.sh             # coleta (PAGO)
set +e
cd "$(dirname "$0")/.."
PY="$([ -x .venv/bin/python ] && echo .venv/bin/python || echo python)"
PYTHONPATH=. "$PY" scripts/coleta_aberturas_todas.py "$@"
