"""Gargalo por subpilar: subpilar CRÍTICO com volume ≥ piso (30) também quebra o pilar.

Regra sequencial (decisão de 29/out): quebra crítica = soma < 0,5 OU subpilar crítico
≥ piso; ganha o 1º na ordem P → D → Pa → A; fraco pela soma é o 2º critério. Antes, só a
soma contava — empresa com pilar bom pela soma e subpilar zerado dentro ficava SEM gargalo
(BH Airport: Parceria 5,37, Pa2 0,02 com 300 de volume).
"""

from __future__ import annotations

import random

import pytest

from src.api.painel import (
    SUBPILARES_ORDEM,
    calcular_ratio,
    faixa_ratio,
    gargalo_detalhe,
    gargalo_sequencial,
    pilares_com_ferida_interna,
    subpilares_criticos,
)

SAUDAVEL = (100, 0, 10)  # prom, conv, det → ratio 10 (cap 9,99): excelente


def _agg(raw, completar=True):
    """sub -> (prom, conv, det). ``completar`` preenche os 12 subpilares com SAUDAVEL,
    para o caso isolar o subpilar em teste."""
    base = {s: SAUDAVEL for s in SUBPILARES_ORDEM} if completar else {}
    base.update(raw)
    out = {}
    for k, (p, c, d) in base.items():
        r = calcular_ratio(p, d)
        out[k] = {"prom": p, "conv": c, "det": d, "total": p + c + d, "ratio": r}
        out[k]["faixa"] = faixa_ratio(r)
    return out


def test_bh_airport_pilar_bom_com_subpilar_zerado_vira_gargalo():
    """Falha sem a correção: pela soma, Parceria é excelente e o gargalo era None."""
    agg = _agg({"Pa1": (1493, 0, 95), "Pa2": (12, 2, 286)})
    assert gargalo_sequencial(agg) == "Pa"
    d = gargalo_detalhe(agg)
    assert d["motivo"] == "subpilar_critico" and d["subpilares"] == ["Pa2"]


def test_empresa_29_numeros_do_probe():
    """Prod (probe 29/out): D2 3/0/28 (31) passa no piso; Pa2 4/1/18 (23) e A2 1/0/3 (4)
    não. Os demais subpilares aqui são SAUDÁVEIS por construção (não são os de prod) —
    o teste prova a eleição pelos três críticos, não o agg real da 29."""
    agg = _agg({"D2": (3, 0, 28), "Pa2": (4, 1, 18), "A2": (1, 0, 3)})
    d = gargalo_detalhe(agg)
    assert d == {"pilar": "D", "motivo": "subpilar_critico", "subpilares": ["D2"]}


def test_piso_e_inclusivo_e_abaixo_nao_elege():
    assert gargalo_sequencial(_agg({"Pa2": (0, 0, 30)})) == "Pa"  # total 30 = piso
    assert gargalo_sequencial(_agg({"Pa2": (0, 0, 29)})) is None  # 29 < piso


def test_ratio_meio_exato_e_fraco_nao_critico():
    """Régua do código: crítico é ratio < 0,5. 0,50 exato (50 prom / 100 det) é FRACO —
    não elege por subpilar (a legenda impressa '≤ 0,5' está errada, não a régua)."""
    agg = _agg({"Pa2": (50, 0, 100)})
    assert agg["Pa2"]["faixa"] == "fraco"
    assert subpilares_criticos(agg) == []
    assert gargalo_sequencial(agg) is None


def test_sequencial_pilar_anterior_quebrado_pela_soma_vence_subpilar_posterior():
    """P crítico pela soma, mas com subpilares ralos (nenhum ≥ 30); Pa2 crítico ≥ 30.
    A leitura LITERAL daria Pa; a sequencial (decidida) mantém P — o pilar inicial
    travado puxa os seguintes."""
    agg = _agg({"P1": (1, 0, 10), "P2": (1, 0, 10), "P3": (1, 0, 10), "Pa2": (0, 0, 300)})
    d = gargalo_detalhe(agg)
    assert d["pilar"] == "P" and d["motivo"] == "soma_critica" and d["subpilares"] == []


def test_quebra_critica_por_subpilar_vence_fraco_anterior():
    """P fraco pela soma (antes) + Pa2 crítico ≥ piso (depois) → Pa: quebra crítica
    tem precedência sobre posição, como o crítico pela soma já tinha."""
    agg = _agg({"P1": (70, 0, 100), "P2": (70, 0, 100), "P3": (70, 0, 100), "Pa2": (0, 0, 300)})
    assert gargalo_sequencial(agg) == "Pa"


def test_sem_quebra_critica_cai_no_fraco_pela_soma():
    agg = _agg({"D1": (70, 0, 100), "D2": (70, 0, 100), "D3": (70, 0, 100)})
    assert gargalo_detalhe(agg) == {"pilar": "D", "motivo": "soma_fraca", "subpilares": []}


def test_tudo_saudavel_sem_gargalo():
    assert gargalo_detalhe(_agg({})) is None


def test_subpilar_sem_sinal_pd_nao_e_critico():
    """Só conversíveis (prom+det=0): calcular_ratio daria 0,0 — não pode virar crítico."""
    assert subpilares_criticos(_agg({"Pa2": (0, 300, 0)})) == []


def test_piso_explicito_respeitado():
    agg = _agg({"Pa2": (0, 0, 5)})
    assert gargalo_sequencial(agg) is None
    assert gargalo_sequencial(agg, piso=5) == "Pa"


@pytest.mark.parametrize("seed", range(5))
def test_gargalo_none_implica_sem_ferida_interna(seed):
    """Invariante entre as duas réguas que agora dividem o predicado: se nada quebra o
    Lastro, não pode existir ferida interna (crítico ≥ piso escondido num pilar OK). É o
    que torna verdadeira a frase de 'sem gargalo'. Testado contra agg aleatório; e o teste
    é testado: a BH Airport (caso conhecido) tem ferida interna E gargalo."""
    rnd = random.Random(seed)
    for _ in range(400):
        raw = {
            s: (rnd.randint(0, 60), rnd.randint(0, 5), rnd.randint(0, 60))
            for s in SUBPILARES_ORDEM
            if rnd.random() < 0.8
        }
        agg = _agg(raw, completar=False)
        if gargalo_sequencial(agg) is None:
            assert pilares_com_ferida_interna(agg) == {}
    bh = _agg({"Pa1": (1493, 0, 95), "Pa2": (12, 2, 286)})
    assert pilares_com_ferida_interna(bh) and gargalo_sequencial(bh) == "Pa"
