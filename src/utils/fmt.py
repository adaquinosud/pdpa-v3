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


# Rótulo ACENTUADO de faixa para EXIBIÇÃO. O valor GRAVADO fica cru (é chave de comparação
# em código e teste) — só a tela/impresso acentua, via ``| acento``. Não ALTERAR o dado.
_ACENTO = {
    "critico": "Crítico",
    "fraco": "Fraco",
    "atencao": "Atenção",
    "bom": "Bom",
    "excelente": "Excelente",
    "saudavel": "Saudável",
    "erratico": "Errático",
    "medio": "Médio",
    "estavel": "Estável",
    "sistemico": "Sistêmico",
    "cirurgico": "Cirúrgico",
    "misto": "Misto",
    "indisponivel": "Indisponível",
}


def acento(s) -> str:
    """Faixa/rótulo cru → forma acentuada para exibição (``critico`` → ``Crítico``). Fora do
    dicionário devolve o próprio valor. None → "—"."""
    if s is None:
        return "—"
    return _ACENTO.get(str(s).lower(), str(s))
