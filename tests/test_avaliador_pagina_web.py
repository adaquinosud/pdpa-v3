"""Entrada por endereço de página: guarda de rede (SSRF), busca com sessão HTTP DUBLADA
(nenhuma conexão real), extração do HTML por seção e referência da citação."""

from __future__ import annotations

import socket

import pytest

from src.avaliador import pagina_web
from src.avaliador.extracao import conferir_trecho
from src.avaliador.pagina_web import PaginaRecusada, buscar, extrair_html, referencia

PARAGRAFO = (
    "Atendemos empresas de todos os portes com equipes dedicadas em cada região, e o "
    "gerente da sua conta responde em até quatro horas úteis por telefone ou e-mail."
)
PARAGRAFO2 = (
    "Fora das capitais, o prazo depende da transportadora contratada e é informado no "
    "pedido, junto com o código de rastreio e o telefone de quem acompanha a entrega."
)
HTML = f"""<html><head><title>Loja Exemplo</title><script>var x = "SCRIPT-FORA";</script>
<style>.a{{color:red}}</style></head><body>
<a class="skip-link screen-reader-text" href="#c">PULAR-FORA</a>
<header><a href="/">Logo</a><nav><a href="/a">MENU-FORA</a></nav></header>
<div class="cookie-banner">COOKIE-FORA aceite</div>
<main>
<p>Bem-vindo à <strong>Loja Exemplo</strong>, parceira de quem <a href="/x">compra bem</a>.</p>
<h2>Como atendemos</h2>
<p>{PARAGRAFO}</p>
<div hidden>OCULTO-FORA</div>
<h2>Prazos</h2><ul><li>Entrega em até 48 horas nas capitais.</li>
<li>Troca sem custo em 30 dias.</li></ul>
<p>{PARAGRAFO2}</p>
<form><input value="FORM-FORA"><button>Enviar</button></form>
</main>
<footer>RODAPE-FORA Todos os direitos reservados</footer></body></html>"""


# ── extração ───────────────────────────────────────────────────────────────


def test_extrai_por_secao_sem_menu_rodape_script_nem_formulario():
    doc = extrair_html(HTML.encode(), "https://exemplo.com.br/")
    tudo = doc.para_prompt()
    for fora in (
        "SCRIPT-FORA", "MENU-FORA", "RODAPE-FORA", "OCULTO-FORA", "FORM-FORA", "Logo",
        "PULAR-FORA", "COOKIE-FORA",
    ):  # fmt: skip
        assert fora not in tudo, fora
    assert doc.formato == "web" and [p.titulo for p in doc.paginas] == [
        "",
        "Como atendemos",
        "Prazos",
    ]
    assert "=== SEÇÃO 1: abertura da página ===" in tudo
    assert "=== SEÇÃO 2: Como atendemos ===" in tudo
    # link e negrito no meio da frase não quebram a frase (a citação literal casa)
    assert "Bem-vindo à Loja Exemplo, parceira de quem compra bem." in doc.paginas[0].texto
    assert doc.paginas_sem_texto == []  # seção curta não é "página sem texto"


def test_pagina_montada_por_script_nao_vira_leitura_vazia():
    html = b"<html><body><div id='app'></div><noscript>Ative o JavaScript</noscript>"
    html += b"<script>render()</script></body></html>"
    with pytest.raises(PaginaRecusada, match="montada por script ou pede login.*PDF"):
        extrair_html(html, "https://spa.exemplo.com/")


def test_pagina_de_texto_demais_e_recusada(monkeypatch):
    monkeypatch.setattr(pagina_web, "LIMITE_CARACTERES", 200)
    with pytest.raises(PaginaRecusada, match="texto demais"):
        extrair_html(HTML.encode(), "https://exemplo.com.br/")


def test_referencia_e_titulo_da_secao_ou_comeco_do_paragrafo():
    doc = extrair_html(HTML.encode(), "https://exemplo.com.br/")
    ok, n = conferir_trecho(doc, None, "responde em até quatro horas úteis")
    assert ok and referencia(doc, n, "responde em até quatro horas úteis") == (
        "seção “Como atendemos”"
    )
    ok, n = conferir_trecho(doc, None, "parceira de quem compra bem")
    assert ok and n == 1
    assert referencia(doc, n, "parceira de quem compra bem") == (
        "parágrafo que começa “Bem-vindo à Loja Exemplo, parceira de quem compra…”"
    )


def test_motor_poe_a_referencia_na_citacao_conferida():
    from src.avaliador.motor import validar_saida

    doc = extrair_html(HTML.encode(), "https://exemplo.com.br/")
    res = validar_saida(
        doc,
        {
            "resumo": "r",
            "itens": [
                {
                    "subpilar": "D1",
                    "tipo": "forte",
                    "texto": "Prazo de resposta declarado.",
                    "evidencias": [
                        {"pagina": 9, "trecho": "responde em até quatro horas úteis"},
                        {"pagina": 2, "trecho": "TRECHO QUE NÃO EXISTE NA PÁGINA"},
                    ],
                }
            ],
        },
    )
    ev = res["itens"][0]["evidencias"]
    assert ev[0]["conferido"] and ev[0]["referencia"] == "seção “Como atendemos”"
    assert not ev[1]["conferido"] and "referencia" not in ev[1]


# ── guarda de rede ─────────────────────────────────────────────────────────


