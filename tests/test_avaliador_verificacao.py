"""A verificação dos trechos ligada no app (24/10): roda no fim da leitura nova, grava no
parecer, tira do Word o que é navegação, lista ou dois-pontos sem conteúdo, mostra na tela com
o motivo, a pessoa devolve, o Word espera os pendentes, e as peças de medição ficam fora.
Peça inventada (a do _pptx), modelo dublado, sem gasto."""

from __future__ import annotations

import io

import pytest

from src.avaliador import servico
from src.avaliador.servico import AvaliacaoRecusada
from src.models.avaliador import CORRECAO_DEVOLUCAO, AvaliadorCorrecao, AvaliadorParecer
from src.models.empresa import Empresa
from tests.test_avaliador_parecer import _montar, _preencher
from tests.test_avaliador_servico import (
    HORARIO,
    REFERENCIA,
    Dublê,
    _criar,
    _leitura,
    _rodar,
    config_avaliador,
    resposta_v25,
)

# a frase de referência do _pptx sai do Word como navegação (só para o teste)
SAI_REFERENCIA = {"referência no setor": "navegacao"}


@pytest.fixture
def empresa(db_session):
    e = Empresa(nome="Empresa Aval verificação")
    db_session.add(e)
    db_session.commit()
    return e


@pytest.fixture
def teto(monkeypatch):
    config_avaliador(monkeypatch, AVALIADOR_TETO_MENSAL_USD=10.0)


def _tela(a):
    return servico.organizar_marcas(servico.carregar_regua(), a, servico.correcoes_de(a))


def _marca(tela, codigo):
    return next(x for x in servico._linhas_da_tela(tela) if x["codigo"] == codigo)


def _lida(db_session, empresa, presentes=None, exclui=None):
    cli = Dublê([resposta_v25(presentes)], exclui=exclui)
    return _rodar(db_session, _criar(db_session, empresa), cli), cli


def test_roda_no_fim_da_leitura_e_grava_no_parecer_com_o_custo_no_teto(db_session, empresa, teto):
    a, cli = _lida(db_session, empresa, exclui=SAI_REFERENCIA)
    assert len(cli.chamadas) == len(_leitura(cli.chamadas)) + 1  # uma chamada de verificação
    p = db_session.query(AvaliadorParecer).one()
    assert p.verificacao_custo_usd > 0 and p.verificacao_em is not None
    assert servico.gasto_do_mes(db_session, empresa.id) == pytest.approx(
        a.custo_usd + p.verificacao_custo_usd
    )
    tela = _tela(a)
    assert tela["verificacao"] == {"isenta": False, "pendentes": 0, "feita": True}
    # o mesmo trecho em duas marcas é verificado uma vez: dois textos, não três trechos
    assert '"[3]' not in cli.chamadas[-1]["messages"][0]["content"][0]["text"]


def test_marca_que_fica_sem_trecho_vira_nao_esta_em_todo_lugar(db_session, empresa, teto):
    a, _ = _lida(db_session, empresa, exclui=SAI_REFERENCIA)
    tela = _tela(a)
    a1 = _marca(tela, "A1.02")
    assert a1["estado"] == servico.MARCA_NAO_ESTA and a1["evidencias"] == []
    assert a1["excluidas"][0]["etiqueta"] == "não entra no Word: é botão ou menu do site"
    m = _montar(a)
    a1_word = next(s for pl in m["pilares"] for s in pl["subpilares"] if s["codigo"] == "A1")
    assert a1_word["diz"] == [] and a1_word["custa"]  # vazio: ganha o "por que custa"
    assert servico.frase_da_marca(a1["texto"], False) in a1_word["nao_diz"]
    assert not any("referência no setor" in t for t in a1_word["diz"])
    # o D1 não foi tocado
    assert _marca(tela, "D1.01")["estado"] == servico.MARCA_ESTA


