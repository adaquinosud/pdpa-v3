"""Tela Propagação (partial): blocos-quadrante colapsáveis (<details> nativo).
Crítico + Acelerando abertos por padrão; Crônico/Latente/Em-recuperação fechados."""

from __future__ import annotations

import re
from types import SimpleNamespace

from flask import render_template


def _t(nome, tid):
    return {
        "tema_id": tid,
        "nome": nome,
        "subpilar": "Pa2",
        "volume": 10,
        "raio": 3,
        "camadas": ["diag", "RA"],
        "glifo": "↑↑",
        "mensagem": "x",
    }


def _det_tag(html, nome):
    """Atributos do <details> cujo summary contém `nome` (p/ checar 'open')."""
    m = re.search(
        r"<details ([^>]*)>\s*<summary[^>]*>[^<]*<span[^>]*></span>[^(]*" + re.escape(nome),
        html,
    )
    return m.group(1) if m else None


def test_quadrantes_colapsaveis_default_open(app):
    quad = {
        "Crítico": [_t("a", 1)],
        "Acelerando": [_t("b", 2)],
        "Crônico": [_t("c", 3), _t("c2", 4)],
        "Latente": [_t("d", 5)],
        "Em recuperação": [_t("e", 6)],
    }
    with app.test_request_context():
        html = render_template(
            "partials/explorar_propagacao.html",
            empresa=SimpleNamespace(id=1),
            quadrantes=quad,
            total=6,
        )
    # Crítico + Acelerando abertos
    assert "open" in _det_tag(html, "Crítico")
    assert "open" in _det_tag(html, "Acelerando")
    # Crônico / Latente / Em-recuperação fechados
    assert "open" not in _det_tag(html, "Crônico")
    assert "open" not in _det_tag(html, "Latente")
    assert "open" not in _det_tag(html, "Em recuperação")
    # contagem visível no título fechado
    assert "Crônico · reconstrução" in html and "(2)" in html


def test_bloco_vazio_omitido(app):
    quad = {
        "Crítico": [_t("a", 1)],
        "Acelerando": [],
        "Crônico": [],
        "Latente": [],
        "Em recuperação": [],
    }
    with app.test_request_context():
        html = render_template(
            "partials/explorar_propagacao.html",
            empresa=SimpleNamespace(id=1),
            quadrantes=quad,
            total=1,
        )
    assert _det_tag(html, "Crítico") is not None
    assert _det_tag(html, "Latente") is None  # vazio → sem <details>
