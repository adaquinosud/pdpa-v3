"""Entrada do Avaliador: detecta o formato pelo CONTEÚDO e extrai o texto por página.

- Formato pelos bytes, nunca pela extensão: ``%PDF-`` → pdf; zip com
  ``ppt/presentation.xml`` → pptx. Qualquer outra coisa é recusada com mensagem que
  nomeia o que serve.
- Nada vai para disco: o upload é lido em memória, então não há temporário a limpar.
- PPTX: percorre formas recursivamente (grupos), caixas de texto, células de tabela e a
  nota do apresentador. A nota fica SEPARADA do corpo do slide: o comprador vê o slide,
  normalmente não vê a nota — o motor recebe as duas marcadas, e "página sem texto" é
  julgada pelo corpo.
- PDF (14/10): dois extratores, o pdftotext (poppler, programa à parte, pela entrada
  padrão, sem disco) e o pypdf; fica o que sai com menos página ilegível e menos palavra
  colada ou com ligadura perdida (15/10). Os dois colados = recusa com o número na tela,
  antes de cobrar.
- Limites (decisão do Alexandre, 12/10): 60 MB, 120 páginas, 150 mil caracteres. O de
  caracteres é o que contém custo; o de bytes só barra arquivo absurdo.
"""

from __future__ import annotations

import collections
import io
import json
import logging
import re
import subprocess
import unicodedata
import zipfile
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

LIMITE_BYTES = 60 * 1024 * 1024
LIMITE_PAGINAS = 120
LIMITE_CARACTERES = 150_000
# Página com menos que isto de caracteres não-brancos no corpo = "sem texto" (critério
# exibido na tela junto com a lista das páginas).
MIN_CARACTERES_PAGINA = 20
# Página cujo texto extraído traz caracteres de controle (categoria Cc, fora tabulação e
# quebra de linha) no lugar das letras = "texto ilegível": o gerador do PDF codificou o
# texto de um jeito que o extrator não decodifica ("\x00D\x00I\x00A..." no resumo
# executivo do próprio app, WeasyPrint, 14/10). O texto NÃO vai para o modelo: a leitura
# seria de lixo, com cara de leitura certa. Medido em 150 PDFs locais em 14/10: só os
# resumos executivos do app (todas as páginas) e um mapa astral (1 página, símbolos sem
# letra) passam dos dois cortes; o mínimo absoluto tira página quase vazia (1 nulo em 10).
MIN_CONTROLES_ILEGIVEL = 20
FRACAO_CONTROLES_ILEGIVEL = 0.02
# Trecho citado mais curto que isto não prova nada (uma palavra casa em qualquer lugar).
MIN_CARACTERES_TRECHO = 12

FORMATOS_ACEITOS = "PowerPoint (.pptx), Word (.docx) ou PDF"
# Formatos SEM página: o texto é lido por seção (um título abre uma seção; o que vem antes
# do primeiro título é a abertura) e a citação mostra o título da seção ou o começo do
# parágrafo, nunca um número. Fonte única: motor, tela e prompt perguntam aqui.
FORMATOS_POR_SECAO = frozenset({"web", "docx"})
ABERTURA = {"web": "abertura da página", "docx": "abertura do documento"}
# Título NOSSO da seção do rodapé do site (página da web). Como a abertura, não é texto do
# documento: a referência o mostra sem aspas.
RODAPE = "rodapé da página"
# Linha de tabela (PowerPoint, Word) vira uma linha de texto com as células separadas por
# isto. O separador é NOSSO, não existe no documento: a tela mostra a citação de linha de
# tabela célula por célula (e linha por linha, quando o trecho junta duas linhas), para o
# Ctrl+F achar cada pedaço.
SEPARADOR_CELULA = " | "
FORMATOS_COM_TABELA = frozenset({"pptx", "docx"})
# Quantas palavras do parágrafo nomeiam o lugar da citação quando a seção não tem título.
PALAVRAS_REFERENCIA = 8


class DocumentoRecusado(ValueError):
    """O documento não pode ser lido. A mensagem vai para a tela como está."""


@dataclass
class Pagina:
    numero: int
    texto: str
    notas: str = ""
    titulo: str = ""  # página da web: o título da seção ("" = abertura da página)
    # Página da web lida junto com outras (17/10): o endereço de onde a seção veio. Vazio
    # em todo o resto (arquivo, texto colado, uma página só).
    endereco: str = ""

    @property
    def sem_texto(self) -> bool:
        return len(re.sub(r"\s", "", self.texto)) < MIN_CARACTERES_PAGINA


