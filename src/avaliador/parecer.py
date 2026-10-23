"""O parecer de uma leitura no formato 3, montado no app (fatia 2, 22/10).

Na frente, uma página (22/10): uma linha por subpilar com o nome curto do que a peça diz e do
que falta (``frente``), feita só do que a tela tem. Depois, a forma aprovada no parecer da
Localiza (leitura nº 31): no alto, a frase da ordem; por
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
- subpilar sem resposta: "Não encontramos no texto nada que responda a essa expectativa.";
  depois do que a peça não diz e antes do achado, até três frases da biblioteca do "por que
  custa" (``biblioteca.sorteio``, 23/10): a ordem do bloco fica ausência, por que ela custa,
  achado.
"""

from __future__ import annotations

import io
from difflib import SequenceMatcher
from typing import List, Optional

from src.api.painel import NOME_PILAR
from src.avaliador import biblioteca
from src.avaliador.extracao import RODAPE, _normalizar, linha_inteira
from src.avaliador.servico import (
    MARCA_ESTA,
    MARCA_NAO_ESTA,
    MARCA_SEM_CONFERENCIA,
    frase_da_marca,
)
from src.avaliador.veredito import declarar_cobertura

MAX_TRECHOS = 4
SEM_RESPOSTA = "Não encontramos no texto nada que responda a essa expectativa."
# o título das frases da biblioteca no bloco (23/10: as outras três partes têm título)
ROTULO_CUSTA = "Por que isso custa"


def impresso(e: dict, doc=None) -> str:
    """O texto que o parecer imprime para o trecho ``e`` (23/10): a linha inteira da peça
    quando o trecho começa no meio dela (``extracao.linha_inteira``); senão, o trecho como foi
    citado. Sem o texto da peça guardado (``doc`` None: leitura concluída ou com mais de 30
    dias sem uso) não há como saber onde a linha começa, e sai o trecho como foi citado. A
    tela continua mostrando o trecho citado."""
    if doc is None:
        return e["trecho"]
    if "impresso" not in e:
        e["impresso"] = linha_inteira(doc, e.get("pagina_encontrada"), e["trecho"]) or e["trecho"]
    return e["impresso"]


def _ordem_da_marca(x: dict, escolhas: dict) -> List[dict]:
    """Os trechos de uma marca na ordem em que concorrem ao parecer (22/10): o escolhido pela
    pessoa ("usar este no parecer") primeiro; o do rodapé da página por último, para o rodapé
    cru não cair no documento; entre os demais, a ordem da peça (seção; dentro da seção, a
    ordem da leitura). Não "o menor primeiro": na #32 o menor era sempre rótulo de link
    ("Veículo: AGRO+"), que não é falso, só vazio."""
    quero = _normalizar(escolhas.get(x["codigo"], ""))
    evs = [e for e in x["evidencias"] if e.get("conferido")]
    return sorted(
        evs,
        key=lambda e: (
            0 if quero and _normalizar(e["trecho"]) == quero else 1,
            1 if RODAPE in (e.get("referencia") or "") else 0,
            e.get("pagina_encontrada") or float("inf"),  # sem seção: depois das outras
        ),
    )


# Dois trechos que dividem um pedaço de texto maior que esta fração do MENOR deles contam
# como o mesmo trecho (22/10, Exemplo da #32: "Na primeira etapa do programa, dez produtores…"
# e "dez produtores… São pequenas propriedades…", nenhum contido no outro, saíram os dois).
SOBREPOSICAO = 0.5
# ... e o pedaço comum tem de ter pelo menos isto: começo igual curto ("Veículo: AGRO+" e
# "Veículo: EMBRAPII") não faz dois trechos serem o mesmo
MIN_COMUM = 40


