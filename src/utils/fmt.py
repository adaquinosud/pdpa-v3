"""Formatação numérica pt-BR (fonte ÚNICA, sem literal de formatação espalhado).

``virg``: decimal com VÍRGULA — toda tela e todo impresso em português usam este helper,
nunca ``'%.2f'|format`` cru (que sai com ponto). Registrado como filtro Jinja em app.py.
"""

from __future__ import annotations

from typing import Optional


def virg(x: Optional[float], casas: int = 2) -> str:
    """``1.41 -> "1,41"``. None / não-numérico → "—". ``casas`` = casas decimais."""
    if x is None:
        return "—"
    try:
        return f"{float(x):.{casas}f}".replace(".", ",")
    except (ValueError, TypeError):
        return "—"
