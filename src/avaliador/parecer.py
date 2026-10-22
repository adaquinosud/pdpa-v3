"""O parecer de uma leitura no formato 3, montado no app (fatia 2, 22/10).

A forma é a aprovada no parecer da Localiza (leitura nº 31): no alto, a frase da ordem; por
subpilar, na ordem do Manual, o que a peça diz (só trechos, um por marca, até quatro), o que
não diz (a frase de cada marca vazia) e o achado; no fim, a nota do bloco C.

O que a peça diz e o que não diz saem da tela JÁ CORRIGIDA (``servico.organizar_marcas`` com as
correções à mão): montar o parecer é corrigir, e cada correção fica gravada. O que a pessoa
escreve (a ordem, os achados, a nota) vem de ``servico.textos_do_parecer``.

É impresso que vai ao cliente: BLOQUEIA, não degrada (CLAUDE.md §10). Enquanto houver
pendência (ordem ou achado em branco, marca sem conferência, leitura feita com outra régua), o
Word não sai, e a tela diz o que falta.

Regras de seleção, decididas em 21-22/10:
- a tela mostra tudo; o parecer escolhe;
- o código da marca nunca aparece; a frase do "não diz" é a da marca (``frase_da_marca``);
- peça SEM cliente com nome: as exceções (o grupo à parte) não entram; COM cliente com nome
  elas já estão dentro de Pa1 e Pa2;
- subpilar sem resposta: "Não encontramos no texto nada que responda a essa expectativa."
"""

from __future__ import annotations

import io
from typing import List

from src.api.painel import NOME_PILAR
from src.avaliador.extracao import _normalizar
from src.avaliador.servico import (
    MARCA_ESTA,
    MARCA_NAO_ESTA,
    MARCA_SEM_CONFERENCIA,
    frase_da_marca,
)
from src.avaliador.veredito import declarar_cobertura

MAX_TRECHOS = 4
SEM_RESPOSTA = "Não encontramos no texto nada que responda a essa expectativa."


def _escolhidos(marcas: List[dict]) -> List[dict]:
    """Um trecho por marca, na ordem do Manual, até quatro; trecho já usado por uma marca
    anterior do mesmo subpilar não se repete (a marca usa o seguinte dela, se houver)."""
    out, usados = [], []
    for x in marcas:
        if x["estado"] != MARCA_ESTA:
            continue
        for e in (e for e in x["evidencias"] if e.get("conferido")):
            alvo = _normalizar(e["trecho"])
            if any(alvo in u or u in alvo for u in usados):
                continue
            out.append({"codigo": x["codigo"], **e})
            usados.append(alvo)
            break
        if len(out) == MAX_TRECHOS:
            break
    return out


def montar(tela: dict, textos: dict, numero: int, data: str, cobertura: dict) -> dict:
    """``tela``: ``servico.organizar_marcas`` (com as correções). ``textos``:
    ``servico.textos_do_parecer``. Devolve o parecer pronto para o Word e as pendências."""
    pendencias: List[str] = []
    if not textos["ordem"].strip():
        pendencias.append("Escreva a frase da ordem, no alto.")
    pilares = []
    for bloco in tela["pilares"]:
        subs = []
        for sp in bloco["subpilares"]:
            s = sp["subpilar"]
            for x in sp["marcas"]:
                if x.get("nota"):
                    pendencias.append(
                        "Esta leitura foi feita antes da régua de hoje (há marca que saiu do "
                        "Manual ou foi reescrita): faça uma leitura nova da peça."
                    )
                if x["estado"] == MARCA_SEM_CONFERENCIA:
                    pendencias.append(
                        f"{s.nome}: resolva a marca sem conferência "
                        f"(“{frase_da_marca(x['texto'], True)}”): inclua o trecho da peça ou "
                        "marque que não está."
                    )
            achado = textos["achados"].get(s.codigo, "").strip()
            if not achado:
                pendencias.append(f"{s.nome}: escreva o achado.")
            subs.append(
                {
                    "codigo": s.codigo,
                    "nome": s.nome,
                    "diz": [e["trecho"] for e in _escolhidos(sp["marcas"])],
                    "nao_diz": [
                        frase_da_marca(x["texto"], False)
                        for x in sp["marcas"]
                        if x["estado"] == MARCA_NAO_ESTA
                    ],
                    "achado": achado,
                }
            )
        pilares.append({"nome": NOME_PILAR[bloco["pilar"].codigo], "subpilares": subs})
    return {
        "titulo": "Parecer PDPA",
        "cabecalho": f"Leitura nº {numero}, {data}. " + " ".join(declarar_cobertura(cobertura)),
        "ordem": textos["ordem"].strip(),
        "pilares": pilares,
        "nota_c": textos["nota_c"].strip(),
        "pendencias": list(dict.fromkeys(pendencias)),  # sem repetir, na ordem
    }


def escolhidos_da_tela(tela: dict) -> set:
    """(código, trecho) de cada trecho que vai para o parecer: a tela marca "vai para o
    parecer" ao lado deles."""
    out = set()
    for bloco in tela["pilares"]:
        for sp in bloco["subpilares"]:
            out |= {(e["codigo"], e["trecho"]) for e in _escolhidos(sp["marcas"])}
    return out


def gerar_docx(p: dict, empresa: str) -> bytes:
    """O Word do parecer. Só chamar sem pendências (quem chama confere)."""
    from docx import Document
    from docx.shared import Pt, RGBColor

    assert not p["pendencias"], "parecer com pendência não vira Word"
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)
    doc.add_heading(f"{p['titulo']}: {empresa}", 0)
    cab = doc.add_paragraph(p["cabecalho"])
    cab.runs[0].italic = True
    doc.add_heading("A ordem", 1)
    doc.add_paragraph(p["ordem"])

    def rotulo(texto):
        r = doc.add_paragraph().add_run(texto)
        r.bold = True
        r.font.size = Pt(10)
        r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    for pilar in p["pilares"]:
        doc.add_heading(pilar["nome"], 1)
        for sp in pilar["subpilares"]:
            doc.add_heading(sp["nome"], 2)
            rotulo("O que a peça diz")
            if sp["diz"]:
                for t in sp["diz"]:
                    q = doc.add_paragraph(f"“{' '.join(t.split())}”")
                    q.paragraph_format.left_indent = Pt(14)
            else:
                doc.add_paragraph(SEM_RESPOSTA)
            if sp["nao_diz"]:
                rotulo("O que a peça não diz")
                for t in sp["nao_diz"]:
                    doc.add_paragraph(t, style="List Bullet")
            rotulo("O achado")
            doc.add_paragraph(sp["achado"])
    if p["nota_c"]:
        doc.add_heading("O que dá para conferir na peça", 1)
        doc.add_paragraph(p["nota_c"])
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