def _repete(a: str, b: str) -> bool:
    """Os dois trechos (normalizados) dizem o mesmo: um contido no outro, ou um pedaço comum
    maior que ``SOBREPOSICAO`` do menor e com pelo menos ``MIN_COMUM`` caracteres."""
    if a in b or b in a:
        return True
    comum = SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    return comum.size >= MIN_COMUM and comum.size > SOBREPOSICAO * min(len(a), len(b))


def _escolhidos(
    marcas: List[dict],
    escolhas: Optional[dict] = None,
    impressos: Optional[List[str]] = None,
    doc=None,
) -> List[dict]:
    """Até quatro trechos por bloco. Primeira volta: um trecho de cada marca respondida, na
    ordem do Manual (o primeiro de ``_ordem_da_marca`` que não repete). Se sobrar lugar, novas
    voltas pegam o trecho seguinte das marcas que têm mais, na mesma ordem, até fechar quatro
    (23/10: na Fibrav, Qualidade da Entrega tinha duas marcas com três trechos cada e saíam
    dois). Trecho que repete um já usado no bloco (``_repete``: igual, contido ou com a maior
    parte em comum) não entra, nem o que repete um já impresso em outro bloco (``impressos``),
    a não ser que seja o escolhido pela pessoa. A comparação é pelo texto IMPRESSO
    (``impresso``): dois trechos da mesma linha da peça viram a mesma linha inteira."""
    escolhas = escolhas or {}
    impressos = impressos or []
    out, usados = [], []
    filas = [(x, _ordem_da_marca(x, escolhas)) for x in marcas if x["estado"] == MARCA_ESTA]
    while len(out) < MAX_TRECHOS and any(fila for _, fila in filas):
        for x, fila in filas:
            if len(out) == MAX_TRECHOS:
                break
            quero = _normalizar(escolhas.get(x["codigo"], ""))
            while fila:
                e = fila.pop(0)
                fora = [] if _normalizar(e["trecho"]) == quero else impressos
                alvo = _normalizar(impresso(e, doc))
                if any(_repete(alvo, u) for u in usados + fora):
                    continue
                out.append({"codigo": x["codigo"], **e})
                usados.append(alvo)
                break
    return out


def selecao(tela: dict, escolhas: Optional[dict] = None) -> dict:
    """subpilar → trechos que vão para o parecer, na ordem do Manual. Quem lê o parecer vê
    bloco, não marca: trecho já impresso num bloco anterior não volta, a não ser que o bloco
    fique vazio sem ele (decisão de 22/10)."""
    impressos: List[str] = []
    doc = tela.get("documento")
    out = {}
    for bloco in tela["pilares"]:
        for sp in bloco["subpilares"]:
            picks = _escolhidos(sp["marcas"], escolhas, impressos, doc)
            if not picks:  # sem os repetidos o bloco ficaria vazio: eles voltam
                picks = _escolhidos(sp["marcas"], escolhas, doc=doc)
            impressos += [_normalizar(impresso(e, doc)) for e in picks]
            out[sp["subpilar"].codigo] = picks
    return out


def _lista(nomes: List[str]) -> str:
    return nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]


def linha_da_frente(marcas: List[dict], cliente_nomeado) -> str:
    """Uma linha por subpilar, feita só do que a tela já tem (22/10): o nome curto de cada
    marca que a peça diz e de cada uma que falta, sem nota nem contagem. As marcas que só se
    esperam com cliente nomeado entram só quando a peça TEM cliente nomeado (sem a resposta,
    também ficam fora). Marca sem nome curto (saiu do Manual) usa a frase."""
    vale = [x for x in marcas if cliente_nomeado is True or not x.get("so_cliente_nomeado")]

    def nomes(estado):
        return [
            x.get("nome_curto") or frase_da_marca(x["texto"], estado == MARCA_ESTA)
            for x in vale
            if x["estado"] == estado
        ]

    diz, falta, conferir = nomes(MARCA_ESTA), nomes(MARCA_NAO_ESTA), nomes(MARCA_SEM_CONFERENCIA)
    # com dois-pontos: o nome curto é rótulo, não complemento de "diz" ("ensina sem vender")
    partes = [f"Diz: {_lista(diz)}." if diz else "Nada escrito."]
    partes.append(f"Falta: {_lista(falta)}." if falta else "Nada falta.")
    if conferir:
        partes.append(f"A conferir: {_lista(conferir)}.")
    return " ".join(partes)


