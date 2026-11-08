"""scripts/extrair_manual_md.py: o .md de leitura do Manual sai do .docx no formato combinado."""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path
from zipfile import ZipFile

_spec = importlib.util.spec_from_file_location(
    "extrair_manual_md", Path(__file__).parents[1] / "scripts" / "extrair_manual_md.py"
)
ext = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ext)


def _p(texto, estilo=None):
    ppr = f'<w:pPr><w:pStyle w:val="{estilo}"/></w:pPr>' if estilo else ""
    return f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{texto}</w:t></w:r></w:p>'


def _docx(tmp_path, nome, corpo):
    caminho = tmp_path / nome
    with ZipFile(caminho, "w") as z:
        z.writestr("word/document.xml", f"<w:document><w:body>{corpo}</w:body></w:document>")
    return caminho


def test_formato_titulos_tabela_e_cabecalho(tmp_path):
    corpo = (
        _p("Manual de Operação · v8", "BodyText")
        + _p("Sobre este manual", "Heading1")
        + "<w:p/>"
        + _p("Estrutura", "Heading2")
        + _p("Comparação", "Heading3")
        + "<w:tbl><w:tr><w:tc>"
        + _p("A")
        + "</w:tc><w:tc>"
        + _p("B")
        + "</w:tc></w:tr><w:tr><w:tc>"
        + _p("1 &amp; 2")
        + "</w:tc><w:tc>"
        + _p("3")
        + "</w:tc></w:tr></w:tbl>"
        + _p("Posições — linha de lista")
    )
    md = ext.extrair(_docx(tmp_path, "PDPA_Manual_Operacao_v16.docx", corpo), date(2026, 11, 7))
    assert md == (
        "<!-- Texto extraído de data/PDPA_Manual_Operacao_v16.docx em 07/11/2026. "
        "A fonte é o .docx; este arquivo é só para leitura. -->\n\n"
        "Manual de Operação · v8\n\n# Sobre este manual\n\n## Estrutura\n\n### Comparação\n\n"
        "| A | B |\n|---|---|\n| 1 & 2 | 3 |\n\nPosições — linha de lista\n"
    )


def test_mais_recente_e_o_de_maior_numero_e_ignora_trava_do_word(tmp_path):
    for nome in ("PDPA_Manual_Operacao_v3.docx", "PDPA_Manual_Operacao_v16.docx"):
        _docx(tmp_path, nome, "")
    _docx(tmp_path, "PDPA_Manual_Operacao_v9.docx", "")
    (tmp_path / "~$PA_Manual_Operacao_v99.docx").write_text("trava")
    assert ext.mais_recente(tmp_path).name == "PDPA_Manual_Operacao_v16.docx"
