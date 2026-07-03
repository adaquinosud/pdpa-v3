#!/bin/bash
# Cron MENSAL da Reputação em IA (frente IA · G5). Roda a sonda das empresas alvo
# (≥1 verbatim) e encadeia classificação + defasagem. Wrapper fino do script Python.
#
# Uso:
#   bash scripts/run_sonda_ia.sh                 # sonda o mês atual
#   bash scripts/run_sonda_ia.sh --dry-run       # só lista as empresas
#   bash scripts/run_sonda_ia.sh --competencia 2026-07
set +e
cd "$(dirname "$0")/.."

# Em dev usa o .venv; no container (Render) o python do PATH (/opt/venv).
PY="$([ -x .venv/bin/python ] && echo .venv/bin/python || echo python)"

PYTHONPATH=. "$PY" scripts/sonda_ia_mensal.py "$@"
