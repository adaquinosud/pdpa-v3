"""Tela do Avaliador: só admin (aba, URL e cada rota), aviso amarrado à constante de
retenção, render do caminho feliz e dos estados (cliente LLM dublado, sem gasto)."""

from __future__ import annotations

import io
import json

import pytest

from src.avaliador import servico
from src.models.avaliador import AvaliadorAnalise
from src.models.empresa import Empresa
from tests.test_avaliador_servico import (
    DESCRICAO,
    SENTINELA,
    Dublê,
    _pptx,
    config_avaliador,
    resposta_v25,
)


@pytest.fixture
def empresa(db_session):
    e = Empresa(nome="Empresa Aval")
    db_session.add(e)
    db_session.commit()
    return e


@pytest.fixture
def teto(monkeypatch):
    config_avaliador(monkeypatch, AVALIADOR_TETO_MENSAL_USD=10.0)


def _url(e, sufixo=""):
    return f"/empresas/{e.id}/explorar/avaliador{sufixo}"


def _enviar(
    client,
    e,
    dados=None,
    nome="proposta.pptx",
    texto="",
    descricao=DESCRICAO,
    url="",
    cliente="nao",
):
    data = {"descricao": descricao, "texto": texto, "url": url, "cliente_nomeado": cliente}
    if dados is not False:
        data["arquivo"] = (io.BytesIO(dados or _pptx()), nome)
    return client.post(_url(e), data=data, content_type="multipart/form-data")


def _pronta(client_loyall, db_session, e, cli=None, **kw):
    assert _enviar(client_loyall, e, **kw).status_code == 200
    aid = db_session.query(AvaliadorAnalise).order_by(AvaliadorAnalise.id.desc()).first().id
    servico.processar(aid, client=cli or Dublê())  # a thread é no-op em TESTING
    db_session.expire_all()
    return aid


# ── acesso ─────────────────────────────────────────────────────────────────


def test_admin_ve_a_aba_e_cliente_nao(client_loyall, client_cliente_factory, empresa):
    html = client_loyall.get(f"/empresas/{empresa.id}/explorar").get_data(as_text=True)
    assert ">Avaliador<" in html
    cli = client_cliente_factory(empresa.id)
    html = cli.get(f"/empresas/{empresa.id}/explorar").get_data(as_text=True)
    assert ">Avaliador<" not in html


def test_cliente_nao_abre_pela_url_da_aba(client_cliente_factory, empresa):
    cli = client_cliente_factory(empresa.id)
    for url in (
        f"/empresas/{empresa.id}/explorar?tab=avaliador",
        f"/empresas/{empresa.id}/explorar/tab/avaliador",
    ):
        html = cli.get(url).get_data(as_text=True)
        assert "Carregando o Avaliador" not in html and "avaliador-painel" not in html


def test_cliente_recebe_403_em_todas_as_rotas(client_cliente_factory, empresa):
    cli = client_cliente_factory(empresa.id)
    assert cli.get(_url(empresa)).status_code == 403
    assert _enviar(cli, empresa).status_code == 403
    assert cli.get(_url(empresa, "/1")).status_code == 403
    for suf in ("/1/refazer", "/1/concluir", "/1/apagar"):
        assert cli.post(_url(empresa, suf)).status_code == 403, suf


def test_analise_de_outra_empresa_e_404(client_loyall, db_session, empresa, teto):
    aid = _pronta(client_loyall, db_session, empresa)
    outra = Empresa(nome="Outra")
    db_session.add(outra)
    db_session.commit()
    assert client_loyall.get(_url(outra, f"/{aid}")).status_code == 404


# ── painel e aviso ─────────────────────────────────────────────────────────


def test_aviso_le_a_mesma_constante_que_apaga(client_loyall, empresa, monkeypatch):
    html = client_loyall.get(_url(empresa)).get_data(as_text=True)
    assert "O documento vai para um modelo externo da Anthropic para ser lido." in html
    assert "Você também pode apagar a leitura inteira, com o resumo e os trechos citados" in html
    assert (
        "Pelos termos comerciais da Anthropic, o conteúdo enviado é tratado como informação "
        "confidencial e não pode ser usado para treinar modelos." in html
    )
    assert "O texto das páginas vai para um modelo externo da Anthropic para ser lido." in html
    assert "depois de 7 dias sem uso" in html
    assert "ficam só os trechos citados na leitura" in html
    assert "O que é esta peça e para que ela serve?" in html
    config_avaliador(monkeypatch, AVALIADOR_DIAS_RETENCAO_TEXTO=3)
    html = client_loyall.get(_url(empresa)).get_data(as_text=True)
    assert "depois de 3 dias sem uso" in html


