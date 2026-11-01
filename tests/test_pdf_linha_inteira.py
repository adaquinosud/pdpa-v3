"""Linha de tabela do impresso não se parte entre páginas (31/out).

Nos Temas da 29, a linha "atendimento personalizado" quebrou: o 17 (célula de uma linha só)
ficou sozinho no pé da página, e nome + exemplo (duas linhas) desceram para a seguinte com a
coluna Ocorrências vazia. Este teste gera PDF de verdade com o CSS de ``base_pdf.html`` e varre a
altura de um espaçador até a quebra cair dentro da linha — em toda altura, número e nome têm de
sair na mesma página. Precisa do WeasyPrint com as libs nativas e do ``pdftotext``; sem eles, pula.
"""

from __future__ import annotations

import shutil
import subprocess
from types import SimpleNamespace

import pytest

from src.relatorios.pdf import PdfIndisponivel, render_pdf

_LINHA = (
    "<tr><td><strong>nome comprido que quebra em duas linhas NOMEFIM</strong></td>"
    '<td style="text-align:right">NUM{n}</td>'
    "<td>exemplo comprido o bastante para ocupar duas linhas na coluna de exemplo, como os "
    "verbatins da seção de Temas Recorrentes EXFIM</td></tr>"
)


def _texto(pdf, p):
    return subprocess.run(
        ["pdftotext", "-f", str(p), "-l", str(p), str(pdf), "-"], capture_output=True, text=True
    ).stdout


def test_linha_da_tabela_nao_se_parte(app, tmp_path):
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext ausente")
    try:
        render_pdf("<p>x</p>")
    except PdfIndisponivel:
        pytest.skip("WeasyPrint sem libs nativas")

    linhas = "".join(_LINHA.format(n=n) for n in (9101, 9102, 9103))
    corpo = (
        '{% extends "relatorios/base_pdf.html" %}{% block conteudo %}'
        '<div style="height:{{ mm }}mm"></div>'
        "<table><thead><tr><th>Tema</th><th>Ocorrências</th><th>Exemplo</th></tr></thead>"
        "<tbody>" + linhas + "</tbody></table>{% endblock %}"
    )
    partidas = []
    with app.test_request_context():
        tpl = app.jinja_env.from_string(corpo)
        for mm in range(200, 290, 3):
            pdf = tmp_path / "t.pdf"
            pdf.write_bytes(render_pdf(tpl.render(mm=mm, empresa=SimpleNamespace(nome="E"))))
            info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
            n_pag = int(next(x for x in info.splitlines() if x.startswith("Pages")).split()[-1])
            for p in range(1, n_pag + 1):
                t = _texto(pdf, p)
                contas = (t.count("NUM9"), t.count("NOMEFIM"), t.count("EXFIM"))
                if len(set(contas)) > 1:  # número, nome e exemplo em páginas diferentes
                    partidas.append((mm, p, contas))
    assert not partidas, f"linha partida (mm, página, (números, nomes, exemplos)): {partidas}"