@dataclass
class Documento:
    formato: str
    paginas: List[Pagina] = field(default_factory=list)
    # Só do PDF, só na extração (não vai para o banco): qual extrator ficou, quantas
    # palavras saíram coladas nele e quantas perderam a ligadura (palavra ou pedaço solto).
    extrator: str = ""
    palavras: int = 0
    coladas: List[str] = field(default_factory=list)
    ligaduras: List[str] = field(default_factory=list)

    @property
    def n_paginas(self) -> int:
        return len(self.paginas)

    @property
    def por_secao(self) -> bool:
        return self.formato in FORMATOS_POR_SECAO

    @property
    def nome_abertura(self) -> str:
        return ABERTURA.get(self.formato, "abertura")

    @property
    def enderecos(self) -> List[str]:
        """As páginas da web lidas juntas, na ordem em que foram enviadas."""
        vistos: List[str] = []
        for p in self.paginas:
            if p.endereco and p.endereco not in vistos:
                vistos.append(p.endereco)
        return vistos

    @property
    def paginas_sem_texto(self) -> List[int]:
        if self.por_secao:  # seção curta é seção curta, não slide-imagem
            return []
        return [p.numero for p in self.paginas if p.sem_texto]

    @property
    def total_caracteres(self) -> int:
        return sum(len(p.texto) + len(p.notas) for p in self.paginas)

    def para_json(self) -> str:
        return json.dumps(
            {
                "formato": self.formato,
                "paginas": [
                    {
                        "n": p.numero,
                        "texto": p.texto,
                        "notas": p.notas,
                        "titulo": p.titulo,
                        "endereco": p.endereco,
                    }
                    for p in self.paginas
                ],
            },
            ensure_ascii=False,
        )

    @classmethod
    def de_json(cls, raw: str) -> "Documento":
        d = json.loads(raw)
        return cls(
            formato=d["formato"],
            paginas=[
                Pagina(
                    p["n"],
                    p["texto"],
                    p.get("notas", ""),
                    p.get("titulo", ""),
                    p.get("endereco", ""),
                )
                for p in d["paginas"]
            ],
        )

    def para_prompt(self) -> str:
        """Texto do documento como o modelo o recebe: página a página, numerado, com a
        nota do apresentador marcada à parte."""
        blocos = []
        for p in self.paginas:
            corpo = p.texto.strip() or "[página sem texto legível]"
            if self.formato == "texto":
                rotulo = "TEXTO COLADO"
            elif self.por_secao:
                rotulo = f"SEÇÃO {p.numero}: {p.titulo or self.nome_abertura}"
                if p.endereco:
                    rotulo += f" (página {caminho(p.endereco)})"
            else:
                rotulo = f"PÁGINA {p.numero}"
            bloco = f"=== {rotulo} ===\n{corpo}"
            if p.notas.strip():
                bloco += (
                    "\n--- nota do apresentador (o comprador normalmente NÃO vê) ---\n"
                    + p.notas.strip()
                )
            blocos.append(bloco)
        return "\n\n".join(blocos)


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


# Arquivo antigo do Office (.doc, .ppt) e arquivo do Office com SENHA usam o mesmo
# contêiner (OLE2); o que diz qual é qual é o nome do fluxo interno, gravado em UTF-16.
_OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _tem_fluxo(dados: bytes, nome: str) -> bool:
    return nome.encode("utf-16-le") in dados