def test_teto_zero_mostra_o_motivo_e_nao_cria(client_loyall, db_session, empresa):
    html = _enviar(client_loyall, empresa).get_data(as_text=True)
    assert "desligado" in html
    assert db_session.query(AvaliadorAnalise).count() == 0


def test_sem_descricao_recusa_e_preserva_o_texto(client_loyall, db_session, empresa, teto):
    html = _enviar(client_loyall, empresa, dados=False, texto="Cliente: oi", descricao="").get_data(
        as_text=True
    )
    assert "o que é a peça e para que ela serve" in html and "Cliente: oi" in html
    assert db_session.query(AvaliadorAnalise).count() == 0


def test_doc_antigo_e_recusado_com_instrucao(client_loyall, db_session, empresa, teto):
    doc = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64 + "WordDocument".encode("utf-16-le")
    html = _enviar(client_loyall, empresa, doc, nome="contrato.doc").get_data(as_text=True)
    assert "Documento do Word antigo (.doc). Abra no Word e salve como .docx" in html
    assert db_session.query(AvaliadorAnalise).count() == 0


def test_render_de_word_cita_secao_e_conta_secoes(client_loyall, db_session, empresa, teto):
    from tests.test_avaliador_word import _docx, _p

    corpo = (
        _p(f"Proposta comercial para a Empresa X. {SENTINELA}")
        + _p("Atendimento", "Ttulo1")
        + _p("Atendimento de segunda a sexta das 8h às 18h pelo gerente de conta.")
        + _p("Quem somos", "Ttulo1")
        + _p("Somos referência no setor há vinte anos, com clientes em todo o país.")
    )
    aid = _pronta(client_loyall, db_session, empresa, dados=_docx(corpo), nome="proposta.docx")
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert "3 seções" in html and "páginas" not in html.split("modelo")[0][-200:]
    assert "seção “Atendimento”: “segunda a sexta das 8h às 18h”" in html
    assert "seção “Quem somos”: “Somos referência no setor há vinte anos”" in html
    assert "p. 2" not in html


def test_envio_mostra_processando_com_polling(client_loyall, empresa, teto):
    html = _enviar(client_loyall, empresa).get_data(as_text=True)
    assert 'hx-trigger="every 3s"' in html and "Na fila" in html
    assert SENTINELA not in html  # o texto da peça não vai para a tela


# ── caminho feliz e estados ────────────────────────────────────────────────


def test_render_da_analise_pronta(client_loyall, db_session, empresa, teto):
    aid = _pronta(client_loyall, db_session, empresa)
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert 'hx-trigger="every 3s"' not in html
    assert "Pilar 2: DISPONIBILIDADE" in html  # título do Manual, sem travessão na tela
    assert "Apresenta como o cliente acessa a empresa?" in html  # pergunta do capítulo 17
    assert "D1 · Acessibilidade" in html
    assert "o cliente consegue chegar ao serviço, ser atendido, abordar o balcão?" in html
    for fora in (">Sim<", ">Parcial<", ">Forte<", "Placar", "Deveria ter", "formato anterior"):
        assert fora not in html, fora
    assert "p. 2: “segunda a sexta das 8h às 18h”" in html
    assert 'data-marca="D1.04" data-estado="esta"' in html  # o mesmo trecho em duas marcas
    assert "—" not in html and "–" not in html  # nenhum travessão na tela
    secoes = ["peca", "achados", "contradicoes", "marcas", "fora_dos_doze", "a_parte"]
    pos = [html.index(f'data-secao="{x}"') for x in secoes]
    assert pos == sorted(pos)
    assert "Nenhum achado fora das marcas nesta peça." in html
    assert "Nenhuma contradição no texto lido." in html
    assert "Peça sem cliente com nome." in html
    assert "Lidas 3 páginas." in html and "Imagens não são lidas" in html
    assert "Reler com esta descrição" in html and "Concluir" in html


