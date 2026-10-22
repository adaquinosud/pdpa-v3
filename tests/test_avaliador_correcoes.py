"""Correção à mão de uma leitura no formato 3 (fatia 1 do parecer no app, 22/10).

Recusar um trecho citado, incluir um trecho achado na peça e desfazer ficam gravados em
``avaliador_correcoes``, com o número da leitura e o hash do conteúdo; o resultado gravado da
leitura não muda e a tela aplica as correções por cima. Cliente LLM dublado, sem gasto."""

from __future__ import annotations

import json
import re

import pytest

from src.avaliador import servico
from src.avaliador.servico import AvaliacaoRecusada
from src.models.avaliador import CORRECAO_INCLUSAO, CORRECAO_RECUSA, AvaliadorCorrecao
from src.models.empresa import Empresa
from tests.test_avaliador_servico import HORARIO, Dublê, _criar, _rodar, config_avaliador
from tests.test_ui_avaliador import _pronta, _url

TRECHO = HORARIO[1]  # D1.01 e D1.04 citam este trecho no dublê


@pytest.fixture
def empresa(db_session):
    e = Empresa(nome="Empresa Aval correções")
    db_session.add(e)
    db_session.commit()
    return e


@pytest.fixture
def teto(monkeypatch):
    config_avaliador(monkeypatch, AVALIADOR_TETO_MENSAL_USD=10.0)


def _estados(a):
    tela = servico.organizar_marcas(servico.carregar_regua(), a, servico.correcoes_de(a))
    return {x["codigo"]: x for p in tela["pilares"] for sp in p["subpilares"] for x in sp["marcas"]}


def _pronta_servico(db_session, empresa):
    return _rodar(db_session, _criar(db_session, empresa), Dublê())


def test_recusar_grava_e_a_tela_aplica_sem_mexer_no_gravado(db_session, empresa, teto):
    a = _pronta_servico(db_session, empresa)
    gravado = a.itens_json
    servico.recusar_trecho(db_session, a, "D1.01", TRECHO, None)
    servico.recusar_trecho(db_session, a, "D1.01", TRECHO, None)  # repetida não duplica
    db_session.commit()
    (c,) = db_session.query(AvaliadorCorrecao).all()
    assert (c.analise_id, c.conteudo_hash, c.marca_codigo, c.tipo, c.trecho, c.pagina) == (
        a.id, a.conteudo_hash, "D1.01", CORRECAO_RECUSA, TRECHO, 2,
    )  # fmt: skip
    assert c.marca_texto == "Diz por onde se fala com a empresa?" and c.desfeita_em is None
    assert a.itens_json == gravado
    e = _estados(a)
    assert e["D1.01"]["estado"] == "nao_esta" and e["D1.01"]["corrigida"]
    assert [x["trecho"] for x in e["D1.01"]["recusadas"]] == [TRECHO]
    assert e["D1.04"]["estado"] == "esta"  # o mesmo trecho noutra marca não muda
    with pytest.raises(AvaliacaoRecusada, match="não é um dos citados"):
        servico.recusar_trecho(db_session, a, "D1.04", "outro trecho qualquer", None)


def test_incluir_so_entra_se_estiver_na_peca(db_session, empresa, teto):
    a = _pronta_servico(db_session, empresa)
    servico.incluir_trecho(db_session, a, "D1.05", "  Atendimento de segunda a sexta  ", None)
    db_session.commit()
    (c,) = db_session.query(AvaliadorCorrecao).all()
    assert (c.tipo, c.trecho, c.pagina) == (CORRECAO_INCLUSAO, "Atendimento de segunda a sexta", 2)
    e = _estados(a)
    assert e["D1.05"]["estado"] == "esta" and e["D1.05"]["evidencias"][0]["incluido"]
    with pytest.raises(AvaliacaoRecusada, match="não foi achado na peça"):
        servico.incluir_trecho(db_session, a, "D1.05", "texto que não existe nesta peça", None)
    servico.concluir(a)
    with pytest.raises(AvaliacaoRecusada, match="texto desta peça já foi apagado"):
        servico.incluir_trecho(db_session, a, "D1.03", "Atendimento de segunda a sexta", None)


