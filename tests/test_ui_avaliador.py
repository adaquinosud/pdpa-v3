"""Tela do Avaliador: só admin (aba, URL e cada rota), aviso amarrado à constante de
retenção, e render do caminho feliz e dos estados (cliente LLM dublado, sem gasto)."""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from src.avaliador import servico
from src.models.avaliador import AvaliadorAnalise
from src.models.empresa import Empresa
from tests.test_avaliador_servico import SENTINELA, Dublê, _pptx, config_avaliador


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


def _subir(client, e, dados=None, nome="proposta.pptx"):
    return client.post(
        _url(e),
        data={"arquivo": (io.BytesIO(dados or _pptx()), nome)},
        content_type="multipart/form-data",
    )


def _analise_pronta(client_loyall, db_session, e, cli):
    r = _subir(client_loyall, e)
    assert r.status_code == 200
    aid = db_session.query(AvaliadorAnalise).one().id
    servico.processar(aid, client=cli)  # a thread é no-op em TESTING; roda aqui
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
    assert _subir(cli, empresa).status_code == 403
    for suf in ("/1", "/1/tipo", "/1/preco-anexo", "/1/retomar", "/1/concluir"):
        metodo = cli.get if suf == "/1" else cli.post
        assert metodo(_url(empresa, suf)).status_code == 403, suf


def test_analise_de_outra_empresa_e_404(client_loyall, db_session, empresa, teto):
    aid = _analise_pronta(client_loyall, db_session, empresa, Dublê())
    outra = Empresa(nome="Outra")
    db_session.add(outra)
    db_session.commit()
    assert client_loyall.get(_url(outra, f"/{aid}")).status_code == 404


# ── painel e aviso ─────────────────────────────────────────────────────────


def test_aviso_le_a_mesma_constante_que_apaga(client_loyall, empresa, monkeypatch):
    html = client_loyall.get(_url(empresa)).get_data(as_text=True)
    assert "modelo externo da Anthropic" in html and "depois de 7 dias sem uso" in html
    assert "ficam só os trechos citados na leitura" in html
    config_avaliador(monkeypatch, AVALIADOR_DIAS_RETENCAO_TEXTO=3)
    html = client_loyall.get(_url(empresa)).get_data(as_text=True)
    assert "depois de 3 dias sem uso" in html


def test_teto_zero_mostra_o_motivo_e_nao_cria(client_loyall, db_session, empresa):
    html = _subir(client_loyall, empresa).get_data(as_text=True)
    assert "desligado" in html
    assert db_session.query(AvaliadorAnalise).count() == 0


def test_word_e_recusado_com_mensagem(client_loyall, db_session, empresa, teto):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<w/>")
    html = _subir(client_loyall, empresa, buf.getvalue(), "proposta.pptx").get_data(as_text=True)
    assert "Documento do Word ainda não é aceito" in html
    assert db_session.query(AvaliadorAnalise).count() == 0


def test_upload_cria_e_mostra_processando_com_polling(client_loyall, db_session, empresa, teto):
    html = _subir(client_loyall, empresa).get_data(as_text=True)
    assert 'hx-trigger="every 3s"' in html and "Na fila" in html
    assert SENTINELA not in html  # o texto do documento não vai para a tela


# ── caminho feliz e estados ────────────────────────────────────────────────


def test_render_da_analise_pronta(client_loyall, db_session, empresa, teto):
    aid = _analise_pronta(client_loyall, db_session, empresa, Dublê(tipo="institucional"))
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert 'hx-trigger="every 3s"' not in html  # polling para no estado final
    assert "Padrão de teste." in html  # leitura do fim
    assert "Apresentação institucional" in html and "Refazer leitura com este tipo" in html
    assert "Quando eu precisar de você, eu alcanço uma pessoa?" in html
    assert "Acessibilidade" in html  # nome de NOME_SUBPILAR
    assert "Sem resposta" in html
    # frase buscada pelo id na biblioteca (L1-D1-01)
    assert "Falta dizer por onde falar com você" in html
    assert "não cobrada em Apresentação institucional" in html  # supressão declarada
    assert "Concluir" in html


def test_preco_pergunta_antes_e_frase_depois(client_loyall, db_session, empresa, teto):
    aid = _analise_pronta(client_loyall, db_session, empresa, Dublê(tipo="proposta"))
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert "Não encontrei preço neste documento" in html and "Não há anexo" in html
    html = client_loyall.post(
        _url(empresa, f"/{aid}/preco-anexo"), data={"em_anexo": "nao"}
    ).get_data(as_text=True)
    assert "Não encontrei preço neste documento" not in html
    assert "Não há preço aqui e não há anexo comercial" in html  # L1-P1d_sem_anexo-01


def test_citacao_nao_conferida_nao_aparece_como_citacao(client_loyall, db_session, empresa, teto):
    aid = _analise_pronta(client_loyall, db_session, empresa, Dublê())
    a = db_session.get(AvaliadorAnalise, aid)
    res = json.loads(a.resultado_json)
    res["D1"] = {
        "codigo": "D1",
        "veredito": "respondida",
        "evidencias": [
            {
                "pagina": 2,
                "trecho": "TRECHO-INVENTADO-XYZ",
                "conferido": False,
                "pagina_encontrada": None,
            },
            {
                "pagina": 1,
                "trecho": "segunda a sexta das 8h às 18h",
                "conferido": True,
                "pagina_encontrada": 2,
            },
        ],
        "frase_id": None,
        "complemento": None,
        "alerta": None,
    }
    a.resultado_json = json.dumps(res)
    db_session.commit()
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert "TRECHO-INVENTADO-XYZ" not in html
    assert "citação não encontrada no documento" in html
    assert "p. 2 — “segunda a sexta das 8h às 18h”" in html and "o modelo citou a p. 1" in html


def test_falhou_mostra_motivo_e_retomar(client_loyall, db_session, empresa, teto):
    aid = _analise_pronta(client_loyall, db_session, empresa, Dublê(ruins={"A3"}))
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert "A leitura não terminou" in html and "A3" in html and "Retomar" in html


def test_corrigir_tipo_volta_para_a_fila(client_loyall, db_session, empresa, teto):
    aid = _analise_pronta(client_loyall, db_session, empresa, Dublê())
    html = client_loyall.post(_url(empresa, f"/{aid}/tipo"), data={"tipo": "proposta"}).get_data(
        as_text=True
    )
    assert "Na fila" in html and 'hx-trigger="every 3s"' in html
    db_session.expire_all()
    assert db_session.get(AvaliadorAnalise, aid).tipo_corrigido == "proposta"


def test_concluir_apaga_o_texto(client_loyall, db_session, empresa, teto):
    aid = _analise_pronta(client_loyall, db_session, empresa, Dublê())
    html = client_loyall.post(_url(empresa, f"/{aid}/concluir")).get_data(as_text=True)
    assert "Texto do documento apagado em" in html and "Refazer leitura" not in html
    db_session.expire_all()
    assert db_session.get(AvaliadorAnalise, aid).texto_json is None