def test_pagina_sem_texto_mostra_os_dois_criterios(client_loyall, db_session, empresa, teto):
    from src.avaliador.extracao import FRACAO_CONTROLES_ILEGIVEL, MIN_CARACTERES_PAGINA

    aid = _pronta(client_loyall, db_session, empresa)
    db_session.get(AvaliadorAnalise, aid).paginas_sem_texto_json = "[2]"
    db_session.commit()
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert f"menos de {MIN_CARACTERES_PAGINA} caracteres" in html
    pct = round(FRACAO_CONTROLES_ILEGIVEL * 100)
    assert f"texto ilegível, com mais de {pct}% de caracteres de controle" in html


def test_texto_colado_sem_paginas(client_loyall, db_session, empresa, teto):
    conversa = (
        "Cliente: com quem eu falo se der problema?\nVendedor: comigo, Fulano, das 8h às 18h."
    )
    resp = resposta_v25({"D1.03": (1, "comigo, Fulano, das 8h às 18h")})
    aid = _pronta(client_loyall, db_session, empresa, Dublê([resp]), dados=False, texto=conversa)
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert "Texto colado" in html and "“comigo, Fulano, das 8h às 18h”" in html
    assert "p. 1" not in html and "Lido o texto colado, inteiro." in html


def test_citacao_nao_conferida_nao_aparece_como_citacao(client_loyall, db_session, empresa, teto):
    aid = _pronta(client_loyall, db_session, empresa)
    a = db_session.get(AvaliadorAnalise, aid)
    g = json.loads(a.itens_json)
    d101 = next(m for m in g["marcas"] if m["codigo"] == "D1.01")
    d101["evidencias"] = [
        {
            "pagina": 2,
            "trecho": "TRECHO-INVENTADO-XYZ",
            "conferido": False,
            "pagina_encontrada": None,
        }
    ]
    a.itens_json = json.dumps(g)
    db_session.commit()
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert "TRECHO-INVENTADO-XYZ" not in html
    assert 'data-marca="D1.01" data-estado="sem_conferencia"' in html
    assert "o trecho citado não foi achado na peça" in html


def test_falhou_mostra_motivo_e_tentar_de_novo(client_loyall, db_session, empresa, teto):
    aid = _pronta(client_loyall, db_session, empresa, Dublê(quebra=True))
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert "A leitura não terminou" in html and "Tentar de novo" in html


def test_reler_com_outra_descricao_volta_para_a_fila(client_loyall, db_session, empresa, teto):
    aid = _pronta(client_loyall, db_session, empresa)
    html = client_loyall.post(
        _url(empresa, f"/{aid}/refazer"), data={"descricao": "Conversa de pós-venda"}
    ).get_data(as_text=True)
    assert "Na fila" in html and 'hx-trigger="every 3s"' in html
    db_session.expire_all()
    assert db_session.get(AvaliadorAnalise, aid).descricao == "Conversa de pós-venda"


def test_concluir_apaga_o_texto(client_loyall, db_session, empresa, teto):
    aid = _pronta(client_loyall, db_session, empresa)
    html = client_loyall.post(_url(empresa, f"/{aid}/concluir")).get_data(as_text=True)
    assert "Texto da peça apagado em" in html and "Reler com esta descrição" not in html
    assert "não dá para reler com outra descrição" in html
    # A situação na lista é só a da leitura: o texto apagado se diz na página da leitura.
    assert "texto apagado" not in html
    db_session.expire_all()
    assert db_session.get(AvaliadorAnalise, aid).texto_json is None


def test_apagar_leitura_tira_a_peca_e_guarda_so_o_gasto(client_loyall, db_session, empresa, teto):
    aid = _pronta(client_loyall, db_session, empresa)
    antes = db_session.get(AvaliadorAnalise, aid)
    custo, criado, modelo, versao = (
        antes.custo_usd,
        antes.criado_em,
        antes.modelo,
        antes.prompt_versao,
    )
    assert custo > 0 and antes.itens_json != "[]"
    gasto = servico.gasto_do_mes(db_session, empresa.id)
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert "Apagar leitura" in html and "Não dá para desfazer." in html  # hx-confirm, uma vez

    html = client_loyall.post(_url(empresa, f"/{aid}/apagar")).get_data(as_text=True)
    assert "Leitura apagada." in html and "proposta.pptx" not in html  # a lista se atualiza

    db_session.expire_all()
    a = db_session.get(AvaliadorAnalise, aid)
    assert a.status == "apagada"
    assert (a.descricao, a.arquivo_nome, a.conteudo_hash, a.resumo) == ("", None, "", None)
    assert a.itens_json == "[]" and a.texto_json is None
    assert (a.empresa_id, a.criado_em, a.modelo, a.prompt_versao) == (
        empresa.id,
        criado,
        modelo,
        versao,
    )
    assert a.custo_usd == custo  # o gasto fica: apagar não devolve nada ao teto
    assert servico.gasto_do_mes(db_session, empresa.id) == gasto

    painel = client_loyall.get(_url(empresa)).get_data(as_text=True)
    assert "proposta.pptx" not in painel and DESCRICAO not in painel
    assert client_loyall.get(_url(empresa, f"/{aid}")).status_code == 404
    for suf in ("/refazer", "/concluir", "/apagar"):
        assert client_loyall.post(_url(empresa, f"/{aid}{suf}")).status_code == 404, suf


