"""Ligadura perdida na extração de PDF (15/10). Os quatro PDFs em ``tests/dados/pdf_mac``
saíram do macOS (Keynote, Pages, PowerPoint e Word para Mac), com texto INVENTADO para a
calibração de 14/10 (valores fictícios, nenhum material de cliente; confirmado pelo
Alexandre em 15/10) e sem autor nos metadados."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from src.avaliador import extracao
from src.avaliador.extracao import desfazer_ligaduras, extrair, ligaduras_perdidas

DADOS = Path(__file__).parent / "dados" / "pdf_mac"
SEM_PDFTOTEXT = pytest.mark.skipif(
    shutil.which("pdftotext") is None, reason="pdftotext (poppler) não instalado"
)


def _texto(nome: str) -> str:
    return "\n".join(p.texto for p in extrair((DADOS / f"{nome}.pdf").read_bytes()).paginas)


def _palavras(texto: str):
    return re.findall(r"[^\W\d_]+", texto)


def test_desfazer_ligadura_troca_o_caractere_unico_pelas_letras():
    assert desfazer_ligaduras("Conﬁguracao ﬂuxo eﬃcaz oﬀ ﬄ") == (
        "Configuracao fluxo efficaz off ffl"
    )
    assert desfazer_ligaduras("fila sem ligadura") == "fila sem ligadura"


def test_perdida_exige_o_resto_da_palavra_e_conta_pedaco_solto():
    pdftotext = "uma la e Con guracao ao nal fi fi".split()
    pypdf = "uma fila e Configuracao ao final".split()
    assert sorted(ligaduras_perdidas(pdftotext, pypdf)) == [
        "configuracao", "fi", "fi", "fila", "final",
    ]  # fmt: skip
    # o lado inteiro não é punido pelos pedaços soltos do outro
    assert ligaduras_perdidas(pypdf, pdftotext) == []
    # palavra que falta SEM o resto dela não é ligadura perdida (é colagem, outra régua)
    assert ligaduras_perdidas("eficienciae".split(), "eficiencia e".split()) == []
    # pedaço solto do outro lado ("ffi") não vira palavra inteira, nem quando "ff" + "i"
    # pareceria o rastro dela
    assert ligaduras_perdidas(["i"], ["ffi"]) == []


def test_ligadura_desfeita_tambem_na_saida_do_pdftotext(monkeypatch):
    # nos quatro PDFs do Mac o pdftotext arranca o "fi"; outro PDF pode devolver o
    # caractere único, como o pypdf
    texto = "Conﬁguracao e onboarding completo, com diagnostico inicial em quinze dias."
    monkeypatch.setattr(extracao, "_paginas_pdftotext", lambda dados: [texto])
    monkeypatch.setattr(extracao, "_paginas_pypdf", lambda dados: [texto])
    doc = extracao._extrair_pdf(b"")
    assert doc.extrator == "pdftotext"
    assert "Configuracao" in doc.paginas[0].texto


@SEM_PDFTOTEXT
@pytest.mark.parametrize("nome", ["keynote", "pages"])
def test_keynote_e_pages_leem_as_palavras_inteiras_pelo_pypdf(nome):
    doc = extrair((DADOS / f"{nome}.pdf").read_bytes())
    assert doc.extrator == "pypdf"
    palavras = _palavras(_texto(nome))
    for inteira in ("fila", "eficiencia", "Configuracao", "final"):
        assert inteira in palavras
    assert not set(w.lower() for w in palavras) & set(extracao.PEDACOS_LIGADURA)
    assert "ﬁ" not in _texto(nome)


@SEM_PDFTOTEXT
@pytest.mark.parametrize("nome", ["powerpoint", "word"])
def test_powerpoint_e_word_continuam_no_pdftotext_sem_colagem(nome):
    doc = extrair((DADOS / f"{nome}.pdf").read_bytes())
    assert doc.extrator == "pdftotext"
    texto = _texto(nome)
    assert "Relatorioexecutivo" not in texto
    assert "Importacaosemanal" not in texto


@SEM_PDFTOTEXT
def test_medida_nos_quatro_arquivos_como_medido_em_15_10():
    """pdftotext 5 palavras + pedaços soltos (3 no Keynote, 5 no Pages); pypdf zero."""
    esperado = {"keynote": (8, 0), "pages": (10, 0), "powerpoint": (0, 0), "word": (0, 0)}
    for nome, (no_pdftotext, no_pypdf) in esperado.items():
        dados = (DADOS / f"{nome}.pdf").read_bytes()
        pt = _palavras(desfazer_ligaduras("\n".join(extracao._paginas_pdftotext(dados))))
        pp = _palavras(desfazer_ligaduras("\n".join(extracao._paginas_pypdf(dados))))
        assert (len(ligaduras_perdidas(pt, pp)), len(ligaduras_perdidas(pp, pt))) == (
            no_pdftotext,
            no_pypdf,
        ), nome
