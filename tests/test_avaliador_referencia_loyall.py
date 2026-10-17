"""O caso de medição do site da Loyall: as duas leituras humanas de referência e a
pontuação da rodada 2, como o Alexandre escreveu em 17/10 antes de rodar.

Um subpilar conta como CERTO quando o veredito do app é o do consenso (nos 9 em que as
referências batem) ou qualquer um dos dois valores de referência (nos 3 em que não batem).
Alvo da rodada 2: pelo menos 9 de 12 certos, os errados a um degrau só, e pelo menos 3 Sim.
Rodada 1: pelo menos 1 Sim e no máximo 4 Não. Nas duas: zero alerta "Não com trecho achado".
"""

from __future__ import annotations

import json
from pathlib import Path

REF = json.loads(
    (Path(__file__).parent / "dados" / "site_loyall" / "referencia.json").read_text("utf-8")
)
DEGRAU = {"nao": 0, "parcial": 1, "sim": 2}


def aceitos(cod: str) -> set:
    return {REF["referencia_1"]["vereditos"][cod], REF["referencia_2"]["vereditos"][cod]}


def pontuar(app: dict) -> dict:
    """``app``: código do subpilar → veredito do app. Devolve certos, os errados com a
    distância em degraus até o valor aceito mais próximo, e o placar."""
    certos, errados = [], {}
    for cod, ver in app.items():
        ok = aceitos(cod)
        if ver in ok:
            certos.append(cod)
        else:
            errados[cod] = min(abs(DEGRAU[ver] - DEGRAU[x]) for x in ok)
    placar = {v: sum(1 for x in app.values() if x == v) for v in DEGRAU}
    return {"certos": certos, "errados": errados, "placar": placar}


def rodada_2_passa(app: dict) -> bool:
    p = pontuar(app)
    return (
        len(p["certos"]) >= 9
        and all(d == 1 for d in p["errados"].values())
        and p["placar"]["sim"] >= 3
    )


def test_as_referencias_batem_como_registrado():
    r1, r2 = REF["referencia_1"]["vereditos"], REF["referencia_2"]["vereditos"]
    consenso = {c for c in r1 if r1[c] == r2[c]}
    assert consenso == {"P1", "D1", "Pa1", "A2", "Pa2", "Pa3", "A3", "D2", "A1"}
    assert {c: aceitos(c) for c in ("P2", "P3", "D3")} == {
        "P2": {"parcial", "sim"},
        "P3": {"nao", "parcial"},
        "D3": {"parcial", "nao"},
    }
    for r, esperado in ((r1, (4, 5, 3)), (r2, (5, 4, 3))):
        assert tuple(list(r.values()).count(v) for v in ("sim", "parcial", "nao")) == esperado
    # as três diferenças são de um degrau, nunca de dois
    assert all(abs(DEGRAU[r1[c]] - DEGRAU[r2[c]]) == 1 for c in r1 if c not in consenso)


def test_pontuacao_da_rodada_2():
    assert rodada_2_passa(REF["referencia_1"]["vereditos"])
    assert rodada_2_passa(REF["referencia_2"]["vereditos"])
    tudo_parcial = {c: "parcial" for c in REF["referencia_1"]["vereditos"]}
    p = pontuar(tudo_parcial)
    assert len(p["certos"]) == 6 and not rodada_2_passa(tudo_parcial)
    # o app de hoje errou para baixo: Sim no lugar de Não é erro de dois degraus
    dois = dict(REF["referencia_1"]["vereditos"], D2="sim")
    assert pontuar(dois)["errados"] == {"D2": 2} and not rodada_2_passa(dois)