def test_apagar_e_recusado_com_a_leitura_em_andamento(client_loyall, db_session, empresa, teto):
    assert _enviar(client_loyall, empresa).status_code == 200  # a thread é no-op: fica na fila
    aid = db_session.query(AvaliadorAnalise).order_by(AvaliadorAnalise.id.desc()).first().id
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert "Apagar leitura" not in html
    html = client_loyall.post(_url(empresa, f"/{aid}/apagar")).get_data(as_text=True)
    assert "A leitura ainda está em andamento." in html
    db_session.expire_all()
    a = db_session.get(AvaliadorAnalise, aid)
    assert a.status == "pendente" and a.descricao == DESCRICAO and a.texto_json is not None


def test_pagina_exibida_e_a_conferida_e_a_lista_se_atualiza(
    client_loyall, db_session, empresa, teto
):
    aid = _pronta(client_loyall, db_session, empresa)
    a = db_session.get(AvaliadorAnalise, aid)
    g = json.loads(a.itens_json)
    # o modelo citou a p. 3; o trecho está na p. 2 — a tela mostra a p. 2, e só ela
    next(m for m in g["marcas"] if m["codigo"] == "D1.01")["evidencias"] = [
        {"pagina": 3, "trecho": "segunda a sexta", "conferido": True, "pagina_encontrada": 2}
    ]
    a.itens_json = json.dumps(g)
    db_session.commit()
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    # um bloco por marca: a D1.01 mostra o trecho DELA, na página onde foi achado (o trecho
    # maior, da D1.04, fica no bloco da D1.04)
    bloco = next(b for b in html.split("data-diz")[1:] if 'data-marca="D1.01"' in b)
    assert 'data-marca="D1.04"' not in bloco and "p. 2: “segunda a sexta”" in bloco
    assert "p. 3: “segunda" not in html and "citou" not in html
    # a lista de baixo vem junto, fora da área trocada, com o estado e o custo atuais
    assert 'id="avaliador-lista" hx-swap-oob="true"' in html
    lista = html.split('id="avaliador-lista"', 1)[1]
    assert "Pronta" in lista and "Na fila" not in lista and "US$ 0,0000" not in lista


def test_descartados_e_resumo_ausente_aparecem_declarados(client_loyall, db_session, empresa, teto):
    aid = _pronta(client_loyall, db_session, empresa)
    a = db_session.get(AvaliadorAnalise, aid)
    item = {"subpilar": "D2", "tipo": "falta", "evidencias": [], "alerta": None}
    a.itens_json = json.dumps(
        [dict(item, texto=f"Achado {n}.", descartado=n >= 3) for n in range(5)]
    )
    a.resumo, a.erro_motivo = None, "resumo: OrcamentoEsgotado"
    db_session.commit()
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert "Achado 2." in html and "Achado 3." not in html and "Achado 4." not in html
    assert "Mais 2 itens descartados pelo limite de três por subpilar." in html
    assert "Resumo não gerado (resumo: OrcamentoEsgotado). Os itens abaixo estão completos." in html


def test_pagina_da_web_mostra_o_endereco_lido_e_a_referencia(
    client_loyall, db_session, empresa, teto, monkeypatch
):
    from src.avaliador import pagina_web
    from tests.test_avaliador_pagina_web import HTML

    monkeypatch.setattr(
        pagina_web,
        "buscar",
        lambda url, sessao=None: ("https://exemplo.com.br/inicio", HTML.encode()),
    )
    resp = resposta_v25({"D1.02": (2, "responde em até quatro horas úteis")})
    aid = _pronta(
        client_loyall, db_session, empresa, Dublê([resp]), dados=False, url="exemplo.com.br"
    )
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert "Página lida:" in html and "https://exemplo.com.br/inicio" in html
    assert "Só esta página foi lida, não o site inteiro." in html and "4 seções" in html
    assert "seção “Como atendemos”: “responde em até quatro horas úteis”" in html
    assert "p. 2" not in html
    assert "Lida só a página enviada (4 seções, com o rodapé)" in html
    assert "links não foram seguidos" in html