def frente(tela: dict) -> List[dict]:
    """A página da frente do parecer: os doze subpilares, na ordem do Manual, com a pergunta
    na voz do leitor e a linha. A tela mostra a mesma página que vai para o Word."""
    perguntas = tela.get("perguntas_leitor") or {}
    return [
        {
            "codigo": sp["subpilar"].codigo,
            "nome": sp["subpilar"].nome,
            "pergunta": perguntas.get(sp["subpilar"].codigo, ""),
            "linha": linha_da_frente(sp["marcas"], tela.get("cliente_nomeado")),
        }
        for bloco in tela["pilares"]
        for sp in bloco["subpilares"]
    ]


def estado_do_rascunho(tela: dict, textos: dict) -> dict:
    """campo → "pendente" | "aceito" | "editado" | "mudou" (aceito, ou ainda pendente, sobre
    uma tela que mudou depois do rascunho: correção ou troca de trecho). Campo que não veio
    do rascunho não aparece."""
    rj = textos.get("rascunho") or {}
    if not rj:
        return {}
    from src.avaliador import rascunho as R

    _, agora = R.entrada(tela, textos.get("escolhas") or {}, "")
    out = {}
    for campo, st in rj.items():
        if st["estado"] != "editado" and st.get("base") != agora:
            out[campo] = "mudou"
        else:
            out[campo] = st["estado"]
    return out


def _pendencias_do_rascunho(tela: dict, textos: dict, falta: dict) -> List[str]:
    """Campo que veio do rascunho do modelo só vai para o Word depois de a pessoa passar por
    ele: editar ou aceitar como está (decisão de 22/10)."""
    nomes = {"ordem": "A ordem"}
    nomes.update(
        {
            sp["subpilar"].codigo: sp["subpilar"].nome
            for b in tela["pilares"]
            for sp in b["subpilares"]
        }
    )
    passe = "(edite ou aceite como está)."
    out = []
    for campo, estado in estado_do_rascunho(tela, textos).items():
        if estado == "pendente":
            out.append(f"{nomes.get(campo, campo)}: passe pelo rascunho do modelo {passe}")
        elif estado == "mudou":
            out.append(
                f"{nomes.get(campo, campo)}: a tela mudou depois do rascunho; "
                f"confira de novo {passe}"
            )
        else:
            continue
        falta["rascunho"] += 1
    return out


