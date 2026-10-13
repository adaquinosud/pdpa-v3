"""Extração do Avaliador com documentos SINTÉTICOS gerados no próprio teste (nenhum
documento real entra na suíte)."""

from __future__ import annotations

import io
import zipfile

import pytest

from src.avaliador import extracao
from src.avaliador.extracao import (
    Documento,
    DocumentoRecusado,
    Pagina,
    conferir_trecho,
    detectar_formato,
    extrair,
)

TEXTO_LONGO = "Entregamos o painel mensal até o quinto dia útil de cada mês."


def _pptx() -> bytes:
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    branco = prs.slide_layouts[6]
    # 1: caixa de texto simples + nota do apresentador
    s1 = prs.slides.add_slide(branco)
    s1.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1)).text_frame.text = TEXTO_LONGO
    s1.notes_slide.notes_text_frame.text = "Lembrar de citar o prazo de resposta de quatro horas."
    # 2: texto só dentro de um GRUPO aninhado
    s2 = prs.slides.add_slide(branco)
    grupo = s2.shapes.add_group_shape()
    sub = grupo.shapes.add_group_shape()
    sub.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1)).text_frame.text = (
        "Texto escondido dentro de um grupo aninhado de formas."
    )
    # 3: texto só numa TABELA
    s3 = prs.slides.add_slide(branco)
    tab = s3.shapes.add_table(2, 2, Inches(1), Inches(1), Inches(6), Inches(2)).table
    tab.cell(0, 0).text = "Nível de serviço"
    tab.cell(0, 1).text = "Resposta em até quatro horas úteis"
    # 4: vazio (só imagem, na vida real)
    prs.slides.add_slide(branco)
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _pdf(paginas) -> bytes:
    """PDF mínimo escrito à mão (Helvetica/WinAnsi), uma linha de texto por página.
    Sem WeasyPrint: as libs nativas dele não existem fora da imagem Docker."""
    n = len(paginas)
    objs = {1: b"<< /Type /Catalog /Pages 2 0 R >>"}
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n))
    objs[2] = f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode()
    fonte = 3 + 2 * n
    for i, t in enumerate(paginas):
        pag, cont = 3 + 2 * i, 4 + 2 * i
        objs[pag] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {cont} 0 R "
            f"/Resources << /Font << /F1 {fonte} 0 R >> >> >>"
        ).encode()
        esc = t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        fluxo = b"BT /F1 10 Tf 50 700 Td (" + esc.encode("cp1252") + b") Tj ET" if t else b""
        objs[cont] = b"<< /Length %d >>\nstream\n" % len(fluxo) + fluxo + b"\nendstream"
    objs[fonte] = (
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )
    out = bytearray(b"%PDF-1.4\n")
    offs = {}
    for k in sorted(objs):
        offs[k] = len(out)
        out += b"%d 0 obj\n" % k + objs[k] + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for k in sorted(objs):
        out += b"%010d 00000 n \n" % offs[k]
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


def test_pptx_le_grupo_tabela_e_nota_e_conta_pagina_vazia():
    doc = extrair(_pptx())
    assert doc.formato == "pptx" and doc.n_paginas == 4
    assert TEXTO_LONGO in doc.paginas[0].texto
    assert "quatro horas" in doc.paginas[0].notas  # nota fica separada do corpo
    assert "grupo aninhado" in doc.paginas[1].texto
    assert "Resposta em até quatro horas úteis" in doc.paginas[2].texto
    assert doc.paginas_sem_texto == [4]


def test_nota_vai_marcada_no_prompt():
    prompt = extrair(_pptx()).para_prompt()
    assert "=== PÁGINA 1 ===" in prompt
    assert "nota do apresentador" in prompt
    assert "[página sem texto legível]" in prompt


def test_pdf_por_pagina():
    doc = extrair(_pdf([TEXTO_LONGO, "Segunda página com conteúdo suficiente aqui.", ""]))
    assert doc.formato == "pdf"
    assert doc.n_paginas == 3
    assert "quinto dia útil" in doc.paginas[0].texto
    assert doc.paginas_sem_texto == [3]


def test_json_ida_e_volta():
    doc = extrair(_pptx())
    volta = Documento.de_json(doc.para_json())
    assert [(p.numero, p.texto, p.notas) for p in volta.paginas] == [
        (p.numero, p.texto, p.notas) for p in doc.paginas
    ]


def test_formato_pelo_conteudo_e_nao_pela_extensao():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<w/>")
    with pytest.raises(DocumentoRecusado, match="Word"):
        detectar_formato(buf.getvalue())
    with pytest.raises(DocumentoRecusado, match="não reconhecido"):
        detectar_formato(b"\xd0\xcf\x11\xe0 ppt antigo")


def test_pdf_com_senha_recusado():
    from pypdf import PdfReader, PdfWriter

    w = PdfWriter()
    for p in PdfReader(io.BytesIO(_pdf([TEXTO_LONGO]))).pages:
        w.add_page(p)
    w.encrypt("segredo")
    buf = io.BytesIO()
    w.write(buf)
    with pytest.raises(DocumentoRecusado, match="senha"):
        extrair(buf.getvalue())


def test_so_imagem_recusado():
    with pytest.raises(DocumentoRecusado, match="só imagem"):
        extrair(_pdf(["", ""]))


def test_limites(monkeypatch):
    dados = _pptx()
    monkeypatch.setattr(extracao, "LIMITE_PAGINAS", 3)
    with pytest.raises(DocumentoRecusado, match="limite é 3"):
        extrair(dados)
    monkeypatch.setattr(extracao, "LIMITE_PAGINAS", 120)
    monkeypatch.setattr(extracao, "LIMITE_CARACTERES", 50)
    with pytest.raises(DocumentoRecusado, match="texto demais"):
        extrair(dados)
    monkeypatch.setattr(extracao, "LIMITE_BYTES", 10)
    with pytest.raises(DocumentoRecusado, match="maior que"):
        extrair(dados)


def _doc():
    return Documento(
        "pdf",
        [
            Pagina(1, "Atendimento:   de segunda a sexta,\n das 8h às 18h."),
            Pagina(2, "O gerente responde em “até 4 horas” — sempre."),
        ],
    )


def test_citacao_exata_e_com_espaco_diferente():
    assert conferir_trecho(_doc(), 1, "de segunda a sexta, das 8h às 18h") == (True, 1)


def test_citacao_na_pagina_errada_e_achada_e_corrigida():
    assert conferir_trecho(_doc(), 1, 'responde em "até 4 horas" - sempre') == (True, 2)


def test_citacao_inexistente_ou_parafraseada_nao_confere():
    assert conferir_trecho(_doc(), 1, "atendimento em horário comercial") == (False, None)
    assert conferir_trecho(_doc(), 1, "DE SEGUNDA A SEXTA, DAS 8H") == (False, None)


def test_citacao_curta_demais_nao_prova_nada():
    assert conferir_trecho(_doc(), 1, "sexta") == (False, None)


def test_texto_colado_vira_documento_de_uma_pagina():
    from src.avaliador.extracao import documento_de_texto

    doc = documento_de_texto("Cliente: com quem eu falo?\nVendedor: comigo, das 8h às 18h.")
    assert doc.formato == "texto" and doc.n_paginas == 1
    assert "=== TEXTO COLADO ===" in doc.para_prompt()
    assert conferir_trecho(doc, 1, "comigo, das 8h às 18h") == (True, 1)
    with pytest.raises(DocumentoRecusado, match="vazio"):
        documento_de_texto("   ")
