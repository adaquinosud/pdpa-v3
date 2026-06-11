#!/bin/bash
# Cron noturno GENÉRICO (CP-noturna-toggle): roda a noturna nas empresas com
# coleta_noturna_ativa=TRUE (+ ≥1 fonte ativa com coletor). Substitui o cron fixo
# `run_noturna.sh 4`. Wrapper fino do orquestrador Python (que faz o loop por
# empresa, reusando run_noturna.sh). Passe --dry-run pra listar sem coletar.
#
# Uso:
#   bash scripts/run_noturna_todas.sh             # coleta as empresas ligadas
#   bash scripts/run_noturna_todas.sh --dry-run   # só lista
set +e
cd "$(dirname "$0")/.."

# Em dev usa o .venv; no container (Render) o python do PATH (/opt/venv).
PY="$([ -x .venv/bin/python ] && echo .venv/bin/python || echo python)"

PYTHONPATH=. "$PY" scripts/coleta_noturna_todas.py "$@"