def test_pagina_que_nao_pode_ser_lida_mostra_o_motivo_e_nao_cria(
    client_loyall, db_session, empresa, teto, monkeypatch
):
    from src.avaliador import pagina_web

    def recusa(url, sessao=None):
        raise pagina_web.PaginaRecusada("A página pede senha. Salve como PDF.")

    monkeypatch.setattr(pagina_web, "buscar", recusa)
    html = _enviar(client_loyall, empresa, dados=False, url="exemplo.com").get_data(as_text=True)
    assert "A página pede senha. Salve como PDF." in html and ">exemplo.com</textarea>" in html
    assert "O texto das páginas vai" in html  # o aviso fica na versão da página
    assert db_session.query(AvaliadorAnalise).count() == 0


def test_citacao_de_linha_de_tabela_vem_celula_por_celula(client_loyall, db_session, empresa, teto):
    # o "|" entre células é nosso, não existe no documento: a tela não pode mostrá-lo
    from tests.test_avaliador_word import _docx, _p

    corpo = (
        _p(f"Proposta comercial para a Empresa X, com os planos e valores abaixo. {SENTINELA}")
        + "<w:tbl><w:tr><w:tc>" + _p("Essencial") + "</w:tc><w:tc>"
        + _p("Até 10 unidades, R$ 8.000 por diagnóstico") + "</w:tc></w:tr>"
        + "<w:tr><w:tc>" + _p("Completo") + "</w:tc><w:tc>" + _p("Até 30 unidades")
        + "</w:tc></w:tr></w:tbl>"
    )  # fmt: skip
    resposta = resposta_v25(
        {
            "Pa2.01": [
                (1, "Essencial | Até 10 unidades, R$ 8.000 por diagnóstico"),
                # trecho que junta duas linhas (leitura 12): uma parte por linha
                (1, "R$ 8.000 por diagnóstico\nCompleto | Até 30"),
            ]
        }
    )
    aid = _pronta(
        client_loyall, db_session, empresa, cli=Dublê([resposta]), dados=_docx(corpo),
        nome="proposta.docx",
    )  # fmt: skip
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert (
        "linha da tabela que começa “Essencial”: “Essencial” · "
        "“Até 10 unidades, R$ 8.000 por diagnóstico”"
    ) in html
    assert "Essencial | Até" not in html
    assert "“R$ 8.000 por diagnóstico” · “Completo” · “Até 30”" in html


# ── três leitores: formato 1 (itens), 2 (veredito) e 3 (marcas) ─────────────


def test_formato_da_leitura_reconhece_o_gravado(db_session, empresa):
    a = AvaliadorAnalise(itens_json="[]")
    assert servico.formato_da_leitura(a) == servico.FORMATO_ITENS
    a.itens_json = json.dumps({"formato": 2, "doze": []})
    assert servico.formato_da_leitura(a) == servico.FORMATO_VEREDITO
    a.itens_json = json.dumps({"formato": 3, "marcas": []})
    assert servico.formato_da_leitura(a) == servico.FORMATO_MARCAS
    for estranho in ('{"doze": []}', '"texto"', "{quebrado"):
        a.itens_json = estranho
        assert servico.formato_da_leitura(a) is None, estranho


def test_leitura_antiga_ganha_aviso_so_quando_o_formato_atual_e_outro(
    client_loyall, db_session, empresa, teto, monkeypatch
):
    aid = _pronta(client_loyall, db_session, empresa)
    a = db_session.get(AvaliadorAnalise, aid)  # vira leitura antiga, gravada no formato 1
    a.itens_json = json.dumps(
        [
            {
                "subpilar": "D1",
                "tipo": "forte",
                "texto": "Bom.",
                "evidencias": [],
                "alerta": None,
                "descartado": False,
            }
        ]
    )
    a.resumo = "Resumo antigo."
    db_session.commit()
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert "Leitura num formato anterior (forte, falta e melhorar" in html
    assert ">Forte<" in html  # continua legível
    assert "Resumo antigo." in html
    monkeypatch.setattr(servico, "FORMATO_ATUAL", servico.FORMATO_ITENS)
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert "formato anterior" not in html and ">Forte<" in html


