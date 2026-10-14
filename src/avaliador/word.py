"""Leitura de documento do Word (.docx) para o Avaliador, por seção.

Decisões do Alexandre (14/10):
- Entra o texto do corpo e as tabelas. Cabeçalho, rodapé e comentários de margem ficam de
  fora (são outras partes do arquivo, que não são abertas). Nota de rodapé também.
- Controle de alterações: vale o texto como está. O que foi riscado (``w:del``) e o que
  foi movido daqui para outro lugar (``w:moveFrom``) NÃO entram; o inserido entra. Ler
  texto que o autor já tirou e apontar buraco em cima dele é o pior erro possível.
- Citação sem página: um parágrafo de título (estilo Título/Heading ou nível de tópico)
  abre uma seção; o que vem antes do primeiro título é a abertura do documento.

O XML é lido direto (lxml, sem rede, sem entidade externa), pelo nome local das tags, o
que cobre também o .docx "estrito". Texto oculto (``w:vanish``) não entra, como o oculto
da página da web. O sumário automático (estilo "toc N") não entra: repete os títulos com
número de página. Numeração automática de lista e de cláusula não aparece no texto (o
Word a desenha na hora; não está no XML do parágrafo).
"""

from __future__ import annotations

import io
import re
import zipfile
from typing import Dict, Iterator, List, Optional, Tuple

from src.avaliador.extracao import (
    SEPARADOR_CELULA,
    Documento,
    DocumentoRecusado,
    Pagina,
    _nfc,
)

# Teto do XML descompactado: um .docx de 60 MB de imagens tem document.xml pequeno; XML
# acima disto é arquivo fabricado para estourar memória (zip bomb), não peça comercial.
LIMITE_XML_BYTES = 50 * 1024 * 1024

# Parágrafo curto, todo em MAIÚSCULAS e sem ponto final = título, mesmo sem estilo de título
# (decisão de 14/10: 22 de 65 .docx locais não usam estilo; "PRAZO", "INVESTIMENTO" na
# proposta da casa). Acima disto de caracteres é frase em maiúsculas, não título.
MAX_CARACTERES_TITULO_MAIUSCULAS = 60

_FORA_DA_LEITURA = {"del", "moveFrom", "Fallback", "instrText", "delText", "pPr", "rPr"}
_ESTILO_TITULO = re.compile(r"^(heading|t[ií]tulo|title)( ?\d)?$", re.IGNORECASE)
_ESTILO_SUMARIO = re.compile(r"^(toc|sum[aá]rio) ?\d", re.IGNORECASE)


def _local(el) -> str:
    tag = el.tag
    if not isinstance(tag, str):  # comentário/processamento do XML
        return ""
    return tag.rsplit("}", 1)[-1]


def _attr(el, nome: str) -> Optional[str]:
    for k, v in el.attrib.items():
        if k.rsplit("}", 1)[-1] == nome:
            return v
    return None


def _filho(el, nome: str):
    for c in el:
        if _local(c) == nome:
            return c
    return None


def _xml(z: zipfile.ZipFile, nome: str):
    from lxml import etree

    try:
        info = z.getinfo(nome)
    except KeyError:
        return None
    if info.file_size > LIMITE_XML_BYTES:
        raise DocumentoRecusado("O documento do Word é grande demais para ler.")
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    return etree.fromstring(z.read(nome), parser)


class _Estilos:
    """styleId → é título? é sumário? Segue a cadeia ``basedOn`` (estilo próprio
    "Título da proposta" baseado em "Heading 1" é título)."""

    def __init__(self, raiz):
        self._nome: Dict[str, str] = {}
        self._base: Dict[str, str] = {}
        self._nivel: Dict[str, int] = {}
        if raiz is None:
            return
        for s in raiz:
            if _local(s) != "style":
                continue
            sid = _attr(s, "styleId") or ""
            nome = _filho(s, "name")
            self._nome[sid] = (_attr(nome, "val") or "") if nome is not None else ""
            base = _filho(s, "basedOn")
            if base is not None:
                self._base[sid] = _attr(base, "val") or ""
            ppr = _filho(s, "pPr")
            nivel = _filho(ppr, "outlineLvl") if ppr is not None else None
            if nivel is not None:
                self._nivel[sid] = int(_attr(nivel, "val") or 9)

    def _cadeia(self, sid: str) -> Iterator[str]:
        vistos = set()
        while sid and sid not in vistos:
            vistos.add(sid)
            yield sid
            sid = self._base.get(sid, "")

    def titulo(self, sid: str) -> bool:
        for s in self._cadeia(sid):
            if _ESTILO_TITULO.match(self._nome.get(s, "").strip()):
                return True
            if self._nivel.get(s, 9) < 9:
                return True
        return False

    def sumario(self, sid: str) -> bool:
        return bool(_ESTILO_SUMARIO.match(self._nome.get(sid, "").strip()))


def _titulo_em_maiusculas(texto: str) -> bool:
    return (
        len(texto) <= MAX_CARACTERES_TITULO_MAIUSCULAS
        and texto == texto.upper()
        and any(c.isalpha() for c in texto)
        and not texto.endswith(".")
    )


def _oculto(run) -> bool:
    rpr = _filho(run, "rPr")
    v = _filho(rpr, "vanish") if rpr is not None else None
    return v is not None and (_attr(v, "val") or "true").lower() not in ("0", "false", "off")


