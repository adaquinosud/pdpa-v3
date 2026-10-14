"""PDF com dois extratores (pdftotext e pypdf) e a medição de palavra colada. Os textos
são SINTÉTICOS; a forma colada é a da proposta BEXP v9 (PowerPoint → PDF do macOS, 14/10:
"quetrava", "maisvolume"), não o arquivo."""

from __future__ import annotations

import collections
import shutil

import pytest

from src.avaliador import extracao
from src.avaliador.extracao import DocumentoRecusado, extrair, palavras_coladas
from tests.test_avaliador_extracao import _pdf

LIMPO = (
    "Nós respondemos o que trava, onde trava, em qual unidade e em que ordem consertar. "
    "A resposta é sempre muito parecida: pelo que mais aparece, no ponto com mais volume. "
)
COLADO = (
    "Nós respondemos o quetrava, ondetrava, emqual unidade e emque ordem consertar. "
    "A resposta é sempre muitoparecida: pelo que maisaparece, no ponto com maisvolume. "
)


def _vocab(*textos):
    return collections.Counter(w.lower() for t in textos for w in extracao._palavras(t))


def test_colada_e_ligacao_mais_palavra_solta_e_final_de_palavra_nao_conta():
    v = _vocab(LIMPO * 3, COLADO)
    # "emqual" tem 6 letras: abaixo do mínimo de 7 (palavra curta dá falso positivo demais)
    assert palavras_coladas(COLADO, v) == [
        "quetrava", "ondetrava", "muitoparecida", "maisaparece", "maisvolume",
    ]  # fmt: skip
    # "estruturado" = estrutura + do: final de palavra, não colagem; "portanto" é real
    v2 = _vocab("a estrutura do projeto é estruturado. a estrutura e o do. portanto, por tanto")
    assert palavras_coladas("projeto estruturado portanto", v2) == []


def _dois(monkeypatch, pypdf, poppler):
    monkeypatch.setattr(extracao, "_paginas_pypdf", lambda dados: pypdf)
    monkeypatch.setattr(extracao, "_paginas_pdftotext", lambda dados: poppler)
    return _pdf(["x"])


def test_fica_o_extrator_sem_palavra_colada(monkeypatch):
    doc = extrair(_dois(monkeypatch, [COLADO, LIMPO * 3], [LIMPO, LIMPO * 3]))
    assert doc.extrator == "pdftotext" and doc.coladas == []
    assert "quetrava" not in doc.para_prompt()
    doc = extrair(_dois(monkeypatch, [LIMPO, LIMPO * 3], [COLADO, LIMPO * 3]))
    assert doc.extrator == "pypdf" and doc.coladas == []


def test_os_dois_colados_recusa_com_o_numero_antes_de_cobrar(monkeypatch):
    dados = _dois(monkeypatch, [COLADO, LIMPO * 3], [COLADO, LIMPO * 3])
    with pytest.raises(DocumentoRecusado) as exc:
        extrair(dados)
    msg = str(exc.value)
    assert msg.startswith("O texto deste PDF sai com palavras grudadas: 5 de ")
    assert "o limite é 1,0%" in msg and "“quetrava”, “ondetrava”, “muitoparecida”" in msg
    assert "envie o arquivo original (PowerPoint ou Word)" in msg


def test_poucas_coladas_num_texto_grande_nao_recusa(monkeypatch):
    doc = extrair(_dois(monkeypatch, [COLADO + LIMPO * 200], [COLADO + LIMPO * 200]))
    assert 0 < len(doc.coladas) < extracao.FRACAO_COLADAS_RECUSA * doc.palavras


def test_par_colado_que_se_repete_mais_de_duas_vezes_escapa():
    # limite conhecido da régua: palavra que aparece 3+ vezes é tratada como palavra real
    v = _vocab(LIMPO * 3, COLADO * 3)
    assert "quetrava" not in palavras_coladas(COLADO, v)


def test_sem_pdftotext_le_pelo_pypdf(monkeypatch, caplog):
    import subprocess

    def sem_programa(*a, **k):
        raise FileNotFoundError("pdftotext")

    monkeypatch.setattr(subprocess, "run", sem_programa)
    monkeypatch.setattr(extracao, "_paginas_pypdf", lambda dados: [LIMPO])
    doc = extrair(_pdf(["x"]))
    assert doc.extrator == "pypdf" and "pdftotext não instalado" in caplog.text


def test_contagem_de_paginas_diferente_fica_o_pypdf(monkeypatch, caplog):
    doc = extrair(_dois(monkeypatch, [LIMPO, LIMPO], [LIMPO + LIMPO]))
    assert doc.extrator == "pypdf" and doc.n_paginas == 2
    assert "pdftotext leu 1 páginas e o pypdf 2" in caplog.text


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext não instalado")
def test_pdftotext_de_verdade_le_por_pagina_pela_entrada_padrao():
    textos = extracao._paginas_pdftotext(_pdf(["Primeira página do teste.", "Segunda página."]))
    assert [t.strip() for t in textos] == ["Primeira página do teste.", "Segunda página."]
