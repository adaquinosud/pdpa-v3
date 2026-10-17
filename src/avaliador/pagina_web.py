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
from typing import List, Tuple
from urllib.parse import urljoin, urlsplit

from src.avaliador.extracao import (
    LIMITE_CARACTERES,
    Documento,
    DocumentoRecusado,
    RODAPE,
    Pagina,
    _nfc,
)

MAX_REDIRECIONAMENTOS = 5
TEMPO_CONEXAO_S = 5
TEMPO_LEITURA_S = 10
TEMPO_TOTAL_S = 20
LIMITE_BYTES_HTML = 5 * 1024 * 1024
# Página com menos que isto de texto (depois de tirar menu e script) = "não
# consegui ler": é página montada por script, tela de login ou bloqueio. Critério na tela.
MIN_CARACTERES_PAGINA_WEB = 300
# O app se apresenta como é, nunca como navegador: quem usa a ferramenta nem sempre é o dono
# do site, e passar por cima da regra de bloqueio faria dela raspador de página (decisão do
# Alexandre, 15/10). O endereço é para o administrador do site saber quem é.
AGENTE = "PDPA-Avaliador/1.0 (+https://loyallcompany.com.br)"

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
    "embed", "nav", "form", "button", "select", "input", "textarea", "dialog",
}  # fmt: skip
# O rodapé do site ENTRA (17/10, exceção deliberada ao "extração fica como está"): é onde
# moram telefone e e-mail em quase todo site, e é o que o D1 pergunta. Medido no site da
# leitura de 17/10: sem o rodapé o D1 saiu "Não" e a página tinha e-mail e dois celulares
# no rodapé; o rodapé somou +147 caracteres ali e +182 noutro site (cerca de 10%).
# Vai numa seção própria, no fim (RODAPE), com o menu e o formulário de dentro dele fora.
_PAPEIS_RODAPE = {"contentinfo"}
_CLASSES_FORA = ("screen-reader", "sr-only", "visually-hidden", "skip-link", "cookie")
_PAPEIS_FORA = {"navigation", "banner", "search", "dialog", "alertdialog"}


class PaginaRecusada(DocumentoRecusado):
    """Não deu para ler a página. A mensagem vai para a tela como está."""


# Várias páginas como uma peça só (17/10): quem escolhe as páginas é o usuário; o app não
# segue link nenhum sozinho.
MAX_PAGINAS_WEB = 10


def enderecos_enviados(texto: str) -> List[str]:
    """Os endereços do campo, um por linha (ou separados por espaço), sem repetir."""
    out: List[str] = []
    for e in re.split(r"\s+", texto or ""):
        if e and e not in out:
            out.append(e)
    return out


def juntar(lidas: List[Tuple[str, Documento]]) -> Documento:
    """As páginas lidas, uma depois da outra, numa peça só: cada seção sabe de qual
    endereço veio, a numeração continua, e o rodapé que se repete igual em todas as
    páginas entra uma vez só (senão a mesma linha de contato pesaria cinco vezes)."""
    if len(lidas) == 1:
        return lidas[0][1]
    corpo: List[Tuple[str, Pagina]] = []
    rodapes: List[Tuple[str, Pagina]] = []  # no fim, como numa página só; o igual, uma vez
    for endereco, doc in lidas:
        for p in doc.paginas:
            if p.titulo != RODAPE:
                corpo.append((endereco, p))
            elif all(p.texto != r.texto for _, r in rodapes):
                rodapes.append((endereco, p))
    paginas = [
        Pagina(n, p.texto, p.notas, p.titulo, endereco)
        for n, (endereco, p) in enumerate(corpo + rodapes, start=1)
    ]
    doc = Documento("web", paginas)
    if doc.total_caracteres > LIMITE_CARACTERES:
        raise PaginaRecusada(
            f"As páginas juntas têm texto demais para uma leitura ({doc.total_caracteres:,} "
            f"caracteres; o limite é {LIMITE_CARACTERES:,}). Envie menos páginas.".replace(",", ".")
        )
    return doc