def detectar_formato(dados: bytes) -> str:
    if dados.startswith(b"%PDF-"):
        return "pdf"
    if dados[:4] == b"PK\x03\x04":
        try:
            z = zipfile.ZipFile(io.BytesIO(dados))
            nomes = set(z.namelist())
        except zipfile.BadZipFile:
            raise DocumentoRecusado(f"Arquivo corrompido. Envie {FORMATOS_ACEITOS}.")
        if "ppt/presentation.xml" in nomes:
            return "pptx"
        if "word/document.xml" in nomes:
            return "docx"
        if "mimetype" in nomes and b"opendocument" in z.read("mimetype")[:100]:
            raise DocumentoRecusado(
                "Arquivo do LibreOffice (.odt ou .odp). Abra e salve como Word (.docx) "
                f"ou PowerPoint (.pptx), ou exporte como PDF. Aceito: {FORMATOS_ACEITOS}."
            )
    if dados.startswith(_OLE2):
        if _tem_fluxo(dados, "EncryptedPackage"):
            raise DocumentoRecusado(
                "O arquivo tem senha. Abra, tire a senha e envie de novo, ou exporte como PDF."
            )
        if _tem_fluxo(dados, "WordDocument"):
            raise DocumentoRecusado(
                "Documento do Word antigo (.doc). Abra no Word e salve como .docx (Arquivo › "
                "Salvar como › Documento do Word), ou exporte como PDF, e envie de novo."
            )
    if dados.lstrip()[:5] == b"{\\rtf":
        raise DocumentoRecusado(
            "Arquivo .rtf. Abra no Word e salve como .docx, ou exporte como PDF, e envie de novo."
        )
    raise DocumentoRecusado(
        f"Formato não reconhecido. Envie {FORMATOS_ACEITOS}. "
        "Apresentação antiga (.ppt) precisa ser salva como .pptx antes."
    )


def _textos_forma(shape) -> List[str]:
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    out: List[str] = []
    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        for s in shape.shapes:
            out.extend(_textos_forma(s))
        return out
    if getattr(shape, "has_text_frame", False) and shape.has_text_frame:
        t = shape.text_frame.text
        if t.strip():
            out.append(t)
    if getattr(shape, "has_table", False) and shape.has_table:
        for row in shape.table.rows:
            celulas = [c.text.strip() for c in row.cells if c.text.strip()]
            if celulas:
                out.append(SEPARADOR_CELULA.join(celulas))
    return out


def _extrair_pptx(dados: bytes) -> Documento:
    from pptx import Presentation

    try:
        prs = Presentation(io.BytesIO(dados))
    except Exception:  # noqa: BLE001 — qualquer falha do parser = arquivo ilegível
        raise DocumentoRecusado(f"Não consegui abrir a apresentação. Envie {FORMATOS_ACEITOS}.")
    paginas: List[Pagina] = []
    for i, slide in enumerate(prs.slides, start=1):
        textos: List[str] = []
        for shape in slide.shapes:
            textos.extend(_textos_forma(shape))
        notas = ""
        if slide.has_notes_slide:
            notas = (
                slide.notes_slide.notes_text_frame.text
                if slide.notes_slide.notes_text_frame
                else ""
            )
        paginas.append(Pagina(i, _nfc("\n".join(textos)), _nfc(notas)))
    return Documento("pptx", paginas)


# ── PDF: dois extratores e a medição de palavra colada ────────────────────

TEMPO_PDFTOTEXT_S = 60
# Recusa por palavra colada: pelo menos isto de palavras E desta fração, no MELHOR dos dois
# extratores. ⚠️ NÃO CALIBRADO (14/10): em 140 PDFs locais o maior valor limpo foi 0,21% e
# nenhum PDF teve os dois extratores colados; a proposta BEXP v9 (PowerPoint → PDF do
# macOS) tem 0,33% no pypdf e 0% no pdftotext. O corte fica 5× acima do maior limpo até os
# PDFs dos caminhos da Apple (Keynote, Pages, Word e PowerPoint para Mac, Safari, Canva).
# Medidos em 15/10 (Keynote, Pages, Word e PowerPoint para Mac): 0% no melhor extrator nos
# quatro; não dizem nada sobre o corte, que segue sem calibração.
MIN_COLADAS_RECUSA = 5
FRACAO_COLADAS_RECUSA = 0.01
# Colada = palavra de 7+ letras, rara no documento, que se parte em PALAVRA DE LIGAÇÃO +
# palavra que aparece solta ("que·trava", "mais·volume", "muito·parecida"), ou palavra +
# ligação longa que não é final de palavra ("custo·para"). Ligação curta no fim ("·do",
# "·da", "·quem") é final de palavra real ("estrutura·do") e não conta.
_LIGACAO_INICIO = frozenset(
    """de da do das dos em no na nos nas um uma uns umas que se por para pra com sem sob
    sobre entre até ao aos à às o os a as e ou mas mais menos muito muita muitos muitas
    pouco onde quando como qual quais quem cada todo toda todos todas seu sua seus suas
    nosso nossa nossos nossas este esta estes estas esse essa esses essas isso isto já não
    sim também só ainda bem mal ser é são foi está estão há tem têm vai pelo pela pelos
    pelas num numa""".split()
)
_LIGACAO_FIM = frozenset(
    "para com sobre entre onde quando como mais muito não pelo pela pelos pelas cada".split()
)
_PALAVRAS_REAIS = frozenset(
    """porque porquanto portanto entretanto sobretudo contudo todavia embora enquanto
    conquanto debaixo depois demais deveras outrossim apenas acerca através abaixo acima
    adiante""".split()
)