def _resolve_para(monkeypatch, *ips):
    def fake(host, porta, *a, **k):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, porta)) for ip in ips]

    monkeypatch.setattr(pagina_web.socket, "getaddrinfo", fake)


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1", "10.0.0.5", "192.168.1.10", "172.16.0.1", "169.254.169.254", "::1",
        "0.0.0.0", "100.64.0.1", "::ffff:10.0.0.1", "64:ff9b::a00:1", "64:ff9b::a9fe:a9fe",
    ],  # fmt: skip
)
def test_endereco_que_resolve_para_rede_interna_e_recusado(monkeypatch, ip):
    _resolve_para(monkeypatch, ip)
    with pytest.raises(PaginaRecusada, match="rede interna"):
        pagina_web._validar_destino("https://parece-publico.com/")


def test_um_ip_interno_entre_varios_basta_para_recusar(monkeypatch):
    _resolve_para(monkeypatch, "93.184.216.34", "10.1.2.3")
    with pytest.raises(PaginaRecusada, match="rede interna"):
        pagina_web._validar_destino("https://misto.com/")


@pytest.mark.parametrize(
    "url, msg",
    [
        ("ftp://exemplo.com/x", "http ou https"),
        ("file:///etc/passwd", "http ou https"),
        ("https://usuario:senha@exemplo.com/", "usuário ou senha"),
        ("https://exemplo.com:8080/", "portas padrão"),
    ],
)
def test_esquema_porta_e_credencial_sao_recusados(monkeypatch, url, msg):
    _resolve_para(monkeypatch, "93.184.216.34")
    with pytest.raises(PaginaRecusada, match=msg):
        pagina_web._validar_destino(url)


def test_endereco_sem_esquema_vira_https():
    assert pagina_web.normalizar_endereco(" exemplo.com.br/a ") == "https://exemplo.com.br/a"


# ── busca (sessão HTTP dublada) ────────────────────────────────────────────


class Resp:
    def __init__(self, status=200, corpo=b"", headers=None):
        self.status_code = status
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        self._corpo = corpo
        self.fechada = False

    def iter_content(self, n):
        for i in range(0, len(self._corpo), n):
            yield self._corpo[i : i + n]  # noqa: E203

    def close(self):
        self.fechada = True


class Sessao:
    def __init__(self, respostas):
        self.respostas = dict(respostas)
        self.pedidos = []

    def get(self, url, **kw):
        self.pedidos.append((url, kw))
        return self.respostas[url]


@pytest.fixture
def publico(monkeypatch):
    _resolve_para(monkeypatch, "93.184.216.34")


def test_busca_segue_redirecionamento_e_diz_qual_endereco_leu(publico):
    s = Sessao(
        {
            "https://exemplo.com.br": Resp(301, headers={"Location": "/inicio"}),
            "https://exemplo.com.br/inicio": Resp(200, HTML.encode()),
        }
    )
    lido, html = buscar("exemplo.com.br", sessao=s)
    assert lido == "https://exemplo.com.br/inicio" and html == HTML.encode()
    _, kw = s.pedidos[0]
    assert kw["allow_redirects"] is False and kw["timeout"] == (5, 10)
    assert "Cookie" not in kw["headers"] and "Authorization" not in kw["headers"]


def test_redirecionamento_para_rede_interna_e_barrado(monkeypatch):
    def fake(host, porta, *a, **k):
        ip = "10.0.0.9" if host == "interno.exemplo" else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, porta))]

    monkeypatch.setattr(pagina_web.socket, "getaddrinfo", fake)
    s = Sessao({"https://exemplo.com/": Resp(302, headers={"Location": "http://interno.exemplo/"})})
    with pytest.raises(PaginaRecusada, match="rede interna"):
        buscar("https://exemplo.com/", sessao=s)
    assert len(s.pedidos) == 1  # o salto interno nunca foi pedido


def test_redirecionamento_em_circulo_para(publico):
    s = Sessao({"https://a.com/": Resp(302, headers={"Location": "https://a.com/"})})
    with pytest.raises(PaginaRecusada, match="redireciona demais"):
        buscar("https://a.com/", sessao=s)
    assert len(s.pedidos) == pagina_web.MAX_REDIRECIONAMENTOS + 1


@pytest.mark.parametrize(
    "resp, msg",
    [
        (Resp(403), "pede senha ou bloqueia leitura automática.*salve como PDF"),
        (Resp(401), "pede senha"),
        (Resp(404), "não existe"),
        (Resp(500), "erro \\(500\\)"),
        (Resp(200, b"%PDF-1.4", {"Content-Type": "application/pdf"}), "é um PDF"),
        (Resp(200, b"x", {"Content-Type": "image/png"}), "não é uma página de texto"),
    ],
)
def test_pagina_que_nao_pode_ser_lida_diz_por_que(publico, resp, msg):
    with pytest.raises(PaginaRecusada, match=msg):
        buscar("https://exemplo.com/", sessao=Sessao({"https://exemplo.com/": resp}))
    assert resp.fechada


def test_pagina_grande_demais_para_de_baixar(publico, monkeypatch):
    monkeypatch.setattr(pagina_web, "LIMITE_BYTES_HTML", 100_000)
    resp = Resp(200, b"a" * 300_000)
    with pytest.raises(PaginaRecusada, match="grande demais"):
        buscar("https://exemplo.com/", sessao=Sessao({"https://exemplo.com/": resp}))


def test_falha_de_rede_vira_mensagem(publico):
    import requests

    class Quebra:
        def get(self, url, **kw):
            raise requests.exceptions.ConnectTimeout("x")

    with pytest.raises(PaginaRecusada, match="demorou demais"):
        buscar("https://exemplo.com/", sessao=Quebra())
