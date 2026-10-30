"""Opção 1 (decisão de 29/out): gargalo eleito por SUBPILAR imprime o ratio DO subpilar,
com o nome dele — nunca o do pilar, que pode ser bom e não explica a eleição.

Sem isto a fatia do gargalo por subpilar trocaria um defeito por outro: "o gargalo está em
Parceria, ratio 5,37" quando o que está quebrado é o Pa2 em 0,02. Cobre as superfícies
que nomeiam o gargalo com número: o construtor do Lastro dos impressos, os payloads LLM
(via ``ratio_do_gargalo``), o texto sem LLM do paradoxo, a tabela do impresso e o card da
tela. E o caminho de sempre (eleito pela soma) segue igual.
"""

from __future__ import annotations

from flask import render_template

from src.api.painel import (
    SUBPILARES_ORDEM,
    calcular_ratio,
    faixa_ratio,
    gargalo_detalhe,
    gargalo_travado_por,
)
from src.relatorios.lastro import montar_lastro, ratio_do_gargalo
from src.relatorios.llm_secoes import compor_paradoxo_puro


def _agg(raw):
    base = {s: (100, 0, 10) for s in SUBPILARES_ORDEM}
    base.update(raw)
    out = {}
    for k, (p, c, d) in base.items():
        r = calcular_ratio(p, d)
        out[k] = {
            "prom": p,
            "conv": c,
            "det": d,
            "total": p + c + d,
            "ratio": r,
            "faixa": faixa_ratio(r),
        }
    return out


# Parceria boa pela soma (Pa1 cobre), Pa2 zerado com volume alto → gargalo Pa por subpilar.
POR_SUB = {"Pa1": (1493, 0, 95), "Pa2": (6, 2, 286)}
# Disponibilidade crítica pela soma → gargalo D pela soma.
POR_SOMA = {"D1": (5, 0, 40), "D2": (5, 0, 40), "D3": (5, 0, 40)}


def _lastro(raw, leituras=None):
    agg = _agg(raw)
    det = gargalo_detalhe(agg)
    g = det["pilar"] if det else None
    return agg, g, montar_lastro(agg, g, leituras or {}, {}, detalhe=det)


def test_lastro_por_subpilar_marca_quem_trava_e_ancora_no_eleitor():
    agg, g, lt = _lastro(POR_SUB, leituras={"Pa2": ("leitura do Pa2", None)})
    assert g == "Pa"
    pa = next(p for p in lt.pilares if p.codigo == "Pa")
    assert pa.ratio > 2  # a soma do pilar é BOA — por isso o ratio dele não explica
    assert [x["subpilar"] for x in pa.gargalo_por] == ["Pa2"]
    assert lt.pilar_sub_destaque["Pa"]["pior"] == "Pa2"
    assert lt.pilar_leitura_gargalo["Pa"] == "leitura do Pa2"
    assert all(p.gargalo_por == [] for p in lt.pilares if p.codigo != "Pa")


def test_ratio_do_gargalo_e_do_subpilar_com_o_nome():
    agg, g, lt = _lastro(POR_SUB)
    r = ratio_do_gargalo(lt, g)
    assert r["de"] == "subpilar" and r["subpilar"] == "Pa2 Mutualidade"
    assert r["ratio"] == agg["Pa2"]["ratio"] < 0.05


def test_pela_soma_nada_muda():
    agg, g, lt = _lastro(POR_SOMA)
    assert g == "D"
    assert all(p.gargalo_por == [] for p in lt.pilares)
    r = ratio_do_gargalo(lt, g)
    assert r["de"] == "pilar" and r["subpilar"] is None
    assert r["ratio"] == next(p.ratio for p in lt.pilares if p.codigo == "D")


def test_sem_gargalo_ratio_none():
    _, g, lt = _lastro({})
    assert g is None
    assert ratio_do_gargalo(lt, g) == {"ratio": None, "de": None, "subpilar": None}


def test_paradoxo_puro_diz_travado_por_com_ratio_do_subpilar_e_virgula():
    txt = compor_paradoxo_puro(
        "Aconselhamento",
        "ativo forte.",
        "Parceria",
        "cobrança indevida.",
        gargalo_subpilar="Pa2 Mutualidade",
        gargalo_ratio=0.02,
        gargalo_ratio_de="subpilar",
    )
    assert "O gargalo está em Parceria, travada por Pa2 Mutualidade (ratio 0,02):" in txt
    assert "0.02" not in txt


def test_paradoxo_puro_pela_soma_usa_virgula():
    txt = compor_paradoxo_puro(
        "Aconselhamento",
        "x.",
        "Disponibilidade",
        "y.",
        gargalo_ratio=0.33,
        gargalo_ratio_de="pilar",
    )
    assert "ratio 0,33" in txt and "0.33" not in txt and "travada" not in txt


def _render_linha(app, p):
    with app.test_request_context():
        tpl = app.jinja_env.from_string(
            '{% import "relatorios/_macros.html" as M %}'
            "{{ M.lastro_interp_pilar(p) }}|{{ M.linha_abaixo_do_pilar(p) }}"
        )
        return tpl.render(p=p)


def test_impresso_linha_travado_por_substitui_ferida_e_interrompe(app):
    _, _, lt = _lastro(POR_SUB)
    pa = next(p for p in lt.pilares if p.codigo == "Pa")
    pa.ferida_interna = [{"nome": "Mutualidade", "ratio": 0.02, "det": 286}]
    html = _render_linha(app, pa)
    assert "Interrompe" in html  # o pilar-gargalo é o elo quebrado, não "Âncora"
    assert "Travado por Pa2 Mutualidade em 0,02 (286 críticas em 294 manifestações)" in html
    assert "Aparenta saudável" not in html  # mesmo subpilar não sai duas vezes


def test_impresso_pilar_sem_gargalo_mantem_ferida_interna(app):
    _, _, lt = _lastro(POR_SOMA)
    a = next(p for p in lt.pilares if p.codigo == "A")
    a.ferida_interna = [{"nome": "Orientação", "ratio": 0.1, "det": 50}]
    html = _render_linha(app, a)
    assert "Aparenta saudável, mas carrega Orientação em 0,10" in html
    assert "Travado por" not in html


def test_tela_card_do_gargalo_nomeia_quem_trava(app):
    agg = _agg(POR_SUB)
    travado = gargalo_travado_por(agg, gargalo_detalhe(agg))
    pilares = [
        {
            "pilar": "Pa",
            "nome": "Parceria",
            "ratio": 5.37,
            "faixa": "excelente",
            "total": 1882,
            "gargalo": True,
            "gargalo_por": travado,
            "ferida_interna": [{"nome": "Mutualidade", "ratio": 0.02, "det": 286}],
            "subpilares": [],
        }
    ]
    with app.test_request_context():
        html = render_template("partials/_mapa_lastro.html", pilares=pilares)
    assert "travado por Pa2 Mutualidade em 0,02 (286 detratores)" in html
    assert "aparenta saudável" not in html


def test_pesquisa_mapa_leva_gargalo_por():
    from src.pesquisa.retorno import _mapa_lastro_pesquisa

    valencia = {
        s: {"promotor": p, "conversivel": c, "detrator": d, "total": p + c + d}
        for s, (p, c, d) in {**{s: (100, 0, 10) for s in SUBPILARES_ORDEM}, **POR_SUB}.items()
    }
    mapa = _mapa_lastro_pesquisa(valencia)
    pa = next(m for m in mapa if m["pilar"] == "Pa")
    assert pa["gargalo"] and [x["subpilar"] for x in pa["gargalo_por"]] == ["Pa2"]