def _palavras(texto: str) -> List[str]:
    return re.findall(r"[^\W\d_]+", texto)


def palavras_coladas(texto: str, vocab: "collections.Counter[str]") -> List[str]:
    """As palavras coladas do texto, julgadas contra ``vocab`` (contagem das palavras, em
    minúsculas, de TODOS os extratores do mesmo arquivo)."""
    out = []
    for w in _palavras(texto):
        p = w.lower()
        if len(p) < 7 or vocab[p] > 2 or p in _PALAVRAS_REAIS:
            continue
        for i in range(2, len(p) - 1):
            a, b = p[:i], p[i:]
            if (a in _LIGACAO_INICIO and len(b) >= 3 and vocab[b] >= 2) or (
                b in _LIGACAO_FIM and len(a) >= 3 and vocab[a] >= 2
            ):
                out.append(w)
                break
    return out


# Ligadura (15/10, PDFs do Keynote e do Pages pelo Quartz do macOS): a fonte desenha "fi"
# num glifo só. O pypdf devolve o caractere único (U+FB01), que a normalização NFC não
# desfaz; o pdftotext tira as letras de dentro da palavra e solta o pedaço adiante
# ("Con guracao", "uma la", "ao nal" ... "fi"). Os dois saem com a ligadura desfeita e o
# escolhedor conta a perda.
_LIGADURAS = {chr(c): unicodedata.normalize("NFKC", chr(c)) for c in range(0xFB00, 0xFB07)}
# ⚠️ Lista OBSERVADA até aqui (só "fi" apareceu de fato). Ligadura fora dela passa sem
# aviso: a palavra chega partida e nenhuma régua conta.
PEDACOS_LIGADURA = ("ffi", "ffl", "ff", "fi", "fl")


def desfazer_ligaduras(texto: str) -> str:
    return "".join(_LIGADURAS.get(ch, ch) for ch in texto)


def ligaduras_perdidas(este: List[str], outro: List[str]) -> List[str]:
    """Palavras com letras de ligadura que ``outro`` tem inteiras e ``este`` não tem, MAS
    tem o resto delas sem essas letras ("configuracao" → "con" e "guracao"), mais cada
    pedaço de ligadura solto em ``este``. Comparação direta entre os extratores, sem
    dicionário; pedaço solto do outro lado não conta como palavra inteira.

    Limites conhecidos (aceitos pelo Alexandre em 15/10, revistos depois de 29/10):
    - se ``este`` legitimamente não tem a palavra e por coincidência tem o resto dela,
      conta um ponto falso;
    - PowerPoint e Word são decididos por EMPATE em zero, não por esta medida nem pela de
      coladas: as 13 coladas do pypdf no PowerPoint ("relatorio·executivo") são
      invisíveis às duas réguas. Arquivo em que o pdftotext cola e o pypdf não erra o
      desempate e nada avisa."""
    tem = collections.Counter(w.lower() for w in este)
    inteiras = collections.Counter(w.lower() for w in outro if w.lower() not in PEDACOS_LIGADURA)

    def tem_o_resto(w: str) -> bool:
        for p in PEDACOS_LIGADURA:
            for m in re.finditer(p, w):
                i, j = m.span()
                resto = [r for r in (w[:i], w[j:]) if r]
                if resto and all(tem[r] for r in resto):
                    return True
        return False

    out = [w for w in (inteiras - tem).elements() if tem_o_resto(w)]
    return out + [w for w in este if w.lower() in PEDACOS_LIGADURA]


def _pct(fracao: float) -> str:
    return f"{100 * fracao:.1f}%".replace(".", ",")


