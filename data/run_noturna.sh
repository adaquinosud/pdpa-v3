#!/bin/bash
# Pipeline noturno: coleta Google BH Airport → CP-6 temas-extrair → relatório markdown.
# Cada passo escreve seu próprio log; o gerador consolida tudo.
# NÃO PARA POR NADA: erros loga e segue.

set +e  # falhas individuais não abortam o pipeline
cd "$(dirname "$0")/.."

ROOT="$(pwd)"
TS=$(date +%Y%m%d_%H%M%S)
PIPELINE_LOG="$ROOT/data/pipeline_noturno_${TS}.log"

exec > >(tee -a "$PIPELINE_LOG") 2>&1

echo "════════════════════════════════════════════════════════════════"
echo "[pipeline] início $(date -Iseconds)"
echo "[pipeline] log master: $PIPELINE_LOG"
echo "════════════════════════════════════════════════════════════════"

# ── Passo 1: coleta noturna (38 fontes Google) ─────────────────────────
echo ""
echo "[pipeline] ▶ PASSO 1/3 — coleta noturna 38 fontes Google BH Airport"
echo "[pipeline]   caps: MAX_USD=30, MAX_HOURS=8, EXCLUDE=82,83,84,85,86,129,131,132,135"
echo "[pipeline]   início coleta: $(date -Iseconds)"

PDPA_NOTURNA_EMPRESA="BH Airport" \
PDPA_NOTURNA_MAX_USD=30 \
PDPA_NOTURNA_MAX_HOURS=8 \
PDPA_NOTURNA_EXCLUDE_FONTE_IDS="82,83,84,85,86,129,131,132,135" \
PYTHONPATH=. .venv/bin/python data/coleta_noturna_confins.py
COLETA_EXIT=$?
echo "[pipeline]   coleta saiu com código $COLETA_EXIT"

# ── Passo 2: pipeline pós-coleta (Caminho A — substitui temas-extrair legado) ──
echo ""
echo "[pipeline] ▶ PASSO 2/3 — pipeline-pos-coleta empresa=4 (BH Airport)"
echo "[pipeline]   encadeia: classifica novos → embeddings → temas → cruzamentos → ações"
echo "[pipeline]   roda só se novos >= limiar (default 50); aplica janela 180d"
echo "[pipeline]   início: $(date -Iseconds)"

FLASK_APP=src.app:create_app .venv/bin/flask pipeline-pos-coleta \
    --empresa=4
CP6_EXIT=$?
echo "[pipeline]   pós-coleta saiu com código $CP6_EXIT"

# ── Passo 3: gerador de relatório markdown ─────────────────────────────
echo ""
echo "[pipeline] ▶ PASSO 3/3 — gerador de relatório markdown"
echo "[pipeline]   início gerador: $(date -Iseconds)"

PYTHONPATH=. .venv/bin/python data/gen_relatorio_noturna.py
GEN_EXIT=$?
echo "[pipeline]   gerador saiu com código $GEN_EXIT"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "[pipeline] FIM $(date -Iseconds)"
echo "[pipeline] coleta=$COLETA_EXIT  cp6=$CP6_EXIT  gerador=$GEN_EXIT"
ls -1t data/relatorio_noturna_*.md 2>/dev/null | head -1 | xargs -I{} echo "[pipeline] relatório final: {}"
echo "════════════════════════════════════════════════════════════════"
