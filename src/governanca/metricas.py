"""Helpers de cálculo e recálculo da Lente de Governança (Bloco LG / CP-LG-0).

A escala **Proximity** (0-100) é SEPARADA das faixas operacionais de ratio
(``src/api/painel.py:FAIXAS_RATIO``): ela mede distância da excelência
*consolidada* (ratio 9.0 = cap do sistema), não do piso da faixa "excelente".
"""

from __future__ import annotations

from typing import Dict, Optional, Sequence

# Âncoras da escala Proximity (ver docs/BLOCO_LG.md):
#   ratio 0.5 (crítico)              → Proximity 0
#   ratio 9.0 (excelência/cap)       → Proximity 100
PROXIMITY_RATIO_PISO = 0.5
PROXIMITY_RATIO_TETO = 9.0


def calcular_proximity(ratio: Optional[float]) -> Optional[float]:
    """Proximity 0-100 a partir do ratio: ``(ratio-0.5)/(9.0-0.5)*100``, cap [0,100].

    ``None`` (sem dado suficiente — floor 10 verbatins) → ``None``. Calibração:
    0.5→0 · 2.0→~17.6 · 5.0→~52.9 · 9.0→100.
    """
    if ratio is None:
        return None
    span = PROXIMITY_RATIO_TETO - PROXIMITY_RATIO_PISO
    p = (ratio - PROXIMITY_RATIO_PISO) / span * 100.0
    return max(0.0, min(100.0, p))


def calcular_gini(distribuicao: Sequence[float]) -> Optional[float]:
    """Coeficiente de Gini formal de ``distribuicao`` (0 = distribuído, →1 = concentrado).

    ``distribuicao`` = valores não-negativos (ex.: nº de detratores por loja).
    Retorna ``None`` se vazia ou soma zero (nada a concentrar). Fórmula com
    valores ordenados crescente (1-based ``i``):
    ``G = 2·Σ(i·x_i)/(n·Σx) − (n+1)/n``.
    """
    vals = sorted(float(v) for v in distribuicao)
    n = len(vals)
    if n == 0:
        return None
    total = sum(vals)
    if total <= 0:
        return None
    cum = sum((i + 1) * v for i, v in enumerate(vals))
    gini = (2.0 * cum) / (n * total) - (n + 1.0) / n
    return max(0.0, min(1.0, gini))


def recalcular_governanca(empresa_id: int, *, skip_unchanged: bool = True) -> Dict[str, int]:
    """Recálculo das métricas de governança (Proximity/Gini) por escopo.

    **CP-LG-0: esqueleto no-op** — apenas costurado no pipeline pós-coleta
    (passo 7.5) para fixar o ponto de integração. O cálculo real (Proximity per
    subpilar/pilar/loja e Gini por escopo) entra no CP-LG-1+, persistindo em
    ``proximity_calculations`` / ``gini_concentracao`` e usando
    ``src.utils.hashing.hash_payload`` para o skip por hash.
    """
    return {"proximity": 0, "gini": 0, "pulados": 0}