def _paginas_pdftotext(dados: bytes) -> Optional[List[str]]:
    """Texto por página pelo pdftotext (poppler; GPL, chamado como programa à parte,
    decisão do Alexandre de 14/10). None se o programa não existe ou falha: o pypdf segue
    sozinho, e o log diz por quê."""
    try:
        r = subprocess.run(
            ["pdftotext", "-enc", "UTF-8", "-", "-"],
            input=dados,
            capture_output=True,
            timeout=TEMPO_PDFTOTEXT_S,
        )
    except FileNotFoundError:
        logger.warning("[avaliador] pdftotext não instalado; PDF lido só pelo pypdf")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("[avaliador] pdftotext passou do tempo; PDF lido só pelo pypdf")
        return None
    if r.returncode != 0:
        logger.warning(f"[avaliador] pdftotext falhou (código {r.returncode}); só pypdf")
        return None
    paginas = r.stdout.decode("utf-8", "replace").split("\f")
    if paginas and not paginas[-1].strip():
        paginas.pop()  # o pdftotext fecha toda página com \f
    return paginas


def _extrair_pdf(dados: bytes) -> Documento:
    textos_pypdf = [desfazer_ligaduras(t) for t in _paginas_pypdf(dados)]
    candidatos = [("pypdf", textos_pypdf)]
    textos_poppler = _paginas_pdftotext(dados)
    if textos_poppler is not None:
        textos_poppler = [desfazer_ligaduras(t) for t in textos_poppler]
        if len(textos_poppler) == len(textos_pypdf):
            candidatos.insert(0, ("pdftotext", textos_poppler))  # empate: fica o pdftotext
        else:
            logger.warning(
                f"[avaliador] pdftotext leu {len(textos_poppler)} páginas e o pypdf "
                f"{len(textos_pypdf)}; fica o pypdf"
            )
    vocab = collections.Counter(
        w.lower() for _, textos in candidatos for t in textos for w in _palavras(t)
    )

    def legivel(textos):
        return "\n".join(t for t in textos if not _ilegivel(t))

    def perdidas(nome):
        este = _palavras(legivel(dict(candidatos)[nome]))
        outros = [w for n, ts in candidatos if n != nome for w in _palavras(legivel(ts))]
        return ligaduras_perdidas(este, outros)

    def nota(c):
        nome, textos = c
        ilegiveis = sum(1 for t in textos if _ilegivel(t))
        n = max(len(_palavras(legivel(textos))), 1)
        defeitos = len(palavras_coladas(legivel(textos), vocab)) + len(perdidas(nome))
        return (ilegiveis, defeitos / n)

    nome, textos = min(candidatos, key=nota)  # min é estável: no empate, o primeiro
    doc = Documento(
        "pdf",
        [Pagina(i, _nfc(t)) for i, t in enumerate(textos, start=1)],
        extrator=nome,
        palavras=len(_palavras(legivel(textos))),
        coladas=palavras_coladas(legivel(textos), vocab),
        ligaduras=perdidas(nome),
    )
    logger.info(
        f"[avaliador] PDF: extrator {nome}, {len(doc.coladas)} de {doc.palavras} palavras "
        f"coladas, {len(doc.ligaduras)} com ligadura perdida"
    )
    return doc


def _paginas_pypdf(dados: bytes) -> List[str]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(dados))
        if reader.is_encrypted and not reader.decrypt(""):
            raise DocumentoRecusado("O PDF tem senha. Envie uma versão sem senha.")
        paginas_pdf = list(reader.pages)
    except DocumentoRecusado:
        raise
    except Exception:  # noqa: BLE001
        raise DocumentoRecusado(f"Não consegui abrir o PDF. Envie {FORMATOS_ACEITOS}.")
    textos: List[str] = []
    for pg in paginas_pdf:
        try:
            textos.append(pg.extract_text() or "")
        except Exception:  # noqa: BLE001 — página ilegível conta como sem texto, não derruba
            textos.append("")
    return textos


_BRANCOS_DE_CONTROLE = frozenset("\t\n\r\x0b\x0c")


def _ilegivel(texto: str) -> bool:
    controles = sum(
        1 for c in texto if c not in _BRANCOS_DE_CONTROLE and unicodedata.category(c) == "Cc"
    )
    letras = len(re.sub(r"\s", "", texto))
    return controles >= MIN_CONTROLES_ILEGIVEL and controles > FRACAO_CONTROLES_ILEGIVEL * letras


