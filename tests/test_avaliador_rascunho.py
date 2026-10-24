"""O rascunho do parecer pelo modelo (fatia 3, 22/10): a ordem e os doze achados, só em campo
em branco, passados um a um pela pessoa (editar ou aceitar como está) antes do Word.
Cliente LLM dublado, sem gasto."""

from __future__ import annotations

import io
import json
from types import SimpleNamespace

import pytest

from src.avaliador import parecer as P
from src.avaliador import rascunho as R
from src.avaliador import servico
from src.avaliador.motor import RespostaInvalida
from src.avaliador.servico import AvaliacaoRecusada
from src.models.avaliador import AvaliadorAnalise, AvaliadorParecer
from src.models.empresa import Empresa
from tests.test_avaliador_servico import (
    HORARIO,
    SENTINELA,
    Dublê,
    _criar,
    _rodar,
    config_avaliador,
)
from tests.test_ui_avaliador import _pronta, _url

SUBS = servico.SUBPILARES_ORDEM


def _bom(**troca):
    obj = {
        "ordem": "A peça rompe na Precisão: não diz o que entrega.",
        "achados": {c: f"Achado do modelo para {nome}." for c, nome in zip(SUBS, "abcdefghijkl")},
    }
    obj.update(troca)
    return obj


class Modelo:
    """Dublê do cliente: devolve as respostas na ordem e guarda o que recebeu."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.chamadas = []
        self.messages = self

    def create(self, **kw):
        self.chamadas.append(kw)
        r = self.respostas.pop(0)
        texto = r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=texto)],
            usage=SimpleNamespace(
                input_tokens=4000,
                output_tokens=1500,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
            ),
        )


@pytest.fixture
def empresa(db_session):
    e = Empresa(nome="Empresa Aval rascunho")
    db_session.add(e)
    db_session.commit()
    return e


@pytest.fixture
def teto(monkeypatch):
    config_avaliador(monkeypatch, AVALIADOR_TETO_MENSAL_USD=10.0)


def _pronta_servico(db_session, empresa):
    return _rodar(db_session, _criar(db_session, empresa), Dublê())


def _tela(a):
    return servico.organizar_marcas(servico.carregar_regua(), a, servico.correcoes_de(a))


def _montar(a):
    return P.montar(_tela(a), servico.textos_do_parecer(a), a.id, "22/10/2026",
                    json.loads(a.itens_json)["cobertura"])  # fmt: skip


def _rj(db_session, a):
    db_session.expire_all()
    return json.loads(db_session.query(AvaliadorParecer).one().rascunho_json)


# ── o que vai ao modelo ────────────────────────────────────────────────────


def test_entrada_e_so_a_tela_corrigida_sem_a_peca(db_session, empresa, teto):
    a = _pronta_servico(db_session, empresa)
    texto, base = R.entrada(_tela(a), {}, a.descricao)
    assert HORARIO[1] in texto  # o trecho que vai para o parecer
    assert "Não diz em que dias da semana há expediente." in texto  # o que falta
    assert "Em uma linha: " in texto  # a linha da frente
    assert SENTINELA not in texto  # o resto da peça não vai
    assert len(base) == 16
    # uma correção muda o que o modelo leria: a base muda
    servico.recusar_trecho(db_session, a, "D1.01", HORARIO[1], None)
    db_session.commit()
    assert R.entrada(_tela(a), {}, a.descricao)[1] != base
    # o pedido não leva texto aprovado de parecer nenhum (a #31 é o gabarito)
    assert "Localiza" not in R.sistema() and "aluguel" not in R.sistema().lower()
    # o achado não pode só repetir as listas (a falha do formato 2, 17/10)
    assert "O achado não repete as duas listas" in R.sistema()
    # 22/10, rascunho da #31: "raro em peças desse tipo" e "cidade" completando trecho cortado
    assert "não compare com outras peças nem com o mercado" in R.sistema()
    assert "não complete trecho cortado" in R.sistema()


@pytest.mark.parametrize(
    "estraga, motivo",
    [
        (lambda o: o["achados"].pop("A3"), "exatamente os doze"),
        (lambda o: o.update(ordem=" "), "sem a frase da ordem"),
        (lambda o: o["achados"].update(P2="O P2.03 não aparece."), "código no texto"),
        (lambda o: o["achados"].update(P2="Nenhuma das sete tem resposta."), "contagem"),
        (lambda o: o["achados"].update(P2="Diz pouco — quase nada."), "travessão"),
        (lambda o: o["achados"].update(P2="x" * 701), "700 caracteres"),
    ],
)
def test_validacao_do_rascunho(estraga, motivo):
    o = _bom()
    estraga(o)
    with pytest.raises(RespostaInvalida, match=motivo):
        R.validar(o)
    assert R.validar(_bom())["P1"] == "Achado do modelo para a."


# ── preencher, passar, Word ────────────────────────────────────────────────


def test_rascunho_so_preenche_em_branco_e_o_word_espera_a_pessoa(db_session, empresa, teto):
    a = _pronta_servico(db_session, empresa)
    servico.salvar_parecer(db_session, a, "empresa_da_peca", "Empresa da Peça SA", None)
    servico.salvar_parecer(db_session, a, "D2", "Escrito pela pessoa.", None)
    db_session.commit()
    cli = Modelo(_bom())
    preenchidos = servico.rascunhar_parecer(db_session, a, None, client=cli)
    db_session.commit()
    assert "D2" not in preenchidos and len(preenchidos) == 12  # a ordem e onze achados
    textos = servico.textos_do_parecer(a)
    assert textos["achados"]["D2"] == "Escrito pela pessoa."  # o da pessoa não muda
    assert textos["achados"]["P1"] == "Achado do modelo para a."
    assert textos["ordem"].startswith("A peça rompe")
    rj = _rj(db_session, a)
    assert set(rj) == set(preenchidos) and {x["estado"] for x in rj.values()} == {"pendente"}
    p = db_session.query(AvaliadorParecer).one()
    assert p.rascunho_custo_usd > 0 and p.rascunho_versao == R.VERSAO
    # o gasto entra no teto mensal da empresa
    assert servico.gasto_do_mes(db_session, empresa.id) == pytest.approx(
        a.custo_usd + p.rascunho_custo_usd + p.verificacao_custo_usd
    )
    # o Word espera a pessoa passar por cada campo
    m = _montar(a)
    assert m["falta"]["rascunho"] == 12
    assert "A ordem: passe pelo rascunho do modelo (edite ou aceite como está)." in m["pendencias"]
    # editar e aceitar: os dois valem, e fica guardado qual foi
    servico.salvar_parecer(db_session, a, "P1", "Corrigido pela pessoa.", None)
    for c in [x for x in preenchidos if x != "P1"]:
        servico.aceitar_rascunho(db_session, a, c, None)
    db_session.commit()
    rj = _rj(db_session, a)
    assert rj["P1"]["estado"] == "editado" and rj["P1"]["rascunho"] == "Achado do modelo para a."
    assert rj["A3"]["estado"] == "aceito"
    assert _montar(a)["pendencias"] == []
    # campo todo escrito: o rascunho não roda de novo
    with pytest.raises(AvaliacaoRecusada, match="só preenche campo em branco"):
        servico.rascunhar_parecer(db_session, a, None, client=Modelo())


def test_tela_mudou_depois_do_rascunho_pede_conferencia(db_session, empresa, teto):
    a = _pronta_servico(db_session, empresa)
    servico.salvar_parecer(db_session, a, "empresa_da_peca", "Empresa da Peça SA", None)
    servico.rascunhar_parecer(db_session, a, None, client=Modelo(_bom()))
    servico.salvar_parecer(db_session, a, "A1", "Editado antes da correção.", None)
    for c in ["ordem", *SUBS]:
        if c != "A1":
            servico.aceitar_rascunho(db_session, a, c, None)
    db_session.commit()
    assert _montar(a)["pendencias"] == []
    servico.recusar_trecho(db_session, a, "D1.01", HORARIO[1], None)  # muda a tela
    db_session.commit()
    estado = P.estado_do_rascunho(_tela(a), servico.textos_do_parecer(a))
    assert estado["D1"] == "mudou" and estado["A1"] == "editado"  # o editado é da pessoa
    pend = _montar(a)["pendencias"]
    assert (
        "Acessibilidade: a tela mudou depois do rascunho; "
        "confira de novo (edite ou aceite como está)." in pend
    )
    servico.aceitar_rascunho(db_session, a, "D1", None)
    db_session.commit()
    assert P.estado_do_rascunho(_tela(a), servico.textos_do_parecer(a))["D1"] == "aceito"


def test_falha_grava_o_gasto_e_nao_escreve_nada(db_session, empresa, teto):
    a = _pronta_servico(db_session, empresa)
    cli = Modelo("sem json", _bom(ordem=""))  # as duas tentativas inválidas
    with pytest.raises(AvaliacaoRecusada) as e:
        servico.rascunhar_parecer(db_session, a, None, client=cli)
    assert str(e.value).startswith("O rascunho não saiu (RespostaInvalida). Nada foi escrito")
    assert ", fica registrado." in str(e.value) and "US$ 0," in str(e.value)
    db_session.commit()
    assert len(cli.chamadas) == 2
    p = db_session.query(AvaliadorParecer).one()
    assert p.rascunho_custo_usd > 0  # o gasto conta mesmo na falha
    assert p.ordem == "" and json.loads(p.achados_json) == {} and p.rascunho_json == "{}"


def test_teto_recusa_antes_de_chamar(db_session, empresa, monkeypatch):
    config_avaliador(monkeypatch, AVALIADOR_TETO_MENSAL_USD=10.0)
    a = _pronta_servico(db_session, empresa)
    config_avaliador(monkeypatch, AVALIADOR_TETO_MENSAL_USD=a.custo_usd + 0.001)
    cli = Modelo(_bom())
    with pytest.raises(AvaliacaoRecusada, match="teto mensal"):
        servico.rascunhar_parecer(db_session, a, None, client=cli)
    assert cli.chamadas == []


def test_marca_sem_conferencia_bloqueia_o_rascunho(db_session, empresa, teto):
    a = _pronta_servico(db_session, empresa)
    g = json.loads(a.itens_json)
    m = next(m for m in g["marcas"] if m["codigo"] == "P1.01")
    m["esta"] = True
    m["evidencias"] = [{"pagina": 1, "trecho": "inventado", "conferido": False}]
    a.itens_json = json.dumps(g)
    db_session.commit()
    cli = Modelo(_bom())
    with pytest.raises(AvaliacaoRecusada, match="resolva as marcas sem conferência"):
        servico.rascunhar_parecer(db_session, a, None, client=cli)
    assert cli.chamadas == []


def test_apagar_leitura_tira_o_texto_do_rascunho_e_deixa_o_gasto(db_session, empresa, teto):
    a = _pronta_servico(db_session, empresa)
    servico.rascunhar_parecer(db_session, a, None, client=Modelo(_bom()))
    db_session.commit()
    servico.apagar_leitura(a)
    db_session.commit()
    p = db_session.query(AvaliadorParecer).one()
    assert p.rascunho_json == "{}" and p.rascunho_custo_usd > 0


# ── tela ───────────────────────────────────────────────────────────────────


def test_tela_do_rascunho(client_loyall, db_session, empresa, teto, monkeypatch):
    aid = _pronta(client_loyall, db_session, empresa)
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert "Rascunhar a ordem e 12 achados em branco" in html
    assert "custo de no máximo US$ " in html  # o custo vem antes do clique
    cli = Modelo(_bom())
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: cli)
    html = client_loyall.post(_url(empresa, f"/{aid}/parecer/rascunho")).get_data(as_text=True)
    assert len(cli.chamadas) == 1
    assert html.count("rascunho do modelo, não conferido") == 13
    assert "Achado do modelo para a." in html and "Rascunhar" not in html
    assert "13 rascunhos para passar" in html
    # o subpilar fechado não diz "achado escrito" enquanto o rascunho não foi passado
    p1 = html.split('<details data-subpilar="P1"', 1)[1].split("</summary>", 1)[0]
    assert "rascunho para passar" in p1 and "achado escrito" not in p1
    # editar: o rótulo volta na hora, fora da área trocada
    r = client_loyall.post(
        _url(empresa, f"/{aid}/parecer"), data={"campo": "P1", "texto": "Da pessoa."}
    ).get_data(as_text=True)
    assert 'id="rascunho-rotulo-P1" hx-swap-oob="true"' in r and "editado por você" in r
    html = client_loyall.post(
        _url(empresa, f"/{aid}/parecer/aceitar"), data={"campo": "ordem"}
    ).get_data(as_text=True)
    assert "rascunho aceito como está" in html and "11 rascunhos para passar" in html
    client_loyall.post(
        _url(empresa, f"/{aid}/parecer"), data={"campo": "empresa_da_peca", "texto": "E2 SA"}
    )
    a = db_session.get(AvaliadorAnalise, aid)
    for c in SUBS:
        if c != "P1":
            client_loyall.post(_url(empresa, f"/{aid}/parecer/aceitar"), data={"campo": c})
    r = client_loyall.get(_url(empresa, f"/{aid}/parecer.docx"))
    assert r.status_code == 200
    from docx import Document

    texto = "\n".join(x.text for x in Document(io.BytesIO(r.data)).paragraphs)
    assert "Da pessoa." in texto and "Achado do modelo para b." in texto
    assert a is not None
