#!/bin/bash
# Pipeline noturno de UMA empresa: coleta → pipeline-pos-coleta → relatório markdown.
# CP-#2: rotina de produto, parametrizada por empresa (id ou nome). Um cron por
# empresa no Render aponta pra este script com a empresa como argumento.
#
# Uso: scripts/run_noturna.sh <empresa-id-ou-nome>
#   ex: scripts/run_noturna.sh 4
#       scripts/run_noturna.sh "BH Airport"
#
# Fontes quebradas são desativadas via Fonte.ativo=False (não há EXCLUDE
# hardcoded). Override pontual: export PDPA_NOTURNA_EXCLUDE_FONTE_IDS="..." antes.
# Cada passo escreve seu próprio log; o gerador consolida tudo.
# NÃO PARA POR NADA: erros loga e segue.

set +e  # falhas individuais não abortam o pipeline
cd "$(dirname "$0")/.."

EMPRESA="$1"
if [ -z "$EMPRESA" ]; then
    echo "uso: $0 <empresa-id-ou-nome>" >&2
    exit 2
fi

ROOT="$(pwd)"
TS=$(date +%Y%m%d_%H%M%S)
PIPELINE_LOG="$ROOT/data/pipeline_noturno_${TS}.log"

exec > >(tee -a "$PIPELINE_LOG") 2>&1

echo "════════════════════════════════════════════════════════════════"
echo "[pipeline] início $(date -Iseconds) — empresa=${EMPRESA}"
echo "[pipeline] log master: $PIPELINE_LOG"
echo "════════════════════════════════════════════════════════════════"

# ── Passo 1: coleta noturna (fontes ativas da empresa) ─────────────────
echo ""
echo "[pipeline] ▶ PASSO 1/3 — coleta noturna (fontes ativas de ${EMPRESA})"
echo "[pipeline]   caps: MAX_USD=30, MAX_HOURS=8 (EXCLUDE via Fonte.ativo=False)"
echo "[pipeline]   início coleta: $(date -Iseconds)"

PDPA_NOTURNA_MAX_USD=30 \
PDPA_NOTURNA_MAX_HOURS=8 \
PYTHONPATH=. .venv/bin/python scripts/coleta_noturna.py --empresa="$EMPRESA"
COLETA_EXIT=$?
echo "[pipeline]   coleta saiu com código $COLETA_EXIT"

# ── Passo 2: pipeline pós-coleta (Caminho A — substitui temas-extrair legado) ──
echo ""
echo "[pipeline] ▶ PASSO 2/3 — pipeline-pos-coleta empresa=${EMPRESA}"
echo "[pipeline]   encadeia: classifica novos → embeddings → temas → cruzamentos → ações"
echo "[pipeline]   roda só se novos >= limiar (default 50); aplica janela 180d"
echo "[pipeline]   início: $(date -Iseconds)"

FLASK_APP=src.app:create_app .venv/bin/flask pipeline-pos-coleta \
    --empresa="$EMPRESA"
CP6_EXIT=$?
echo "[pipeline]   pós-coleta saiu com código $CP6_EXIT"

# ── Passo 3: gerador de relatório markdown ─────────────────────────────
echo ""
echo "[pipeline] ▶ PASSO 3/3 — gerador de relatório markdown"
echo "[pipeline]   início gerador: $(date -Iseconds)"

PYTHONPATH=. .venv/bin/python scripts/gen_relatorio_noturna.py --empresa="$EMPRESA"
GEN_EXIT=$?
echo "[pipeline]   gerador saiu com código $GEN_EXIT"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "[pipeline] FIM $(date -Iseconds)"
echo "[pipeline] coleta=$COLETA_EXIT  cp6=$CP6_EXIT  gerador=$GEN_EXIT"
ls -1t data/relatorio_noturna_*.md 2>/dev/null | head -1 | xargs -I{} echo "[pipeline] relatório final: {}"
echo "════════════════════════════════════════════════════════════════"