def _tirar_ilegiveis(doc: Documento) -> List[int]:
    """Esvazia o texto das páginas ilegíveis (viram "sem texto legível", listadas na tela
    com o critério) e devolve os números delas."""
    numeros = []
    for p in doc.paginas:
        sujo = False
        if _ilegivel(p.texto):
            p.texto, sujo = "", True
        if _ilegivel(p.notas):
            p.notas, sujo = "", True
        if sujo:
            numeros.append(p.numero)
    return numeros


def extrair(dados: bytes) -> Documento:
    """Detecta o formato e extrai. Levanta ``DocumentoRecusado`` com mensagem de tela."""
    if len(dados) > LIMITE_BYTES:
        raise DocumentoRecusado(
            f"Arquivo maior que {LIMITE_BYTES // (1024 * 1024)} MB. "
            "Reduza as imagens ou exporte como PDF."
        )
    formato = detectar_formato(dados)
    if formato == "docx":
        from src.avaliador.word import extrair_docx

        doc = extrair_docx(dados)
    else:
        doc = _extrair_pptx(dados) if formato == "pptx" else _extrair_pdf(dados)
    if doc.n_paginas == 0:
        raise DocumentoRecusado("O documento não tem páginas.")
    # seção não é página: documento por seção é limitado só pelos caracteres
    if not doc.por_secao and doc.n_paginas > LIMITE_PAGINAS:
        raise DocumentoRecusado(
            f"O documento tem {doc.n_paginas} páginas; o limite é {LIMITE_PAGINAS}."
        )
    if doc.total_caracteres > LIMITE_CARACTERES:
        raise DocumentoRecusado(
            f"O documento tem texto demais para uma leitura ({doc.total_caracteres:,} "
            f"caracteres; o limite é {LIMITE_CARACTERES:,}).".replace(",", ".")
        )
    ilegiveis = _tirar_ilegiveis(doc)
    if len(doc.paginas_sem_texto) == doc.n_paginas and ilegiveis:
        raise DocumentoRecusado(
            f"O texto deste arquivo saiu ilegível: em {len(ilegiveis)} de {doc.n_paginas} "
            "páginas, a extração devolve caracteres de controle no lugar das letras. Isso "
            "vem do programa que gerou o arquivo, e uma leitura em cima disso seria "
            "inventada. Gere o arquivo por outro programa ou cole o texto da peça."
        )
    if doc.por_secao and all(_ilegivel(p.texto) or p.sem_texto for p in doc.paginas):
        # por seção não há "página sem texto"; documento inteiro vazio é recusado aqui
        raise DocumentoRecusado(
            "O documento não tem texto para ler: está vazio, ou o conteúdo é só imagem. "
            "A leitura de imagem ainda não existe."
        )
    if (
        doc.formato == "pdf"
        and len(doc.coladas) >= MIN_COLADAS_RECUSA
        and len(doc.coladas) >= FRACAO_COLADAS_RECUSA * doc.palavras
    ):
        exemplos = ", ".join(f"“{w}”" for w in doc.coladas[:3])
        raise DocumentoRecusado(
            f"O texto deste PDF sai com palavras grudadas: {len(doc.coladas)} de "
            f"{doc.palavras} palavras ({_pct(len(doc.coladas) / doc.palavras)}; o limite é "
            f"{_pct(FRACAO_COLADAS_RECUSA)}), por exemplo {exemplos}. A leitura seria feita "
            "sobre um texto pior que a peça. Isso vem do programa que gerou o PDF: envie o "
            "arquivo original (PowerPoint ou Word), gere o PDF por outro programa ou cole o "
            "texto da peça."
        )
    if len(doc.paginas_sem_texto) == doc.n_paginas:
        raise DocumentoRecusado(
            "Nenhuma página tem texto legível: o documento parece ser só imagem. "
            "A leitura de imagem ainda não existe."
        )
    return doc


def documento_de_texto(texto: str) -> Documento:
    """Texto colado (uma conversa, um e-mail, uma transcrição). Vira um documento de uma
    "página" só — a citação é conferida contra ele inteiro. Mesmos limites do arquivo."""
    t = _nfc(texto or "").strip()
    if len(re.sub(r"\s", "", t)) < MIN_CARACTERES_PAGINA:
        raise DocumentoRecusado("Cole o texto da conversa ou do documento (está vazio).")
    if len(t) > LIMITE_CARACTERES:
        raise DocumentoRecusado(
            f"O texto é longo demais para uma leitura ({len(t):,} caracteres; o limite é "
            f"{LIMITE_CARACTERES:,}).".replace(",", ".")
        )
    return Documento("texto", [Pagina(1, t)])


