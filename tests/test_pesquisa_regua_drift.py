"""Anti-drift entre as 3 representações da régua (Camada 1 mínima).

A régua existe em três lugares hand-written que "espelham a seção 9 do manual"
independentemente: REGUA_GUIA (prompt do gerador), REGUA_JUIZ (prompt do juiz) e
validador.py (checks em código). Eles podem DIVERGIR com o tempo. Este teste é o
ALARME: falha se o REGUA_GUIA não menciona toda regra que o validador BLOQUEIA. A
fonte única completa (regra escrita uma vez, usada nos 3) fica pra depois.
"""

from __future__ import annotations

from src.pesquisa.regua import REGUA_GUIA
from src.pesquisa.validador import REGRAS_BLOQUEANTES


def test_regua_guia_menciona_toda_regra_bloqueante():
    """Cada regra que o validador pode bloquear tem de estar citada no prompt do
    gerador — senão o gerador escreve sem saber de uma regra que depois o reprova."""
    guia = REGUA_GUIA.upper()
    faltando = []
    for regra in REGRAS_BLOQUEANTES:
        marcador = "ESCOPO" if regra == "escopo" else f"REGRA {regra}"
        if marcador not in guia:
            faltando.append(marcador)
    assert not faltando, (
        f"REGUA_GUIA não menciona {faltando} — regra bloqueante no validador.py sem "
        "correspondência no prompt do gerador (divergência entre guia e validador)."
    )
