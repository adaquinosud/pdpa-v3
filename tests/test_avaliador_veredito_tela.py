"""Leitura no formato 2 (avaliador-v21-veredito): processamento, gravação e tela.

A versão da leitura é posta à mão: estes testes valem antes e depois da virada (a virada
só muda qual versão a leitura NOVA recebe). Cliente dublado: nenhuma chamada paga."""

from __future__ import annotations

import json

import pytest

from src.avaliador import servico, veredito
from src.models.avaliador import AvaliadorAnalise
from tests.test_avaliador_servico import Dublê, resposta_v20
from src.models.empresa import Empresa
from tests.test_avaliador_servico import config_avaliador
from tests.test_ui_avaliador import _enviar, _url


@pytest.fixture
def empresa(db_session):
    e = Empresa(nome="Empresa Aval v20")
    db_session.add(e)
    db_session.commit()
    return e


@pytest.fixture
def teto(monkeypatch):
    config_avaliador(monkeypatch, AVALIADOR_TETO_MENSAL_USD=10.0)


def _pronta_v20(client_loyall, db_session, e, resp=None, **kw):
    assert _enviar(client_loyall, e, **kw).status_code == 200
    a = db_session.query(AvaliadorAnalise).order_by(AvaliadorAnalise.id.desc()).first()
    a.prompt_versao = veredito.PROMPT_VERSAO
    db_session.commit()
    servico.processar(a.id, client=Dublê([resp or resposta_v20()]))
    db_session.expire_all()
    return a.id


def _html(client_loyall, e, aid):
    return client_loyall.get(_url(e, f"/{aid}")).get_data(as_text=True)


def test_processar_grava_o_formato_2(client_loyall, db_session, empresa, teto):
    aid = _pronta_v20(client_loyall, db_session, empresa)
    a = db_session.get(AvaliadorAnalise, aid)
    assert a.status == "pronta" and a.resumo is None and a.erro_motivo is None
    assert servico.formato_da_leitura(a) == servico.FORMATO_VEREDITO
    g = json.loads(a.itens_json)
    assert len(g["doze"]) == 12 and g["lastro"]["ponto_de_partida"] == "P"
    assert g["cobertura"]["unidades"] == 3


def test_tela_na_ordem_do_parecer(client_loyall, db_session, empresa, teto):
    html = _html(client_loyall, empresa, _pronta_v20(client_loyall, db_session, empresa))
    secoes = ["situar", "achados", "contradicoes", "lastro", "vagas", "placar", "doze"]
    pos = [html.index(f'data-secao="{x}"') for x in secoes]
    assert pos == sorted(pos)
    assert "Proposta comercial." in html and "Leitor:</span> Quem decide sozinho." in html
    assert "Lidas 3 páginas." in html and "Imagens não são lidas" in html
    assert "Nenhum achado fora dos doze nesta peça." in html
    assert "Nenhuma contradição no texto lido." in html
    assert "Ponto de partida:</span> Precisão" in html
    assert "Padrão de teste. Comece pela Precisão." in html
    assert "D1 · Acessibilidade" in html and "p. 2: “segunda a sexta das 8h às 18h”" in html
    assert ">Sim<" in html and ">Parcial<" in html and ">Não<" in html
    assert "Deveria ter:</span> Quem cita a empresa como referência." in html
    assert ">Forte<" not in html and "Leitura no formato anterior" not in html
    assert "—" not in html and "–" not in html


def test_lastro_que_nao_nomeia_o_ponto_de_partida_ganha_alerta(
    client_loyall, db_session, empresa, teto
):
    aid = _pronta_v20(client_loyall, db_session, empresa, resposta_v20(lastro="Comece pelo D."))
    html = _html(client_loyall, empresa, aid)
    assert "o texto não nomeia o ponto de partida calculado (Precisão)" in html


def test_lastro_sem_texto_mostra_o_calculo_e_o_motivo(client_loyall, db_session, empresa, teto):
    aid = _pronta_v20(client_loyall, db_session, empresa, resposta_v20(lastro=None))
    a = db_session.get(AvaliadorAnalise, aid)
    assert a.status == "pronta" and a.erro_motivo == "lastro: RespostaInvalida"
    html = _html(client_loyall, empresa, aid)
    assert "Texto do Lastro não gerado (RespostaInvalida)" in html
    assert "Ponto de partida:</span> Precisão" in html


def test_achados_contradicoes_vagas_e_placar(client_loyall, db_session, empresa, teto):
    resp = resposta_v20(
        situar={
            "achados": [{"texto": "A proposta não diz quem assina.", "evidencias": []}],
            "contradicoes": [
                {
                    "texto": "Diz referência e não mostra quem cita.",
                    "evidencias": [
                        {"pagina": 3, "trecho": "Somos referência no setor há vinte anos"}
                    ],
                }
            ],
        }
    )
    html = _html(client_loyall, empresa, _pronta_v20(client_loyall, db_session, empresa, resp))
    assert "A proposta não diz quem assina." in html
    assert "Diz referência e não mostra quem cita." in html
    assert "p. 3: “Somos referência no setor há vinte anos”" in html
    vagas = html.split('data-secao="vagas"')[1].split('data-secao="placar"')[0]
    assert "D2 · Eficácia Operacional</div>" in vagas and "D1 ·" not in vagas  # D1 é "sim"
    # uma linha por conversa: o "deveria ter" fica só na linha do subpilar, nos doze
    assert "Dizer como e quando." not in vagas
    assert "Ordem das recomendações" not in html
    placar = html.split('data-secao="placar"')[1].split('data-secao="doze"')[0]
    assert "</span> 1 ·" in placar and "</span> 10</div>" in placar


def test_citacao_nao_conferida_no_veredito_nao_aparece(client_loyall, db_session, empresa, teto):
    aid = _pronta_v20(client_loyall, db_session, empresa)
    a = db_session.get(AvaliadorAnalise, aid)
    g = json.loads(a.itens_json)
    g["doze"][3]["evidencias"] = [  # D1
        {
            "pagina": 2,
            "trecho": "TRECHO-INVENTADO-XYZ",
            "conferido": False,
            "pagina_encontrada": None,
        }
    ]
    a.itens_json = json.dumps(g)
    db_session.commit()
    html = _html(client_loyall, empresa, aid)
    assert "TRECHO-INVENTADO-XYZ" not in html and "citação não encontrada na peça" in html


def test_a_linha_diz_onde_a_mesma_ausencia_foi_contada(client_loyall, db_session, empresa, teto):
    from tests.test_avaliador_servico import veredito_de

    p1 = dict(
        veredito_de("P1", "parcial", "segunda a sexta das 8h às 18h", 2), mesma_ausencia_de="Pa2"
    )
    resp = resposta_v20(vereditos={"P1": p1})
    html = _html(client_loyall, empresa, _pronta_v20(client_loyall, db_session, empresa, resp))
    assert "A mesma ausência está contada em Pa2 · Mutualidade." in html