def caminho(endereco: str) -> str:
    """O que a tela e o pedido mostram de um endereço: o caminho ("/consultoria/"); a página
    inicial é "/"."""
    from urllib.parse import urlsplit

    return urlsplit(endereco).path or "/"


def nome_secao(doc: Documento, numero: int) -> str:
    """“Título” da seção; título que se repete no documento leva a ordem ("“Preços” (2ª)"),
    senão a citação não diz qual das duas. Sem título: "" (quem chama decide)."""
    pag = next((p for p in doc.paginas if p.numero == numero), None)
    if pag is None or not pag.titulo:
        return ""
    if doc.formato == "web" and pag.titulo == RODAPE:
        return RODAPE
    iguais = [p.numero for p in doc.paginas if p.titulo == pag.titulo]
    ordem = f" ({iguais.index(numero) + 1}ª)" if len(iguais) > 1 else ""
    return f"“{pag.titulo}”{ordem}"


def referencia(doc: Documento, numero: Optional[int], trecho: str) -> str:
    """Onde o usuário acha o trecho num documento por seção (página da web, Word): o
    título da seção; sem título (a abertura), as primeiras palavras do parágrafo onde o
    trecho está."""
    pag = next((p for p in doc.paginas if p.numero == numero), None)
    if pag is None:
        return ""
    if pag.endereco:  # várias páginas lidas juntas: diz de qual
        sem = Pagina(pag.numero, pag.texto, pag.notas, pag.titulo)
        resto = referencia(Documento(doc.formato, [sem]), numero, trecho)
        return f"página {caminho(pag.endereco)}, {resto}"
    if doc.formato == "web" and pag.titulo == RODAPE:
        return RODAPE
    if pag.titulo:
        return f"seção {nome_secao(doc, pag.numero)}"
    alvo = _normalizar(trecho)
    paragrafos = pag.texto.split("\n")
    achado = next((x for x in paragrafos if alvo and alvo in _normalizar(x)), paragrafos[0])
    if doc.formato in FORMATOS_COM_TABELA and SEPARADOR_CELULA in achado:
        return f"linha da tabela que começa “{achado.split(SEPARADOR_CELULA)[0].strip()}”"
    palavras = achado.split()
    inicio = " ".join(palavras[:PALAVRAS_REFERENCIA])
    reticencias = "…" if len(palavras) > PALAVRAS_REFERENCIA else ""
    return f"parágrafo que começa “{inicio}{reticencias}”"


def referencia_curta(ref: str) -> str:
    """O "onde" da tela de marcas (22/10): ``referencia`` gravada, encurtada só para exibir.
    Várias páginas: só o caminho ("/media/"; o rodapé, "/ · rodapé"), porque na web o título
    da seção é muitas vezes uma frase inteira que repetia o trecho logo ao lado. Título de
    seção longo: as primeiras palavras. O gravado não muda (o parecer lê o rodapé nele)."""
    ref = ref or ""
    m = re.match(r"página (\S+), (.*)$", ref, re.S)
    if m:
        return m.group(1) + (" · rodapé" if m.group(2) == RODAPE else "")
    m = re.match(r"seção “(.*)”(.*)$", ref, re.S)
    if m:
        palavras = m.group(1).split()
        if len(palavras) > PALAVRAS_REFERENCIA:
            return f"seção “{' '.join(palavras[:PALAVRAS_REFERENCIA])}…”{m.group(2)}"
    return ref


# ── conferência de citação ────────────────────────────────────────────────