def ler_paginas(texto: str, sessao=None) -> Tuple[List[str], bytes, Documento]:
    """Busca e extrai cada endereço do campo e junta numa peça só. Devolve os endereços
    LIDOS (depois de redirecionamento), os bytes juntos (para o hash) e o documento. Uma
    página que não pode ser lida recusa o pedido inteiro, dizendo qual foi."""
    enderecos = enderecos_enviados(texto)
    if len(enderecos) > MAX_PAGINAS_WEB:
        raise PaginaRecusada(
            f"Até {MAX_PAGINAS_WEB} páginas por leitura; vieram {len(enderecos)}. "
            "Escolha as que importam para esta peça."
        )
    lidas: List[Tuple[str, Documento]] = []
    brutos: List[bytes] = []
    for e in enderecos:
        try:
            lido, html = buscar(e, sessao=sessao)
            doc = extrair_html(html, lido)
        except PaginaRecusada as err:
            if len(enderecos) == 1:
                raise
            raise PaginaRecusada(
                f"Na página {e}: {err} Para seguir com as outras, tire esta página da lista "
                "ou corrija o endereço. Nada foi lido nem cobrado."
            ) from None
        lidas.append((lido, doc))
        brutos.append(html)
    return [lido for lido, _ in lidas], b"\n".join(brutos), juntar(lidas)


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
    if c in (401, 407):
        raise PaginaRecusada(
            "A página pede senha. Abra no navegador, salve como PDF (Imprimir, depois Salvar "
            "como PDF) e envie o PDF."
        )
    if c == 403:  # grupocarbel.com.br, 15/10: o balanceador recusa quem não é navegador
        raise PaginaRecusada(
            "O site recusa leitura automática. Abra a página no navegador, salve como PDF "
            "(Imprimir, depois Salvar como PDF) e envie o PDF. Funciona porque o site libera "
            "quem abre pelo navegador."
        )
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


# Área de uso privado do Unicode: é onde fonte de ícone (Font Awesome, Elementor) põe o
# desenho do envelope, do telefone etc. Não é texto: medido em 17/10, chegava ao pedido
# como caractere solto ("\uf0e0") no rodapé de um site.
_USO_PRIVADO = re.compile("[\ue000-\uf8ff]")


def _espacos(s: str) -> str:
    return re.sub(r"\s+", " ", _USO_PRIVADO.sub("", s or "")).strip()


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
    """Tira menu, script e formulário e devolve uma seção por título (h1-h6). O que vem
    antes do primeiro título é a seção de abertura (sem título); o rodapé do site vem por
    último, numa seção própria (RODAPE)."""
    from bs4 import BeautifulSoup, NavigableString, Tag
    from bs4.element import Comment

    sopa = BeautifulSoup(html, "lxml")
    for t in [t for t in sopa.find_all(True) if _fora(t)]:
        if not t.decomposed:
            t.decompose()
    # rodapé do site: o de fora de outro rodapé e de fora de artigo (rodapé de artigo, com
    # autor e data, fica onde está). Sai da árvore e é lido por último.
    rodapes = [
        t.extract()
        for t in sopa.find_all(
            lambda t: t.name == "footer" or (t.get("role") or "").lower() in _PAPEIS_RODAPE
        )
        if not t.find_parent("footer")
        and not t.find_parent(attrs={"role": "contentinfo"})
        and not t.find_parent("article")
    ]
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

    def andar(no, titulos=True):
        """``titulos=False`` (rodapé): título vira parágrafo, para o rodapé inteiro ficar
        numa seção só ("E-mail", "Telefone" no rodapé não são seções da página)."""
        for filho in no.children:
            if isinstance(filho, Comment):
                continue
            if isinstance(filho, NavigableString):
                linha.append(str(filho))
                continue
            if not isinstance(filho, Tag):
                continue
            if filho.name in _TITULOS and not titulos:
                fechar_linha()
                t = texto_titulo(filho)
                if t:
                    secoes[-1][1].append(t)
                continue
            if filho.name in _TITULOS and filho.find(_DENTRO_DE_TITULO_NAO) is not None:
                # construtor de site (Elementor) embrulha bloco inteiro num título: é
                # contêiner, não título; o título de verdade, se houver, está dentro
                fechar_linha()
                andar(filho, titulos)
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
            andar(filho, titulos)
            if bloco:
                fechar_linha()

    andar(raiz)
    fechar_linha()
    for r in rodapes:
        secoes.append((RODAPE, []))
        andar(r, titulos=False)
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
            "caracteres depois de tirar menu e script). Isso acontece quando a página é "
            "montada por script ou pede login. " + SUGESTAO_PDF
        )
    if doc.total_caracteres > LIMITE_CARACTERES:
        raise PaginaRecusada(
            f"A página tem texto demais para uma leitura ({doc.total_caracteres:,} "
            f"caracteres; o limite é {LIMITE_CARACTERES:,}).".replace(",", ".")
        )
    return doc
