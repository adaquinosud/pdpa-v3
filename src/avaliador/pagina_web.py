"""Entrada do Avaliador por endereço de página pública (decisão do Alexandre, 14/10).

Uma página por vez, nunca o site: busca o endereço, segue no máximo alguns redirecionamentos
e lê o HTML que chegou. Daí para frente é um ``Documento`` como o de um arquivo: cada
SEÇÃO (o trecho entre dois títulos) faz o papel da página, e a citação é conferida
literalmente contra o texto extraído.

Buscar endereço que o usuário digita é a porta clássica para o servidor ser usado contra
a rede dele mesmo (SSRF). Por isso, antes de cada conexão (inclusive a de cada
redirecionamento):
- só ``http``/``https``, só nas portas padrão, sem usuário/senha no endereço;
- o nome é resolvido e TODOS os IPs têm de ser públicos (``is_global``): nada de
  localhost, rede interna, link-local (o 169.254.169.254 dos metadados de nuvem) etc.;
- redirecionamento é seguido à mão, até ``MAX_REDIRECIONAMENTOS``, revalidando cada salto.
Risco que sobra, declarado: o nome pode ser re-resolvido entre a checagem e a conexão
(DNS rebinding). A janela é curta e a aba é só admin.

Sem cookie, sem credencial, só GET, tempo e tamanho limitados. Nada vai para disco.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import time
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlsplit

from src.avaliador.extracao import (
    LIMITE_CARACTERES,
    Documento,
    DocumentoRecusado,
    Pagina,
    _nfc,
)

MAX_REDIRECIONAMENTOS = 5
TEMPO_CONEXAO_S = 5
TEMPO_LEITURA_S = 10
TEMPO_TOTAL_S = 20
LIMITE_BYTES_HTML = 5 * 1024 * 1024
# Página com menos que isto de texto (depois de tirar menu, rodapé e script) = "não
# consegui ler": é página montada por script, tela de login ou bloqueio. Critério na tela.
MIN_CARACTERES_PAGINA_WEB = 300
PALAVRAS_REFERENCIA = 8
AGENTE = "PDPA-Avaliador/1.0 (leitura de uma página a pedido de um usuário da Loyall)"

SUGESTAO_PDF = (
    "Abra a página no navegador e salve como PDF (Imprimir › Salvar como PDF), "
    "depois envie o PDF."
)

_BLOCOS = {
    "p", "div", "section", "article", "main", "li", "ul", "ol", "dl", "dt", "dd",
    "blockquote", "pre", "table", "thead", "tbody", "tfoot", "tr", "td", "th",
    "figure", "figcaption", "address", "details", "summary", "hr", "br",
    "h1", "h2", "h3", "h4", "h5", "h6",
}  # fmt: skip
_TITULOS = {"h1", "h2", "h3", "h4", "h5", "h6"}
# título que tem um destes dentro é contêiner, não título (div solta dentro dele não conta)
_DENTRO_DE_TITULO_NAO = [
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "dl", "table", "blockquote", "pre",
]  # fmt: skip
_FORA = {
    "script", "style", "noscript", "template", "svg", "canvas", "iframe", "object",
    "embed", "nav", "footer", "form", "button", "select", "input", "textarea", "dialog",
}  # fmt: skip
_CLASSES_FORA = ("screen-reader", "sr-only", "visually-hidden", "skip-link", "cookie")
_PAPEIS_FORA = {"navigation", "contentinfo", "banner", "search", "dialog", "alertdialog"}


class PaginaRecusada(DocumentoRecusado):
    """Não deu para ler a página. A mensagem vai para a tela como está."""


# ── endereço e rede ───────────────────────────────────────────────────────


def normalizar_endereco(url: str) -> str:
    u = (url or "").strip()
    if not u:
        raise PaginaRecusada("Informe o endereço da página.")
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", u):
        u = "https://" + u
    return u


def _validar_destino(url: str) -> None:
    """Levanta se o endereço não é uma página pública buscável. Resolve o nome AGORA e
    exige que todos os IPs sejam públicos."""
    p = urlsplit(url)
    if p.scheme not in ("http", "https"):
        raise PaginaRecusada("Só endereços http ou https.")
    if p.username or p.password:
        raise PaginaRecusada("Endereço com usuário ou senha não é aceito.")
    if not p.hostname:
        raise PaginaRecusada("Endereço inválido.")
    try:
        porta = p.port
    except ValueError:
        raise PaginaRecusada("Endereço inválido.")
    if porta not in (None, 80, 443):
        raise PaginaRecusada("Só páginas nas portas padrão da web (80 e 443).")
    try:
        infos = socket.getaddrinfo(p.hostname, porta or (443 if p.scheme == "https" else 80))
    except (socket.gaierror, UnicodeError):
        raise PaginaRecusada(f"Não encontrei o endereço {p.hostname}. Confira se está certo.")
    ips = {info[4][0] for info in infos}
    for ip in ips:
        if not _ip_publico(ipaddress.ip_address(ip.split("%")[0])):
            raise PaginaRecusada(
                "Esse endereço aponta para uma rede interna, não para uma página pública."
            )


_NAT64 = ipaddress.ip_network("64:ff9b::/96")


def _ip_publico(end) -> bool:
    """Público de verdade, inclusive o IPv4 escondido dentro de um IPv6 (mapeado, 6to4,
    Teredo, NAT64): ``is_global`` sozinho aceita 64:ff9b::a00:1, que é o 10.0.0.1."""
    if not end.is_global or end.is_multicast:
        return False
    if end.version == 6:
        dentro = [end.ipv4_mapped, end.sixtofour, end.teredo[1] if end.teredo else None]
        if end in _NAT64:
            dentro.append(ipaddress.IPv4Address(int(end) & 0xFFFFFFFF))
        return all(_ip_publico(v4) for v4 in dentro if v4 is not None)
    return True


def buscar(url: str, sessao=None) -> Tuple[str, bytes]:
    """Busca UMA página pública. Devolve ``(endereco_lido, html)``. Levanta
    ``PaginaRecusada`` com a mensagem de tela em todo caso que não dá HTML legível."""
    import requests

    sessao = sessao or requests.Session()
    inicio = time.monotonic()
    atual = normalizar_endereco(url)
    for _ in range(MAX_REDIRECIONAMENTOS + 1):
        _validar_destino(atual)
        if time.monotonic() - inicio > TEMPO_TOTAL_S:
            raise PaginaRecusada("A página demorou demais para responder. " + SUGESTAO_PDF)
        try:
            resp = sessao.get(
                atual,
                allow_redirects=False,
                stream=True,
                timeout=(TEMPO_CONEXAO_S, TEMPO_LEITURA_S),
                headers={"User-Agent": AGENTE, "Accept": "text/html,application/xhtml+xml"},
            )
        except requests.exceptions.Timeout:
            raise PaginaRecusada("A página demorou demais para responder. " + SUGESTAO_PDF)
        except requests.exceptions.RequestException:
            raise PaginaRecusada("Não consegui acessar a página. " + SUGESTAO_PDF)
        try:
            if resp.status_code in (301, 302, 303, 307, 308):
                destino = resp.headers.get("Location")
                if not destino:
                    raise PaginaRecusada("A página redirecionou para lugar nenhum.")
                atual = urljoin(atual, destino)
                continue
            _checar_resposta(resp)
            return atual, _ler_limitado(resp, inicio)
        finally:
            resp.close()
    raise PaginaRecusada("A página redireciona demais. Envie o endereço final da página.")


def _checar_resposta(resp) -> None:
    c = resp.status_code
    if c in (401, 403, 407):
        raise PaginaRecusada("A página pede senha ou bloqueia leitura automática. " + SUGESTAO_PDF)
    if c == 404 or c == 410:
        raise PaginaRecusada("A página não existe (erro 404). Confira o endereço.")
    if c == 429:
        raise PaginaRecusada("O site recusou a leitura agora (muitas visitas). " + SUGESTAO_PDF)
    if c >= 400:
        raise PaginaRecusada(f"O site respondeu com erro ({c}). " + SUGESTAO_PDF)
    tipo = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if tipo == "application/pdf":
        raise PaginaRecusada("Esse endereço é um PDF. Baixe o arquivo e envie como PDF.")
    if tipo and tipo not in ("text/html", "application/xhtml+xml"):
        raise PaginaRecusada(f"Esse endereço não é uma página de texto ({tipo}).")


def _ler_limitado(resp, inicio: float) -> bytes:
    partes: List[bytes] = []
    total = 0
    for parte in resp.iter_content(64 * 1024):
        total += len(parte)
        if total > LIMITE_BYTES_HTML:
            raise PaginaRecusada("A página é grande demais para uma leitura. " + SUGESTAO_PDF)
        if time.monotonic() - inicio > TEMPO_TOTAL_S:
            raise PaginaRecusada("A página demorou demais para responder. " + SUGESTAO_PDF)
        partes.append(parte)
    return b"".join(partes)


# ── HTML → seções ─────────────────────────────────────────────────────────


def _espacos(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _fora(tag) -> bool:
    if tag.name in _FORA:
        return True
    if (tag.get("role") or "").lower() in _PAPEIS_FORA:
        return True
    if tag.has_attr("hidden") or (tag.get("aria-hidden") or "").lower() == "true":
        return True
    # texto só para leitor de tela ("Skip to content", "Pular para o conteúdo")
    classes = " ".join(tag.get("class") or []).lower()
    if any(c in classes for c in _CLASSES_FORA):
        return True
    # cabeçalho do site (logo + menu) sai; cabeçalho de artigo (só o título) fica
    if tag.name == "header" and tag.find("nav") is not None:
        return True
    return False


def extrair_html(html: bytes, endereco: str) -> Documento:
    """Tira menu, rodapé, script e formulário e devolve uma seção por título (h1-h6).
    O que vem antes do primeiro título é a seção de abertura (sem título)."""
    from bs4 import BeautifulSoup, NavigableString, Tag
    from bs4.element import Comment

    sopa = BeautifulSoup(html, "lxml")
    for t in [t for t in sopa.find_all(True) if _fora(t)]:
        if not t.decomposed:
            t.decompose()
    raiz = sopa.find("main") or sopa.body or sopa

    secoes: List[Tuple[str, List[str]]] = [("", [])]
    linha: List[str] = []

    def fechar_linha():
        texto = _espacos("".join(linha))
        linha.clear()
        if texto:
            secoes[-1][1].append(texto)

    def texto_titulo(tag) -> str:
        # quebra de linha e bloco dentro do título viram espaço ("Uma metodologia<br>sem
        # sistema" não pode virar "metodologiasem"); inline continua colado ("<em>")
        partes: List[str] = []
        for d in tag.descendants:
            if isinstance(d, NavigableString) and not isinstance(d, Comment):
                partes.append(str(d))
            elif isinstance(d, Tag) and d.name in _BLOCOS:
                partes.append(" ")
        return _espacos("".join(partes))

    def andar(no):
        for filho in no.children:
            if isinstance(filho, Comment):
                continue
            if isinstance(filho, NavigableString):
                linha.append(str(filho))
                continue
            if not isinstance(filho, Tag):
                continue
            if filho.name in _TITULOS and filho.find(_DENTRO_DE_TITULO_NAO) is not None:
                # construtor de site (Elementor) embrulha bloco inteiro num título: é
                # contêiner, não título; o título de verdade, se houver, está dentro
                fechar_linha()
                andar(filho)
                fechar_linha()
                continue
            if filho.name in _TITULOS:
                fechar_linha()
                t = texto_titulo(filho)
                if t:
                    secoes.append((t, [t]))
                continue
            bloco = filho.name in _BLOCOS
            if bloco:
                fechar_linha()
            andar(filho)
            if bloco:
                fechar_linha()

    andar(raiz)
    fechar_linha()

    paginas: List[Pagina] = []
    for titulo, paragrafos in secoes:
        if not paragrafos:
            continue
        paginas.append(Pagina(len(paginas) + 1, _nfc("\n".join(paragrafos)), titulo=_nfc(titulo)))
    doc = Documento("web", paginas)
    total = sum(len(re.sub(r"\s", "", p.texto)) for p in paginas)
    if total < MIN_CARACTERES_PAGINA_WEB:
        raise PaginaRecusada(
            f"Não consegui ler o texto desta página (menos de {MIN_CARACTERES_PAGINA_WEB} "
            "caracteres depois de tirar menu e rodapé). Isso acontece quando a página é "
            "montada por script ou pede login. " + SUGESTAO_PDF
        )
    if doc.total_caracteres > LIMITE_CARACTERES:
        raise PaginaRecusada(
            f"A página tem texto demais para uma leitura ({doc.total_caracteres:,} "
            f"caracteres; o limite é {LIMITE_CARACTERES:,}).".replace(",", ".")
        )
    return doc


def referencia(doc: Documento, numero: Optional[int], trecho: str) -> str:
    """Onde o usuário acha o trecho numa página da web: o título da seção; sem título
    (a abertura da página), as primeiras palavras do parágrafo onde o trecho está."""
    from src.avaliador.extracao import _normalizar

    pag = next((p for p in doc.paginas if p.numero == numero), None)
    if pag is None:
        return ""
    if pag.titulo:
        return f"seção “{pag.titulo}”"
    alvo = _normalizar(trecho)
    paragrafos = pag.texto.split("\n")
    achado = next((x for x in paragrafos if alvo and alvo in _normalizar(x)), paragrafos[0])
    palavras = achado.split()
    inicio = " ".join(palavras[:PALAVRAS_REFERENCIA])
    reticencias = "…" if len(palavras) > PALAVRAS_REFERENCIA else ""
    return f"parágrafo que começa “{inicio}{reticencias}”"