def test_formato_nao_reconhecido_e_declarado_sem_quebrar(client_loyall, db_session, empresa, teto):
    aid = _pronta(client_loyall, db_session, empresa)
    db_session.get(AvaliadorAnalise, aid).itens_json = '{"outra": "coisa"}'
    db_session.commit()
    r = client_loyall.get(_url(empresa, f"/{aid}"))
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "formato que a tela não reconhece" in html
    assert ">Forte<" not in html


def test_varias_paginas_numa_leitura_so(client_loyall, db_session, empresa, teto, monkeypatch):
    from src.avaliador import pagina_web
    from tests.test_avaliador_pagina_web import HTML

    paginas = {
        "exemplo.com.br": ("https://exemplo.com.br/", HTML),
        "exemplo.com.br/prazos": ("https://exemplo.com.br/prazos", HTML.replace("Loja", "Prazo")),
    }
    monkeypatch.setattr(
        pagina_web, "buscar", lambda url, sessao=None: (paginas[url][0], paginas[url][1].encode())
    )
    aid = _pronta(
        client_loyall, db_session, empresa, dados=False, url="exemplo.com.br\nexemplo.com.br/prazos"
    )
    a = db_session.get(AvaliadorAnalise, aid)
    assert a.arquivo_nome == "https://exemplo.com.br/\nhttps://exemplo.com.br/prazos"
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert "Páginas lidas juntas (2):" in html
    assert "Só estas páginas foram lidas, não o site inteiro." in html
    assert "Lidas juntas as 2 páginas enviadas" in html and "/, /prazos." in html
    lista = html.split('id="avaliador-lista"', 1)[1]
    assert "https://exemplo.com.br/ e mais 1 página" in lista


def test_uma_pagina_que_falha_recusa_antes_de_gastar_e_diz_o_que_fazer(
    client_loyall, db_session, empresa, teto, monkeypatch
):
    from src.avaliador import pagina_web, servico
    from tests.test_avaliador_pagina_web import HTML

    def buscar(url, sessao=None):
        if url.endswith("/fechada"):
            raise pagina_web.PaginaRecusada("A página pede senha. Salve como PDF.")
        return "https://exemplo.com.br/", HTML.encode()

    chamadas = []
    monkeypatch.setattr(pagina_web, "buscar", buscar)
    monkeypatch.setattr(servico, "disparar", lambda *a, **k: chamadas.append(a))
    html = _enviar(
        client_loyall, empresa, dados=False, url="exemplo.com.br\nexemplo.com.br/fechada"
    ).get_data(as_text=True)
    assert "Na página exemplo.com.br/fechada: A página pede senha." in html
    assert "tire esta página da lista ou corrija o endereço. Nada foi lido nem cobrado." in html
    assert db_session.query(AvaliadorAnalise).count() == 0  # nada gravado, nenhum custo
    assert chamadas == []  # o modelo não foi chamado


def test_numero_da_leitura_na_lista_e_na_analise(client_loyall, db_session, empresa, teto):
    aid = _pronta(client_loyall, db_session, empresa)
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert f"Leitura nº {aid} ·" in html and "peça de medição" not in html
    assert "Reler com esta descrição" in html and "Apagar leitura" in html
    lista = client_loyall.get(_url(empresa)).get_data(as_text=True)
    assert ">Nº</th>" in lista and f'<td class="py-1 pr-2 text-loyall-500">{aid}</td>' in lista


def test_peca_de_medicao_sem_botoes_e_recusada_na_rota(
    client_loyall, db_session, empresa, teto, monkeypatch
):
    aid = _pronta(client_loyall, db_session, empresa)
    monkeypatch.setattr(servico, "PECAS_DE_MEDICAO", frozenset({aid}))
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert f"Leitura nº {aid} · peça de medição ·" in html and "data-medicao" in html
    for botao in ("Reler com esta descrição", "Concluir</button>", "Apagar leitura"):
        assert botao not in html
    for suf in ("/refazer", "/concluir", "/apagar"):  # pela rota, mesmo sem o botão
        html = client_loyall.post(_url(empresa, f"/{aid}{suf}")).get_data(as_text=True)
        assert "Peça de medição: o texto e o resultado desta leitura" in html
    a = db_session.get(AvaliadorAnalise, aid)
    db_session.refresh(a)
    assert a.texto_json is not None and a.status == "pronta"
