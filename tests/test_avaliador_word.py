"""Leitura de Word (.docx) do Avaliador com documentos SINTÉTICOS montados no teste (o XML
mínimo que o Word grava; nenhum documento real entra na suíte)."""

from __future__ import annotations

import io
import zipfile

import pytest

from src.avaliador import extracao, word
from src.avaliador.extracao import (
    DocumentoRecusado,
    conferir_trecho,
    detectar_formato,
    extrair,
    referencia,
)
from src.avaliador.motor import sem_numero_de_secao

NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
    'xmlns:v="urn:schemas-microsoft-com:vml"'
)
ESTILOS = f"""<w:styles {NS}>
<w:style w:type="paragraph" w:styleId="Ttulo1"><w:name w:val="heading 1"/></w:style>
<w:style w:type="paragraph" w:styleId="TituloProposta"><w:name w:val="Título da proposta"/>
  <w:basedOn w:val="Ttulo1"/></w:style>
<w:style w:type="paragraph" w:styleId="Sumrio1"><w:name w:val="toc 1"/></w:style>
<w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
</w:styles>"""


def _p(texto, estilo=None, extra=""):
    ppr = f'<w:pPr><w:pStyle w:val="{estilo}"/></w:pPr>' if estilo else ""
    return f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{texto}</w:t></w:r>{extra}</w:p>'


def _docx(corpo: str, estilos: str = ESTILOS, extras=None, ns: str = NS) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", f"<w:document {ns}><w:body>{corpo}</w:body></w:document>")
        if estilos:
            z.writestr("word/styles.xml", estilos)
        for nome, conteudo in (extras or {}).items():
            z.writestr(nome, conteudo)
    return buf.getvalue()


ABERTURA = "Proposta de atendimento para a Empresa Exemplo, válida por trinta dias corridos."
HORARIO = "Atendimento de segunda a sexta das 8h às 18h pelo gerente de conta."
REFERENCIA = "Somos referência no setor há vinte anos, com clientes em todo o país."

CORPO = (
    _p(ABERTURA) + _p("Sumário automático 3", "Sumrio1") + _p("Como atendemos", "Ttulo1")
    # palavra partida em dois trechos de formatação ("Atendi" + "mento") volta inteira
    + '<w:p><w:r><w:t>Atendi</w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">'
    "mento de segunda a sexta das 8h às 18h pelo gerente de conta.</w:t></w:r>"
    '<w:r><w:commentReference w:id="0"/></w:r></w:p>'
    # controle de alterações: riscado e movido-daqui saem; inserido e movido-para entram
    + '<w:p><w:r><w:t xml:space="preserve">Resposta em </w:t></w:r>'
    '<w:del w:id="1" w:author="A"><w:r><w:delText>quatro horas</w:delText></w:r></w:del>'
    '<w:ins w:id="2" w:author="A"><w:r><w:t>um dia útil</w:t></w:r></w:ins>'
    '<w:moveFrom w:id="3" w:author="A"><w:r><w:t>TEXTO-MOVIDO-DAQUI</w:t></w:r></w:moveFrom>'
    '<w:r><w:t xml:space="preserve"> por e-mail.</w:t></w:r></w:p>'
    + "<w:p><w:r><w:rPr><w:vanish/></w:rPr><w:t>OCULTO-FORA</w:t></w:r>"
    "<w:r><w:t>Plantão aos sábados.</w:t></w:r></w:p>"
    + _p("Quem somos", "TituloProposta")
    + _p(REFERENCIA)
    # caixa de texto: o Word grava duas vezes (moderna e reserva); entra uma
    + "<w:p><w:r><mc:AlternateContent><mc:Choice><w:drawing><wps:txbx><w:txbxContent>"
    + _p("Selo de qualidade na caixa de texto.")
    + "</w:txbxContent></wps:txbx></w:drawing></mc:Choice><mc:Fallback><w:pict><v:textbox>"
    "<w:txbxContent>"
    + _p("Selo de qualidade na caixa de texto.")
    + "</w:txbxContent></v:textbox></w:pict></mc:Fallback></mc:AlternateContent></w:r></w:p>"
    + '<w:p><w:pPr><w:outlineLvl w:val="1"/></w:pPr><w:r><w:t>Preços</w:t></w:r></w:p>'
    + "<w:tbl><w:tblPr/><w:tblGrid/>"
    "<w:tr><w:tc>" + _p("Plano") + "</w:tc><w:tc>" + _p("Valor mensal") + "</w:tc></w:tr>"
    "<w:tr><w:tc>" + _p("Essencial") + "</w:tc><w:tc>" + _p("R$ 8.000") + "</w:tc></w:tr>"
    "</w:tbl>"
)
EXTRAS = {
    "word/header1.xml": f"<w:hdr {NS}>{_p('CABECALHO-FORA')}</w:hdr>",
    "word/footer1.xml": f"<w:ftr {NS}>{_p('RODAPE-FORA')}</w:ftr>",
    "word/comments.xml": f"<w:comments {NS}><w:comment w:id='0'>{_p('COMENTARIO-FORA')}"
    "</w:comment></w:comments>",
    "word/footnotes.xml": f"<w:footnotes {NS}>{_p('NOTA-FORA')}</w:footnotes>",
}


