"""Entrada do Avaliador: detecta o formato pelo CONTEÚDO e extrai o texto por página.

- Formato pelos bytes, nunca pela extensão: ``%PDF-`` → pdf; zip com
  ``ppt/presentation.xml`` → pptx. Qualquer outra coisa é recusada com mensagem que
  nomeia o que serve.
- Nada vai para disco: o upload é lido em memória, então não há temporário a limpar.
- PPTX: percorre formas recursivamente (grupos), caixas de texto, células de tabela e a
  nota do apresentador. A nota fica SEPARADA do corpo do slide: o comprador vê o slide,
  normalmente não vê a nota — o motor recebe as duas marcadas, e "página sem texto" é
  julgada pelo corpo.
- Limites (decisão do Alexandre, 12/10): 60 MB, 120 páginas, 150 mil caracteres. O de
  caracteres é o que contém custo; o de bytes só barra arquivo absurdo.
"""

from __future__ import annotations

import io
import json
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

LIMITE_BYTES = 60 * 1024 * 1024
LIMITE_PAGINAS = 120
LIMITE_CARACTERES = 150_000
# Página com menos que isto de caracteres não-brancos no corpo = "sem texto" (critério
# exibido na tela junto com a lista das páginas).
MIN_CARACTERES_PAGINA = 20
# Trecho citado mais curto que isto não prova nada (uma palavra casa em qualquer lugar).
MIN_CARACTERES_TRECHO = 12

FORMATOS_ACEITOS = "PowerPoint (.pptx) ou PDF"


class DocumentoRecusado(ValueError):
    """O documento não pode ser lido. A mensagem vai para a tela como está."""


@dataclass
class Pagina:
    numero: int
    texto: str
    notas: str = ""

    @property
    def sem_texto(self) -> bool:
        return len(re.sub(r"\s", "", self.texto)) < MIN_CARACTERES_PAGINA


@dataclass
class Documento:
    formato: str
    paginas: List[Pagina] = field(default_factory=list)

    @property
    def n_paginas(self) -> int:
        return len(self.paginas)

    @property
    def paginas_sem_texto(self) -> List[int]:
        return [p.numero for p in self.paginas if p.sem_texto]

    @property
    def total_caracteres(self) -> int:
        return sum(len(p.texto) + len(p.notas) for p in self.paginas)

    def para_json(self) -> str:
        return json.dumps(
            {
                "formato": self.formato,
                "paginas": [
                    {"n": p.numero, "texto": p.texto, "notas": p.notas} for p in self.paginas
                ],
            },
            ensure_ascii=False,
        )

    @classmethod
    def de_json(cls, raw: str) -> "Documento":
        d = json.loads(raw)
        return cls(
            formato=d["formato"],
            paginas=[Pagina(p["n"], p["texto"], p.get("notas", "")) for p in d["paginas"]],
        )

    def para_prompt(self) -> str:
        """Texto do documento como o modelo o recebe: página a página, numerado, com a
        nota do apresentador marcada à parte."""
        blocos = []
        for p in self.paginas:
            corpo = p.texto.strip() or "[página sem texto legível]"
            rotulo = "TEXTO COLADO" if self.formato == "texto" else f"PÁGINA {p.numero}"
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


def detectar_formato(dados: bytes) -> str:
    if dados.startswith(b"%PDF-"):
        return "pdf"
    if dados[:4] == b"PK\x03\x04":
        try:
            nomes = set(zipfile.ZipFile(io.BytesIO(dados)).namelist())
        except zipfile.BadZipFile:
            raise DocumentoRecusado(f"Arquivo corrompido. Envie {FORMATOS_ACEITOS}.")
        if "ppt/presentation.xml" in nomes:
            return "pptx"
        if "word/document.xml" in nomes:
            raise DocumentoRecusado(
                f"Documento do Word ainda não é aceito. Envie {FORMATOS_ACEITOS} "
                "(no Word: Arquivo › Salvar como › PDF)."
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
                out.append(" | ".join(celulas))
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


def _extrair_pdf(dados: bytes) -> Documento:
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
    paginas: List[Pagina] = []
    for i, pg in enumerate(paginas_pdf, start=1):
        try:
            texto = pg.extract_text() or ""
        except Exception:  # noqa: BLE001 — página ilegível conta como sem texto, não derruba
            texto = ""
        paginas.append(Pagina(i, _nfc(texto)))
    return Documento("pdf", paginas)


def extrair(dados: bytes) -> Documento:
    """Detecta o formato e extrai. Levanta ``DocumentoRecusado`` com mensagem de tela."""
    if len(dados) > LIMITE_BYTES:
        raise DocumentoRecusado(
            f"Arquivo maior que {LIMITE_BYTES // (1024 * 1024)} MB. "
            "Reduza as imagens ou exporte como PDF."
        )
    formato = detectar_formato(dados)
    doc = _extrair_pptx(dados) if formato == "pptx" else _extrair_pdf(dados)
    if doc.n_paginas == 0:
        raise DocumentoRecusado("O documento não tem páginas.")
    if doc.n_paginas > LIMITE_PAGINAS:
        raise DocumentoRecusado(
            f"O documento tem {doc.n_paginas} páginas; o limite é {LIMITE_PAGINAS}."
        )
    if doc.total_caracteres > LIMITE_CARACTERES:
        raise DocumentoRecusado(
            f"O documento tem texto demais para uma leitura ({doc.total_caracteres:,} "
            f"caracteres; o limite é {LIMITE_CARACTERES:,}).".replace(",", ".")
        )
    if len(doc.paginas_sem_texto) == doc.n_paginas:
        raise DocumentoRecusado(
            "Nenhuma página tem texto legível — o documento parece ser só imagem. "
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


# ── conferência de citação ────────────────────────────────────────────────

_TROCAS = str.maketrans(
    {"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "–": "-", "—": "-", " ": " "}
)


def _normalizar(s: str) -> str:
    return re.sub(r"\s+", " ", _nfc(s).translate(_TROCAS)).strip()


def conferir_trecho(
    doc: Documento, pagina: Optional[int], trecho: str
) -> Tuple[bool, Optional[int]]:
    """O trecho citado existe LITERALMENTE no texto extraído?

    Normaliza só espaço, Unicode (NFC) e aspas/travessões tipográficos — nada de
    maiúscula/minúscula nem paráfrase. Procura primeiro na página citada, depois nas
    outras. Devolve ``(conferido, pagina_encontrada)``. Trecho curto demais nunca confere.
    """
    alvo = _normalizar(trecho)
    if len(alvo) < MIN_CARACTERES_TRECHO:
        return False, None
    ordem = sorted(doc.paginas, key=lambda p: 0 if p.numero == pagina else 1)
    for p in ordem:
        if alvo in _normalizar(p.texto) or alvo in _normalizar(p.notas):
            return True, p.numero
    return False, None
