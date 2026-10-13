"""Tela do Avaliador: só admin (aba, URL e cada rota), aviso amarrado à constante de
retenção, render do caminho feliz e dos estados (cliente LLM dublado, sem gasto)."""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from src.avaliador import servico
from src.models.avaliador import AvaliadorAnalise
from src.models.empresa import Empresa
from tests.test_avaliador_servico import DESCRICAO, SENTINELA, Dublê, _pptx, config_avaliador


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


def _enviar(client, e, dados=None, nome="proposta.pptx", texto="", descricao=DESCRICAO):
    data = {"descricao": descricao, "texto": texto}
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
    for suf in ("/1/refazer", "/1/concluir"):
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
    assert "modelo externo da Anthropic" in html and "depois de 7 dias sem uso" in html
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


def test_word_e_recusado_com_mensagem(client_loyall, db_session, empresa, teto):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<w/>")
    html = _enviar(client_loyall, empresa, buf.getvalue()).get_data(as_text=True)
    assert "Documento do Word ainda não é aceito" in html
    assert db_session.query(AvaliadorAnalise).count() == 0


def test_envio_mostra_processando_com_polling(client_loyall, empresa, teto):
    html = _enviar(client_loyall, empresa).get_data(as_text=True)
    assert 'hx-trigger="every 3s"' in html and "Na fila" in html
    assert SENTINELA not in html  # o texto da peça não vai para a tela


# ── caminho feliz e estados ────────────────────────────────────────────────


def test_render_da_analise_pronta(client_loyall, db_session, empresa, teto):
    aid = _pronta(client_loyall, db_session, empresa)
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert 'hx-trigger="every 3s"' not in html
    assert "Padrão de teste." in html  # resumo
    assert "Pilar 2 — DISPONIBILIDADE" in html  # título literal do Manual
    assert "D1 · Acessibilidade" in html
    assert "o cliente consegue chegar ao serviço, ser atendido, abordar o balcão?" in html
    assert ">Forte<" in html and ">Falta<" in html and ">Melhorar<" in html
    assert "“segunda a sexta das 8h às 18h”" in html and "p. 2" in html
    assert "P1 · Calibração da Promessa — sem observação nesta peça." in html
    assert "Reler com esta descrição" in html and "Concluir" in html


def test_texto_colado_sem_paginas(client_loyall, db_session, empresa, teto):
    conversa = (
        "Cliente: com quem eu falo se der problema?\nVendedor: comigo, Fulano, das 8h às 18h."
    )
    resp = {
        "resumo": "Faltou rota fora do horário.",
        "itens": [
            {
                "subpilar": "D1",
                "tipo": "forte",
                "texto": "Nomeou a pessoa.",
                "evidencias": [{"pagina": 1, "trecho": "comigo, Fulano, das 8h às 18h"}],
            }
        ],
    }
    aid = _pronta(client_loyall, db_session, empresa, Dublê([resp]), dados=False, texto=conversa)
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert "Texto colado" in html and "“comigo, Fulano, das 8h às 18h”" in html
    assert "p. 1" not in html


def test_citacao_nao_conferida_nao_aparece_como_citacao(client_loyall, db_session, empresa, teto):
    aid = _pronta(client_loyall, db_session, empresa)
    a = db_session.get(AvaliadorAnalise, aid)
    itens = json.loads(a.itens_json)
    itens[0]["evidencias"] = [
        {
            "pagina": 2,
            "trecho": "TRECHO-INVENTADO-XYZ",
            "conferido": False,
            "pagina_encontrada": None,
        }
    ]
    a.itens_json = json.dumps(itens)
    db_session.commit()
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert "TRECHO-INVENTADO-XYZ" not in html
    assert "citação não encontrada na peça" in html


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
    db_session.expire_all()
    assert db_session.get(AvaliadorAnalise, aid).texto_json is None