_TROCAS = str.maketrans(
    {"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "–": "-", "—": "-", " ": " "}
)


def _normalizar(s: str) -> str:
    return re.sub(r"\s+", " ", _nfc(s).translate(_TROCAS)).strip()


def conferir_trecho(
    doc: Documento, pagina: Optional[int], trecho: str
) -> Tuple[bool, Optional[int]]:
    """O trecho citado existe na peça? ``(conferido, pagina_encontrada)``; a regra é a de
    ``localizar_trecho``."""
    achada, _, _ = localizar_trecho(doc, pagina, trecho)
    return achada is not None, achada


# Medido em 21/10 (13 leituras do site da Loyall, 919 citações, 58 recusadas): 37 eram o
# título de um bloco emendado ao texto de baixo com pontuação que a peça não tem
# ("Consultoria de CX: Diagnóstico…", onde a peça tem uma quebra de linha) e 10 eram dois
# pedaços literais da mesma seção juntados por reticências. Nos dois casos a palavra é
# toda da peça; o que o modelo põe é a costura.
AJUSTE_EMENDA = "emenda"
AJUSTE_ELISAO = "elisao"
MARCA_ELISAO = " […] "
_JUNCAO = r"\s*[:.|·-]\s+"
_ELISAO = re.compile(r"\s*(?:\[\s*(?:\.\.\.|…)\s*\]|\(\s*(?:\.\.\.|…)\s*\)|\.\.\.|…)\s*")


def _com_quebras(s: str) -> str:
    """Como ``_normalizar``, mas guardando as quebras de linha (uma por vez)."""
    s = re.sub(r"[^\S\n]+", " ", _nfc(s).translate(_TROCAS))
    return re.sub(r" ?\n[ \n]*", "\n", s).strip()


def _padrao(alvo: str) -> "re.Pattern":
    """Cada espaço do trecho casa com espaço ou quebra; cada pontuação de junção casa com
    ela mesma OU com uma quebra de linha da peça (e só com quebra: pontuação que a peça
    não tem, num lugar onde a peça não quebra a linha, continua recusada)."""
    rx = ""
    for i, pedaco in enumerate(re.split(f"({_JUNCAO})", alvo)):
        literal = re.escape(pedaco).replace(r"\ ", "[ \n]")
        rx += f"(?:{literal}|\n)" if i % 2 else literal
    return re.compile(rx)


def _achar(fonte: str, alvo: str, inicio: int = 0) -> Optional[Tuple[int, str]]:
    """(fim, como está na peça, com quebra virando espaço) ou None."""
    m = _padrao(alvo).search(fonte, inicio)
    if m is None:
        return None
    return m.end(), m.group(0).replace("\n", " ")


def localizar_trecho(
    doc: Documento, pagina: Optional[int], trecho: str
) -> Tuple[Optional[int], str, str]:
    """O trecho citado existe na peça? Devolve ``(pagina_encontrada ou None, o trecho como
    está na peça, ajuste)``.

    Normaliza só espaço, Unicode (NFC) e aspas/travessões tipográficos — nada de
    maiúscula/minúscula nem paráfrase. Procura primeiro na página citada, depois nas
    outras. Trecho curto demais nunca confere. Duas costuras do modelo são aceitas (21/10),
    sempre com toda palavra literal e devolvendo o trecho como está na peça, para a tela
    não mostrar o que a peça não diz:
    - ``emenda``: pontuação de junção onde a peça tem uma quebra de linha;
    - ``elisao``: pedaços separados por reticências, cada um com o mínimo de caracteres,
      todos na MESMA página ou seção e na ordem da peça; a tela mostra " […] " entre eles.
    """
    alvo = _normalizar(trecho)
    if len(alvo) < MIN_CARACTERES_TRECHO:
        return None, trecho, ""
    ordem = sorted(doc.paginas, key=lambda p: 0 if p.numero == pagina else 1)
    for p in ordem:
        if alvo in _normalizar(p.texto) or alvo in _normalizar(p.notas):
            return p.numero, trecho, ""
    for p in ordem:
        for campo in (p.texto, p.notas):
            achado = _achar(_com_quebras(campo), alvo)
            if achado:
                return p.numero, achado[1], AJUSTE_EMENDA
    partes = [x.strip() for x in _ELISAO.split(alvo) if x.strip()]
    if len(partes) < 2 or any(len(x) < MIN_CARACTERES_TRECHO for x in partes):
        if len(partes) == 1 and partes[0] != alvo:  # reticências só na ponta
            achada, literal, _ = localizar_trecho(doc, pagina, partes[0])
            if achada is not None:
                return achada, literal, AJUSTE_ELISAO
        return None, trecho, ""
    for p in ordem:
        for campo in (p.texto, p.notas):
            fonte, pos, literais = _com_quebras(campo), 0, []
            for parte in partes:
                achado = _achar(fonte, parte, pos)
                if achado is None:
                    break
                pos, literal = achado
                literais.append(literal)
            else:
                return p.numero, MARCA_ELISAO.join(literais), AJUSTE_ELISAO
    return None, trecho, ""