def _texto_paragrafo(p) -> Tuple[str, List]:
    """Texto visível do parágrafo como está (sem riscado, sem oculto) e as caixas de
    texto que ele carrega (lidas depois, como blocos próprios)."""
    partes: List[str] = []
    caixas: List = []

    def andar(el):
        for c in el:
            nome = _local(c)
            if not nome or nome in _FORA_DA_LEITURA:
                continue
            if nome == "txbxContent":
                caixas.append(c)
                continue
            if nome == "r" and _oculto(c):
                continue
            if nome == "t":
                partes.append(c.text or "")
            elif nome in ("tab", "br", "cr"):
                partes.append(" ")
            elif nome == "noBreakHyphen":
                partes.append("-")
            else:
                andar(c)

    andar(p)
    return re.sub(r"\s+", " ", "".join(partes)).strip(), caixas


def _blocos(el, estilos: _Estilos) -> Iterator[Tuple[str, str]]:
    """("titulo"|"rotulo"|"texto", linha) na ordem do documento."""
    for c in el:
        nome = _local(c)
        if nome == "p":
            ppr = _filho(c, "pPr")
            sid = ""
            nivel = 9
            if ppr is not None:
                ps = _filho(ppr, "pStyle")
                sid = (_attr(ps, "val") or "") if ps is not None else ""
                ol = _filho(ppr, "outlineLvl")
                if ol is not None:
                    nivel = int(_attr(ol, "val") or 9)
            texto, caixas = _texto_paragrafo(c)
            if texto and not estilos.sumario(sid):
                if nivel < 9 or estilos.titulo(sid):
                    tipo = "titulo"
                elif _titulo_em_maiusculas(texto):
                    tipo = "rotulo"  # título sem estilo, pelas maiúsculas
                else:
                    tipo = "texto"
                yield tipo, texto
            for cx in caixas:
                yield from _blocos(cx, estilos)
        elif nome == "tbl":
            yield from _tabela(c, estilos)
        elif nome in _FORA_DA_LEITURA or not nome:
            continue
        else:  # sdt, sdtContent, customXml, ins, moveTo, AlternateContent, Choice...
            yield from _blocos(c, estilos)


def _celula(tc, estilos: _Estilos) -> str:
    return " ".join(t for _, t in _blocos(tc, estilos))


def _linhas(tbl) -> Iterator:
    for c in tbl:
        nome = _local(c)
        if nome == "tr":
            yield c
        elif nome not in _FORA_DA_LEITURA and nome not in ("tblPr", "tblGrid"):
            yield from _linhas(c)  # linha dentro de sdt/ins


def _tabela(tbl, estilos: _Estilos) -> Iterator[Tuple[str, str]]:
    """Uma linha de tabela = uma linha de texto, células separadas por SEPARADOR_CELULA
    (o mesmo formato da tabela do PowerPoint)."""
    for tr in _linhas(tbl):
        celulas = []
        for tc in tr:
            if _local(tc) == "tc":
                t = _celula(tc, estilos)
                if t:
                    celulas.append(t)
            elif _local(tc) == "sdt":
                for sub in tc.iter():
                    if _local(sub) == "tc":
                        t = _celula(sub, estilos)
                        if t:
                            celulas.append(t)
        if celulas:
            yield "texto", SEPARADOR_CELULA.join(celulas)


def extrair_docx(dados: bytes) -> Documento:
    try:
        z = zipfile.ZipFile(io.BytesIO(dados))
        corpo_xml = _xml(z, "word/document.xml")
        estilos = _Estilos(_xml(z, "word/styles.xml"))
    except DocumentoRecusado:
        raise
    except Exception:  # noqa: BLE001 — XML quebrado = arquivo ilegível
        raise DocumentoRecusado(
            "Não consegui abrir este documento do Word. Abra no Word, salve de novo como "
            ".docx e envie, ou exporte como PDF."
        )
    corpo = _filho(corpo_xml, "body") if corpo_xml is not None else None
    if corpo is None:
        raise DocumentoRecusado(
            "Não achei o texto deste documento do Word. Abra no Word, salve de novo como "
            ".docx e envie, ou exporte como PDF."
        )
    secoes: List[Tuple[str, List[str]]] = [("", [])]
    rotulo_sozinho = False
    for tipo, linha in _blocos(corpo, estilos):
        if tipo in ("titulo", "rotulo"):
            if rotulo_sozinho:
                # "SEÇÃO 3" em maiúsculas logo antes do título de verdade: uma seção só,
                # "SEÇÃO 3 · Título", e não uma seção vazia com o rótulo
                titulo, linhas = secoes.pop()
                secoes.append((f"{titulo} · {linha}", linhas + [linha]))
            else:
                secoes.append((linha, [linha]))
            rotulo_sozinho = tipo == "rotulo"
        else:
            secoes[-1][1].append(linha)
            rotulo_sozinho = False
    paginas: List[Pagina] = []
    for titulo, linhas in secoes:
        if linhas:
            paginas.append(Pagina(len(paginas) + 1, _nfc("\n".join(linhas)), titulo=_nfc(titulo)))
    if not paginas:
        raise DocumentoRecusado(
            "O documento não tem texto para ler: está vazio, ou o conteúdo é só imagem. "
            "A leitura de imagem ainda não existe."
        )
    return Documento("docx", paginas)
