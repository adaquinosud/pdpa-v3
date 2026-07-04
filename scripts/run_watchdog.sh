#!/bin/bash
# CP-poscoleta-watchdog: rede de segurança do pós-coleta (a cada 6h no cron).
# Varre as empresas e retoma o pós-coleta das que ficaram com estado parcial
# (daemon-thread morta por redeploy). Lock por-empresa + cooldown 6h → idempotente
# e sem thrash. Roda no container cron, que sobrevive a redeploy do web.
set +e
cd "$(dirname "$0")/.."

PY="$([ -x .venv/bin/python ] && echo .venv/bin/python || echo python)"

PYTHONPATH=. FLASK_APP=src.app:create_app "$PY" -m flask pos-coleta-watchdog "$@"