def test_desfazer_marca_a_hora_e_a_correcao_fica(db_session, empresa, teto):
    a = _pronta_servico(db_session, empresa)
    servico.recusar_trecho(db_session, a, "D1.01", TRECHO, None)
    db_session.commit()
    c = db_session.query(AvaliadorCorrecao).one()
    servico.desfazer_correcao(db_session, a, c.id)
    db_session.commit()
    assert c.desfeita_em is not None and db_session.query(AvaliadorCorrecao).count() == 1
    assert _estados(a)["D1.01"]["estado"] == "esta"
    with pytest.raises(AvaliacaoRecusada, match="não está ativa"):
        servico.desfazer_correcao(db_session, a, c.id)


def test_apagar_leitura_tira_o_trecho_e_guarda_que_houve_correcao(db_session, empresa, teto):
    a = _pronta_servico(db_session, empresa)
    servico.recusar_trecho(db_session, a, "D1.01", TRECHO, None)
    db_session.commit()
    servico.apagar_leitura(a)
    db_session.commit()
    c = db_session.query(AvaliadorCorrecao).one()
    assert c.trecho == "" and (c.marca_codigo, c.tipo) == ("D1.01", CORRECAO_RECUSA)


def test_peca_de_medicao_aceita_correcao(db_session, empresa, teto, monkeypatch):
    a = _pronta_servico(db_session, empresa)
    monkeypatch.setattr(servico, "PECAS_DE_MEDICAO", frozenset({a.id}))
    servico.recusar_trecho(db_session, a, "D1.01", TRECHO, None)
    assert len(servico.correcoes_de(a)) == 1


def test_so_leitura_pronta_no_formato_atual(db_session, empresa, teto):
    a = db_session.get(servico.AvaliadorAnalise, _criar(db_session, empresa))  # pendente
    with pytest.raises(AvaliacaoRecusada, match="pode ser corrigida"):
        servico.recusar_trecho(db_session, a, "D1.01", TRECHO, None)


def test_tela_corrige_pelo_clique(client_loyall, db_session, empresa, teto):
    aid = _pronta(client_loyall, db_session, empresa)
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert "não responde" in html and "incluir trecho da peça" in html
    html = client_loyall.post(
        _url(empresa, f"/{aid}/corrigir/recusar"), data={"codigo": "D1.01", "trecho": TRECHO}
    ).get_data(as_text=True)
    linha = html.split('data-marca="D1.01"', 1)[1].split("</div>", 1)[0]
    assert 'data-estado="nao_esta"' in html.split('data-marca="D1.01"', 1)[1][:30]
    assert "(corrigida à mão)" in linha
    assert re.search(r'line-through">“' + re.escape(TRECHO) + "”</span> recusado à mão", html)
    c = db_session.query(AvaliadorCorrecao).one()
    assert c.usuario_id is not None  # quem corrigiu
    html = client_loyall.post(
        _url(empresa, f"/{aid}/corrigir/incluir"),
        data={"codigo": "D1.05", "trecho": "inexistente na peça"},
    ).get_data(as_text=True)
    assert "Esse trecho não foi achado na peça" in html
    html = client_loyall.post(
        _url(empresa, f"/{aid}/corrigir/desfazer"), data={"correcao_id": c.id}
    ).get_data(as_text=True)
    assert 'data-marca="D1.01" data-estado="esta"' in html
    assert client_loyall.post(_url(empresa, f"/{aid}/corrigir/outra")).status_code == 404
    assert json.loads(db_session.get(servico.AvaliadorAnalise, aid).itens_json)["formato"] == 3