def _doc():
    return extrair(_docx(CORPO, extras=EXTRAS))


def test_word_le_por_secao_com_titulos_pelo_estilo():
    doc = _doc()
    assert doc.formato == "docx" and doc.por_secao
    assert [p.titulo for p in doc.paginas] == ["", "Como atendemos", "Quem somos", "Preços"]
    assert doc.paginas[0].texto == ABERTURA  # o sumário automático não entra
    assert doc.paginas_sem_texto == []
    assert "=== SEÇÃO 1: abertura do documento ===" in doc.para_prompt()
    assert "=== SEÇÃO 2: Como atendemos ===" in doc.para_prompt()


def test_cabecalho_rodape_comentario_nota_e_oculto_ficam_de_fora():
    tudo = _doc().para_prompt()
    for fora in ("CABECALHO-FORA", "RODAPE-FORA", "COMENTARIO-FORA", "NOTA-FORA", "OCULTO-FORA"):
        assert fora not in tudo, fora
    assert HORARIO in tudo  # palavra partida em formatação volta inteira


def test_alteracao_marcada_vale_o_texto_como_esta():
    tudo = _doc().para_prompt()
    assert "Resposta em um dia útil por e-mail." in tudo
    assert "quatro horas" not in tudo and "TEXTO-MOVIDO-DAQUI" not in tudo


def test_tabela_entra_uma_linha_por_linha_e_caixa_de_texto_uma_vez():
    doc = _doc()
    assert doc.paginas[3].texto.split("\n") == [
        "Preços",
        "Plano | Valor mensal",
        "Essencial | R$ 8.000",
    ]
    assert doc.para_prompt().count("Selo de qualidade na caixa de texto.") == 1


def test_citacao_mostra_secao_ou_comeco_do_paragrafo():
    doc = _doc()
    ok, n = conferir_trecho(doc, None, "segunda a sexta das 8h às 18h")
    assert ok and referencia(doc, n, "x") == "seção “Como atendemos”"
    ok, n = conferir_trecho(doc, None, "válida por trinta dias corridos")
    assert ok and referencia(doc, n, "válida por trinta dias corridos") == (
        "parágrafo que começa “Proposta de atendimento para a Empresa Exemplo, válida…”"
    )
    assert sem_numero_de_secao(doc, "A seção 1 e a seção 3") == (
        "A abertura do documento e a seção “Quem somos”"
    )


def test_word_estrito_le_pelo_nome_local_das_tags():
    estrito = NS.replace(
        "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "http://purl.oclc.org/ooxml/wordprocessingml/main",
    )
    doc = extrair(_docx(_p(ABERTURA), estilos="", ns=estrito))
    assert doc.paginas[0].texto == ABERTURA


# ── o que não dá para ler ──────────────────────────────────────────────────


def _ole2(fluxo: str) -> bytes:
    return b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100 + fluxo.encode("utf-16-le")


@pytest.mark.parametrize(
    "dados, msg",
    [
        (_ole2("WordDocument"), r"Word antigo \(\.doc\)\. Abra no Word e salve como \.docx"),
        (_ole2("EncryptedPackage"), "tem senha"),
        (b"{\\rtf1\\ansi texto}", r"\.rtf\. Abra no Word e salve como \.docx"),
        (_ole2("PowerPoint Document"), r"\.ppt\) precisa ser salva como \.pptx"),
    ],
)
def test_arquivo_que_nao_da_para_ler_diz_o_que_fazer(dados, msg):
    with pytest.raises(DocumentoRecusado, match=msg):
        detectar_formato(dados)


def test_odt_recusado_com_instrucao():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.text")
    with pytest.raises(DocumentoRecusado, match="LibreOffice"):
        detectar_formato(buf.getvalue())


def test_word_vazio_ou_so_imagem_e_recusado():
    with pytest.raises(DocumentoRecusado, match="não tem texto para ler"):
        extrair(_docx("<w:p><w:r><w:drawing/></w:r></w:p>"))


def test_word_quebrado_e_recusado_com_instrucao():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<w:document <<< quebrado")
    with pytest.raises(DocumentoRecusado, match="salve de novo como .docx"):
        extrair(buf.getvalue())


def test_xml_descompactado_grande_demais_e_recusado(monkeypatch):
    monkeypatch.setattr(word, "LIMITE_XML_BYTES", 100)
    with pytest.raises(DocumentoRecusado, match="grande demais"):
        extrair(_docx(CORPO))


def test_caractere_de_controle_no_xml_e_arquivo_quebrado_nao_leitura_de_lixo():
    # XML 1.0 não aceita caractere de controle: o Word não tem como sair com o lixo do PDF
    # (um nulo antes de cada letra); se vier, o arquivo é recusado, nunca lido
    corpo = _p("".join("&#1;" + c for c in "TEXTO QUE VIROU CONTROLE " * 4))
    with pytest.raises(DocumentoRecusado, match="Não consegui abrir"):
        extrair(_docx(corpo))


def test_limite_de_paginas_nao_vale_para_secao(monkeypatch):
    monkeypatch.setattr(extracao, "LIMITE_PAGINAS", 2)
    assert extrair(_docx(CORPO)).n_paginas == 4
