"""Copy do card Índice Geral (frente copy Painel).

A explicação deixou de falar em "pilar travado" (vocabulário de gargalo, que a 17
não tem) e passa a dizer que o PIOR PILAR define o teto. A frase final é DERIVADA
do dado (nome do pilar + ratio) e CONDICIONAL: só aparece quando o pior pilar é o
binding (pior*2 == indice_geral); quando a média ponderada é o teto, some — senão
o executivo faria pior×2 e acharia divergência com o índice exibido.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment

# Espelha o bloco de templates/partials/explorar_painel.html (self-contained em n1).
# O teste estático abaixo garante que o template real carrega a mesma expressão.
_SNIPPET = (
    "{% set _com_vol = n1.pilares | selectattr('total') | list %}"
    "{% set _pior = (_com_vol | min(attribute='ratio')) if _com_vol else none %}"
    "Não é média — é o pior pilar que define o teto."
    "{% if _pior and (_pior.ratio * 2) | round(2) == n1.indice_geral %}"
    " Aqui, {{ _pior.nome }} em {{ ('%.2f'|format(_pior.ratio))|replace('.', ',') }} é o teto."
    "{% endif %}"
)


def _render(n1):
    return Environment().from_string(_SNIPPET).render(n1=n1)


def test_frase_final_deriva_pior_pilar_quando_binda():
    # Empresa 17: pior pilar Precisão 1,03 → índice 2,06; pior binda (1,03×2 == 2,06).
    n1 = {
        "indice_geral": 2.06,
        "pilares": [
            {"pilar": "P", "nome": "Precisão", "ratio": 1.03, "total": 262},
            {"pilar": "D", "nome": "Direção", "ratio": 1.73, "total": 100},
            {"pilar": "Pa", "nome": "Parceria", "ratio": 1.66, "total": 200},
        ],
    }
    html = _render(n1)
    assert "é o pior pilar que define o teto" in html
    # nome + ratio DERIVADOS do dado, ratio com vírgula (locale) — teste de dono da 17
    assert "Aqui, Precisão em 1,03 é o teto." in html


def test_frase_final_some_quando_media_binda():
    # média ponderada < pior pilar → índice = média×2; pior (2,0×2=4,0) != índice 2,0
    # → a frase final some (as duas primeiras ficam).
    n1 = {
        "indice_geral": 2.0,
        "pilares": [
            {"pilar": "P", "nome": "Precisão", "ratio": 2.0, "total": 100},
            {"pilar": "D", "nome": "Direção", "ratio": 2.0, "total": 100},
        ],
    }
    html = _render(n1)
    assert "é o pior pilar que define o teto" in html  # as 2 primeiras ficam
    assert "Aqui," not in html  # a frase final auto-verificável NÃO aparece


def test_sem_pilar_com_volume_nao_quebra_e_omite_frase():
    html = _render({"indice_geral": 0.0, "pilares": []})
    assert "é o pior pilar que define o teto" in html and "Aqui," not in html


def test_copy_antiga_fora_e_nova_no_template_real():
    tpl = Path("templates/partials/explorar_painel.html").read_text(encoding="utf-8")
    # Índice Geral (item 1)
    assert "Pilar travado puxa o índice para baixo" not in tpl  # vocabulário de gargalo fora
    assert "é o pior pilar que define o teto" in tpl  # copy nova presente
    assert "(_pior.ratio * 2) | round(2) == n1.indice_geral" in tpl  # a condicional derivada
    # Proximity Geral (item 2)
    assert "O pilar gargalo puxa para baixo" not in tpl  # vocabulário de gargalo fora
    assert "É o pilar mais distante que fixa o conjunto — não a média." in tpl
    assert "proximity.binding_pilar_nome" in tpl  # nomeia o binding (condicional)


# ── Item 2 · Proximity Geral: binding = MENOR PROXIMITY (não menor ratio) ──────

_SNIPPET2 = (
    "Distância da excelência consolidada (ratio 9.0). É o pilar mais distante que "
    "fixa o conjunto — não a média."
    "{% if proximity.binding_pilar_nome %} Aqui, {{ proximity.binding_pilar_nome }}.{% endif %}"
)


def _render2(proximity):
    return Environment().from_string(_SNIPPET2).render(proximity=proximity)


def test_binding_proximity_pega_menor_proximity():
    from src.ui import _pilar_binding_proximity

    # D tem a MENOR proximity (20) → binda D. O helper vê proximity, não ratio.
    prox = {"P": {"valor": 35.0}, "D": {"valor": 20.0}, "Pa": {"valor": 48.0}}
    assert _pilar_binding_proximity(prox) == "D"


def test_binding_proximity_ignora_pilar_null():
    from src.ui import _pilar_binding_proximity

    # um pilar (talvez o de menor ratio) com proximity NULL não entra no min.
    prox = {"P": {"valor": None}, "D": {"valor": 30.0}, "Pa": {"valor": 45.0}}
    assert _pilar_binding_proximity(prox) == "D"


def test_binding_proximity_todos_null_sem_binding():
    from src.ui import _pilar_binding_proximity

    assert _pilar_binding_proximity({"P": {"valor": None}, "D": {"valor": None}}) is None


def test_proximity_nomeia_binding_quando_ha():
    html = _render2({"binding_pilar_nome": "Precisão"})
    assert "É o pilar mais distante que fixa o conjunto — não a média." in html
    assert "Aqui, Precisão." in html  # NOME do binding derivado


def test_proximity_omite_nome_quando_null():
    # todos os pilares sem proximity (nenhum subpilar acima do piso) → não nomeia
    html = _render2({"binding_pilar_nome": None})
    assert "não a média." in html and "Aqui," not in html
