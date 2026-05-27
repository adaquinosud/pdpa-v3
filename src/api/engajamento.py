"""Engajamento — indicador básico (pré-condição operacional do PDPA).

NÃO é 5º pilar: sinaliza se há *volume/diversidade/regularidade* suficientes para
os demais indicadores não serem especulativos. Três usos (Bloco Engajamento):

1. **Índice de Engajamento** (0-100) — 4º indicador, ao lado de Índice Geral,
   Previsibilidade e Concentração.
2. **Selo de confiança** por volume (🟢 ≥30 / 🟡 10-30 / 🔴 <10) — anota
   confiabilidade nas telas; não muda fórmula.
3. **Modulação do Leaderboard** — score × (engajamento/100) + gate de volume.

Fórmula: ``(volume_norm × 0.5) + (diversidade × 0.3) + (consistencia × 0.2)`` ×100.
- volume_norm = log1p(volume) / log1p(volume_máx do escopo) — log1p evita log(0/1).
- diversidade = fontes ativas / fontes cadastradas (do próprio escopo: loja→fontes
  da loja; empresa→fontes da empresa). Cap 1.0.
- consistencia = meses com verbatim / total de meses na janela.
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

# Pesos da fórmula (Cap. 4 — Indicadores Quantitativos; pendência editorial).
PESO_VOLUME = 0.5
PESO_DIVERSIDADE = 0.3
PESO_CONSISTENCIA = 0.2

# Gate/selo de confiança estatística por volume.
VOLUME_CONFIANCA_ALTA = 30
VOLUME_CONFIANCA_MEDIA = 10  # 10-30 média; < 10 baixa


def indice_engajamento(
    volume: int,
    volume_max: int,
    fontes_ativas: int,
    fontes_cadastradas: int,
    meses_com_verbatim: int,
    meses_total: int,
) -> int:
    """Índice de Engajamento (0-100) do escopo. Componentes em [0,1], pesos
    0.5/0.3/0.2. Robusto a zero (log1p, denominadores defendidos)."""
    vol_norm = math.log1p(max(0, volume)) / math.log1p(volume_max) if volume_max > 0 else 0.0
    diversidade = min(1.0, fontes_ativas / fontes_cadastradas) if fontes_cadastradas > 0 else 0.0
    consistencia = (meses_com_verbatim / meses_total) if meses_total > 0 else 0.0
    bruto = (
        vol_norm * PESO_VOLUME + diversidade * PESO_DIVERSIDADE + consistencia * PESO_CONSISTENCIA
    )
    return round(min(1.0, max(0.0, bruto)) * 100)


def fator_confianca(indice_eng: int) -> float:
    """Fator de modulação do Leaderboard = engajamento normalizado (0-1)."""
    return max(0.0, min(100, indice_eng)) / 100.0


def selo_confianca(volume: int) -> Tuple[str, str, str]:
    """Selo de confiança estatística por volume → (nivel, emoji, classe Tailwind)."""
    if volume >= VOLUME_CONFIANCA_ALTA:
        return ("alta", "🟢", "text-emerald-600")
    if volume >= VOLUME_CONFIANCA_MEDIA:
        return ("media", "🟡", "text-amber-600")
    return ("baixa", "🔴", "text-rose-600")


def volume_suficiente_ranking(volume: int) -> bool:
    """Gate do Leaderboard: abaixo do mínimo, vai p/ 'volume insuficiente'."""
    return volume >= VOLUME_CONFIANCA_MEDIA


def componentes_engajamento(
    volume: int,
    volume_max: int,
    fontes_ativas: int,
    fontes_cadastradas: int,
    meses_com_verbatim: int,
    meses_total: int,
) -> Dict[str, float]:
    """Componentes normalizados (0-1) — p/ exibir o detalhe do índice no card."""
    return {
        "volume_norm": round(
            math.log1p(max(0, volume)) / math.log1p(volume_max) if volume_max > 0 else 0.0, 3
        ),
        "diversidade": round(
            min(1.0, fontes_ativas / fontes_cadastradas) if fontes_cadastradas > 0 else 0.0, 3
        ),
        "consistencia": round((meses_com_verbatim / meses_total) if meses_total > 0 else 0.0, 3),
    }
