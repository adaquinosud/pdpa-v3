"""Formulário com "cliente com nome" e a tela do formato 3 (balizador de marcas, fatia 2,
18/10). O motor que grava o formato 3 é a fatia seguinte: aqui a leitura pronta é montada
no banco de TESTE, no formato combinado. Nenhuma chamada paga."""

from __future__ import annotations

import json

import pytest

from src.avaliador import servico, veredito
from src.avaliador.extracao import Documento
from src.avaliador.servico import AvaliacaoRecusada
from src.models.avaliador import AvaliadorAnalise
from src.models.empresa import Empresa
from tests.test_avaliador_servico import DESCRICAO, _pptx, config_avaliador
from tests.test_ui_avaliador import _enviar, _url


@pytest.fixture
def empresa(db_session):
    e = Empresa(nome="Empresa Aval marcas")
    db_session.add(e)
    db_session.commit()
    return e


@pytest.fixture
def teto(monkeypatch):
    config_avaliador(monkeypatch, AVALIADOR_TETO_MENSAL_USD=10.0)


TRECHO = "Atendimento de segunda a sexta das 8h às 18h"


def _ultima(db_session):
    return db_session.query(AvaliadorAnalise).order_by(AvaliadorAnalise.id.desc()).first()


def _marca(codigo, grupo, texto, esta, trecho=None, conferido=True):
    ev = [{"pagina": 2, "trecho": trecho, "conferido": conferido, "pagina_encontrada": 2}]
    return {
        "codigo": codigo,
        "grupo": grupo,
        "texto": texto,
        "esta": esta,
        "evidencias": ev if trecho else [],
    }


def _pronta_v3(client_loyall, db_session, e, cliente="nao"):
    assert _enviar(client_loyall, e, cliente=cliente).status_code == 200
    a = _ultima(db_session)
    cob = veredito.cobertura(Documento.de_json(a.texto_json))
    marcas = [
        _marca("D1.01", "D1", "Diz por onde se fala com a empresa?", True, TRECHO),
        _marca("D1.04", "D1", "Diz em que horário a empresa atende?", True, "inventado", False),
        _marca("D1.05", "D1", "Diz em que dias da semana há expediente?", False),
        _marca("Pa1.05", "Pa1", "Menciona o nome da empresa que vai ler?", False),
        _marca("P1.99", "P1", "Marca que saiu do Manual depois da leitura?", False),
        _marca("C.01", "C", "Quando cita dado ou pesquisa, diz de onde veio?", False),
    ]
    a.itens_json = json.dumps(
        {
            "formato": 3,
            "cobertura": cob,
            "marcas": marcas,
            "achados": [{"texto": "A peça não diz quem assina.", "evidencias": []}],
            "contradicoes": [],
        },
        ensure_ascii=False,
    )
    a.status = "pronta"
    db_session.commit()
    return a.id


def _html(client_loyall, e, aid):
    return client_loyall.get(_url(e, f"/{aid}")).get_data(as_text=True)


def test_formulario_pergunta_e_grava_cliente_com_nome(client_loyall, db_session, empresa, teto):
    html = client_loyall.get(_url(empresa)).get_data(as_text=True)
    assert "A peça foi feita para um cliente com nome?" in html
    assert html.count('name="cliente_nomeado"') == 2 and "required" in html
    _enviar(client_loyall, empresa, cliente="sim")
    assert _ultima(db_session).cliente_nomeado is True
    _enviar(client_loyall, empresa, cliente="nao")
    assert _ultima(db_session).cliente_nomeado is False


def test_sem_a_resposta_nada_e_gravado_nem_cobrado(client_loyall, db_session, empresa, teto):
    html = _enviar(client_loyall, empresa, cliente="").get_data(as_text=True)
    assert "Diga se a peça foi feita para um cliente com nome." in html
    assert 'value="nao" required checked' not in html
    assert db_session.query(AvaliadorAnalise).count() == 0
    with pytest.raises(AvaliacaoRecusada, match="cliente com nome"):
        servico.criar_analise(db_session, empresa.id, None, DESCRICAO, dados=_pptx())


def test_tela_do_formato_3(client_loyall, db_session, empresa, teto):
    aid = _pronta_v3(client_loyall, db_session, empresa)
    assert servico.formato_da_leitura(db_session.get(AvaliadorAnalise, aid)) == 3
    html = _html(client_loyall, empresa, aid)
    secoes = ["peca", "achados", "contradicoes", "marcas", "fora_dos_doze", "a_parte"]
    pos = [html.index(f'data-secao="{x}"') for x in secoes]
    assert pos == sorted(pos)
    assert "Peça sem cliente com nome." in html and "Lidas 3 páginas." in html
    assert "A peça não diz quem assina." in html
    # está: com o trecho achado na peça
    assert 'data-marca="D1.01" data-estado="esta"' in html and f"p. 2: “{TRECHO}”" in html
    # a leitura disse que está, mas o trecho não confere: não vira presença
    assert 'data-marca="D1.04" data-estado="sem_conferencia"' in html
    assert "o trecho citado não foi achado na peça" in html and "“inventado”" not in html
    assert 'data-marca="D1.05" data-estado="nao_esta"' in html
    # a marca que saiu do Manual aparece com o texto gravado
    assert "Marca que saiu do Manual depois da leitura?" in html
    assert (
        "Pilar 2: DISPONIBILIDADE" in html and "Apresenta como o cliente acessa a empresa?" in html
    )
    # sem veredito, placar, contagem ou percentual
    for fora in (">Sim<", ">Parcial<", "Placar", "Lastro", "%", " de 8", "Deveria ter"):
        assert fora not in html, fora
    assert "—" not in html and "–" not in html


def test_excecao_vai_para_o_grupo_a_parte_so_sem_cliente_com_nome(
    client_loyall, db_session, empresa, teto
):
    def onde(html):
        corte = html.index('data-secao="a_parte"') if 'data-secao="a_parte"' in html else None
        i = html.index('data-marca="Pa1.05"')
        return "a_parte" if corte is not None and i > corte else "Pa1"

    sem = _html(client_loyall, empresa, _pronta_v3(client_loyall, db_session, empresa, "nao"))
    assert onde(sem) == "a_parte" and "o vazio aqui não é falta desta peça" in sem
    assert "Pa1 · Menciona o nome da empresa que vai ler?" in sem
    com = _html(client_loyall, empresa, _pronta_v3(client_loyall, db_session, empresa, "sim"))
    assert onde(com) == "Pa1" and 'data-secao="a_parte"' not in com
    assert "Peça feita para um cliente com nome." in com
    aid = _pronta_v3(client_loyall, db_session, empresa, "nao")
    db_session.get(AvaliadorAnalise, aid).cliente_nomeado = None  # leitura de antes do campo
    db_session.commit()
    antiga = _html(client_loyall, empresa, aid)
    assert onde(antiga) == "Pa1" and "Não foi informado se a peça" in antiga