def test_marca_com_outro_trecho_continua_esta_mesmo_que_ele_nao_va_ao_word(
    db_session, empresa, teto
):
    # D1.01 tem dois trechos (o do horário e o da referência); só o da referência sai
    a, _ = _lida(
        db_session, empresa, presentes={"D1.01": [HORARIO, REFERENCIA], "A1.02": REFERENCIA},
        exclui=SAI_REFERENCIA,
    )  # fmt: skip
    d1 = _marca(_tela(a), "D1.01")
    assert d1["estado"] == servico.MARCA_ESTA
    assert len(d1["evidencias"]) == 1 and len(d1["excluidas"]) == 1


def test_devolver_ao_word_fica_gravado_e_desfazer_tira_de_novo(db_session, empresa, teto):
    a, _ = _lida(db_session, empresa, exclui=SAI_REFERENCIA)
    trecho = _marca(_tela(a), "A1.02")["excluidas"][0]["trecho"]
    servico.devolver_trecho(db_session, a, "A1.02", trecho, None)
    db_session.commit()
    a1 = _marca(_tela(a), "A1.02")
    assert a1["estado"] == servico.MARCA_ESTA and a1["excluidas"] == []
    assert a1["evidencias"][0]["devolvido_id"]
    # a medida de uso: quantas exclusões as pessoas desfazem
    devolvidas = db_session.query(AvaliadorCorrecao).filter_by(tipo=CORRECAO_DEVOLUCAO).all()
    assert len(devolvidas) == 1 and devolvidas[0].desfeita_em is None
    servico.desfazer_correcao(db_session, a, devolvidas[0].id)
    db_session.commit()
    assert _marca(_tela(a), "A1.02")["estado"] == servico.MARCA_NAO_ESTA
    with pytest.raises(AvaliacaoRecusada):  # só se devolve o que foi tirado
        servico.devolver_trecho(db_session, a, "D1.01", HORARIO[1], None)


def test_devolucao_nao_marca_a_marca_como_corrigida(db_session, empresa, teto):
    a, _ = _lida(db_session, empresa, exclui=SAI_REFERENCIA)
    trecho = _marca(_tela(a), "A1.02")["excluidas"][0]["trecho"]
    servico.devolver_trecho(db_session, a, "A1.02", trecho, None)
    db_session.commit()
    assert not _marca(_tela(a), "A1.02")["corrigida"]


def test_verificacao_pendente_trava_word_e_rascunho_ate_verificar(
    db_session, empresa, teto, monkeypatch
):
    # a verificação do fim da leitura falha (teto): a leitura fica pronta, a verificação não
    def falha(*a, **k):
        raise AvaliacaoRecusada("teto")

    monkeypatch.setattr(servico, "verificar_trechos", falha)
    a, _ = _lida(db_session, empresa)
    monkeypatch.undo()
    config_avaliador(monkeypatch, AVALIADOR_TETO_MENSAL_USD=10.0)
    assert a.status == "pronta" and _tela(a)["verificacao"]["pendentes"] == 2
    _preencher(db_session, a)
    m = _montar(a)
    assert m["falta"]["verificar"] == 2 and any(
        "Verifique os trechos" in x for x in m["pendencias"]
    )
    with pytest.raises(AvaliacaoRecusada, match="verifique os trechos"):
        servico.rascunhar_parecer(db_session, a, None, client=Dublê())
    assert servico.estimativa_verificacao(a, _tela(a)) > 0
    assert servico.verificar_trechos(db_session, a, None, client=Dublê()) == 2
    db_session.commit()
    assert _tela(a)["verificacao"]["pendentes"] == 0 and _montar(a)["pendencias"] == []
    assert servico.verificar_trechos(db_session, a, None, client=Dublê()) == 0  # nada a fazer


def test_trecho_que_vem_da_correcao_e_verificado_sozinho(db_session, empresa, teto):
    a, _ = _lida(db_session, empresa)
    servico.incluir_trecho(db_session, a, "P1.01", "Proposta comercial para a Empresa X.", None)
    db_session.commit()
    assert _tela(a)["verificacao"]["pendentes"] == 1
    cli = Dublê()
    assert servico.verificar_trechos(db_session, a, None, client=cli) == 1
    assert "[2]" not in cli.chamadas[0]["messages"][0]["content"][0]["text"]  # só o novo


