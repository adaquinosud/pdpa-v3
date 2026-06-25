#!/usr/bin/env bash
# Pre-deploy do Render (CP-Pesquisa-F1.4 / fix-&&).
#
# O preDeployCommand do Render NÃO roda num shell: ele tokeniza a string por
# espaço e dá exec direto. Por isso "alembic ... && python ..." quebrava — o
# alembic recebia "&&" como argumento (argparse → exit 2) e o gate nem rodava.
# A solução robusta é um script único (preDeployCommand = "bash scripts/deploy_pre.sh",
# só 2 tokens), onde o encadeamento roda num shell de verdade.
#
# Passos (ordem importa): migração ANTES do tráfego; depois o gate de calibração
# do LLM-juiz (fail-open em erro de infra; bloqueia só falso-positivo nos limpos).
set -euo pipefail

echo "[deploy_pre] alembic upgrade head"
alembic upgrade head

echo "[deploy_pre] gate de calibração do juiz"
python scripts/gate_calibracao_juiz.py