def montar(tela: dict, textos: dict, numero: int, data: str, cobertura: dict) -> dict:
    """``tela``: ``servico.organizar_marcas`` (com as correções). ``textos``:
    ``servico.textos_do_parecer``. Devolve o parecer pronto para o Word e as pendências."""
    pendencias: List[str] = []
    # o mesmo que ``pendencias``, contado, para a tela dizer numa linha o que falta
    falta = {
        "empresa": False,
        "ordem": False,
        "achados": 0,
        "conferir": 0,
        "regua": False,
        "rascunho": 0,
    }
    escolhidos = selecao(tela, textos.get("escolhas"))
    empresa = (textos.get("empresa_da_peca") or "").strip()
    if not empresa:
        falta["empresa"] = True
        pendencias.append("Escreva o nome da empresa da peça, que sai no título do Word.")
    if not textos["ordem"].strip():
        falta["ordem"] = True
        pendencias.append("Escreva a frase da ordem, no alto.")
    pilares = []
    for bloco in tela["pilares"]:
        subs = []
        for sp in bloco["subpilares"]:
            s = sp["subpilar"]
            for x in sp["marcas"]:
                if x.get("nota"):
                    falta["regua"] = True
                    pendencias.append(
                        "Esta leitura foi feita antes da régua de hoje (há marca que saiu do "
                        "Manual ou foi reescrita): faça uma leitura nova da peça."
                    )
                if x["estado"] == MARCA_SEM_CONFERENCIA:
                    falta["conferir"] += 1
                    pendencias.append(
                        f"{s.nome}: resolva a marca sem conferência "
                        f"(“{frase_da_marca(x['texto'], True)}”): inclua o trecho da peça ou "
                        "marque que não está."
                    )
            achado = textos["achados"].get(s.codigo, "").strip()
            if not achado:
                falta["achados"] += 1
                pendencias.append(f"{s.nome}: escreva o achado.")
            subs.append(
                {
                    "codigo": s.codigo,
                    "nome": s.nome,
                    "diz": [impresso(e, tela.get("documento")) for e in escolhidos[s.codigo]],
                    "nao_diz": [
                        frase_da_marca(x["texto"], False)
                        for x in sp["marcas"]
                        if x["estado"] == MARCA_NAO_ESTA
                    ],
                    "custa": biblioteca.sorteio(
                        numero, s.codigo, sp["marcas"], tela.get("cliente_nomeado")
                    ),
                    "achado": achado,
                }
            )
        pilares.append({"nome": NOME_PILAR[bloco["pilar"].codigo], "subpilares": subs})
    pendencias += _pendencias_do_rascunho(tela, textos, falta)
    return {
        "titulo": "Parecer PDPA",
        "empresa": empresa,
        "cabecalho": f"Leitura nº {numero}, {data}. " + " ".join(declarar_cobertura(cobertura)),
        "ordem": textos["ordem"].strip(),
        "frente": frente(tela),
        "pilares": pilares,
        # a tela mostra as mesmas frases no bloco do subpilar (só as sorteadas, 23/10)
        "custa": {sp["codigo"]: sp["custa"] for pl in pilares for sp in pl["subpilares"]},
        "nota_c": textos["nota_c"].strip(),
        "pendencias": list(dict.fromkeys(pendencias)),  # sem repetir, na ordem
        "falta": falta,
    }


def escolhidos_da_tela(tela: dict, escolhas: Optional[dict] = None) -> set:
    """(código, trecho) de cada trecho que vai para o parecer: a tela marca "vai para o
    parecer" ao lado deles. Mesma seleção do Word (``selecao``)."""
    return {(e["codigo"], e["trecho"]) for picks in selecao(tela, escolhas).values() for e in picks}


def gerar_docx(p: dict) -> bytes:
    """O Word do parecer. Só chamar sem pendências (quem chama confere)."""
    from docx import Document
    from docx.shared import Pt, RGBColor

    assert not p["pendencias"], "parecer com pendência não vira Word"
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)
    # o nome escrito pela pessoa no parecer, nunca o da empresa da conta no app
    doc.add_heading(f"{p['titulo']}: {p['empresa']}", 0)
    cab = doc.add_paragraph(p["cabecalho"])
    cab.runs[0].italic = True
    doc.add_heading("Em uma página", 1)
    for x in p["frente"]:
        par = doc.add_paragraph()
        par.add_run(x["nome"]).bold = True
        if x["pergunta"]:
            par.add_run(f" · {x['pergunta']}").italic = True
        # a linha no mesmo parágrafo, depois de uma quebra (<w:br/>): em parágrafo próprio a
        # frente passou de uma página para duas (22/10, medido convertendo para PDF)
        par.add_run().add_break()
        par.add_run(x["linha"])
    doc.add_page_break()
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
            if sp.get("custa"):
                rotulo(ROTULO_CUSTA)
                doc.add_paragraph(" ".join(sp["custa"]))
            rotulo("O achado")
            doc.add_paragraph(sp["achado"])
    if p["nota_c"]:
        doc.add_heading("O que dá para conferir na peça", 1)
        doc.add_paragraph(p["nota_c"])
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