def test_falha_da_verificacao_grava_o_gasto(db_session, empresa, teto, monkeypatch):
    monkeypatch.setattr(servico, "_verificar_no_fim", lambda *a, **k: None)
    a, _ = _lida(db_session, empresa)

    class Quebrado(Dublê):
        def create(self, **kw):
            r = super().create(**kw)
            r.content[0].text = "sem json"
            return r

    with pytest.raises(AvaliacaoRecusada, match="não saiu"):
        servico.verificar_trechos(db_session, a, None, client=Quebrado())
    db_session.commit()
    p = db_session.query(AvaliadorParecer).one()
    assert p.verificacao_custo_usd > 0 and p.verificacao_json in ("{}", "", None)


def test_peca_de_medicao_nao_e_verificada(db_session, empresa, teto, monkeypatch):
    aid = _criar(db_session, empresa)
    monkeypatch.setattr(servico, "PECAS_DE_MEDICAO", frozenset({aid}))
    cli = Dublê([resposta_v25()], exclui=SAI_REFERENCIA)
    a = _rodar(db_session, aid, cli)
    assert len(cli.chamadas) == len(_leitura(cli.chamadas))  # nenhuma verificação
    tela = _tela(a)
    assert tela["verificacao"] == {"isenta": True, "pendentes": 0, "feita": False}
    assert _marca(tela, "A1.02")["estado"] == servico.MARCA_ESTA  # sai como antes
    with pytest.raises(AvaliacaoRecusada, match="medição"):
        servico.verificar_trechos(db_session, a, None, client=Dublê())


def test_apagar_leitura_limpa_a_verificacao_e_o_gasto_fica(db_session, empresa, teto):
    a, _ = _lida(db_session, empresa, exclui=SAI_REFERENCIA)
    servico.apagar_leitura(a)
    db_session.commit()
    p = db_session.query(AvaliadorParecer).one()
    assert p.verificacao_json == "{}" and p.verificacao_custo_usd > 0


# ── a tela e o Word ─────────────────────────────────────────────────────────


def _url(empresa, resto=""):
    return f"/empresas/{empresa.id}/explorar/avaliador{resto}"


def test_tela_mostra_a_etiqueta_o_botao_de_devolver_e_o_custo(
    client_loyall, db_session, empresa, teto
):
    a, _ = _lida(db_session, empresa, exclui=SAI_REFERENCIA)
    html = client_loyall.get(_url(empresa, f"/{a.id}")).get_data(as_text=True)
    assert "data-excluido" in html and "não entra no Word: é botão ou menu do site" in html
    assert "devolver ao Word" in html and "verificação dos trechos US$" in html
    assert "data-verificar" not in html  # nada pendente


def test_tela_com_pendente_mostra_o_botao_com_o_custo_e_o_word_espera(
    client_loyall, db_session, empresa, teto
):
    a, _ = _lida(db_session, empresa)
    servico.incluir_trecho(db_session, a, "P1.01", "Proposta comercial para a Empresa X.", None)
    _preencher(db_session, a)
    html = client_loyall.get(_url(empresa, f"/{a.id}")).get_data(as_text=True)
    assert "Verificar 1 trecho" in html and "custo de no máximo US$" in html
    r = client_loyall.get(_url(empresa, f"/{a.id}/parecer.docx"))
    assert r.status_code == 409 and "Verifique os trechos" in r.get_data(as_text=True)


def test_word_sai_sem_o_trecho_excluido(client_loyall, db_session, empresa, teto):
    a, _ = _lida(db_session, empresa, exclui=SAI_REFERENCIA)
    _preencher(db_session, a)
    r = client_loyall.get(_url(empresa, f"/{a.id}/parecer.docx"))
    assert r.status_code == 200
    from docx import Document

    texto = "\n".join(x.text for x in Document(io.BytesIO(r.data)).paragraphs)
    assert "referência no setor" not in texto
    assert "segunda a sexta" in texto
    assert servico.frase_da_marca(_marca(_tela(a), "A1.02")["texto"], False) in texto
