"""Serviço do Avaliador com cliente LLM DUBLADO (nenhuma chamada paga) e banco de teste."""

from __future__ import annotations

import io
import json
import logging
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.avaliador import servico
from src.avaliador.servico import AvaliacaoRecusada
from src.models.avaliador import STATUS_FALHOU, STATUS_LENDO, STATUS_PRONTA, AvaliadorAnalise
from src.models.empresa import Empresa

SENTINELA = "SENTINELA-DOCUMENTO-CONFIDENCIAL-9F3A"
DESCRICAO = "Proposta comercial para renovar o contrato de um cliente de TI"


def config_avaliador(monkeypatch, **valores):
    """Troca valores de config SÓ para o serviço do Avaliador (o único que os lê).
    Patch na instância devolvida, não na classe Config — imune a outros testes."""
    from src.config import get_config as real

    def fake():
        c = real()
        for k, v in valores.items():
            setattr(c, k, v)
        return c

    monkeypatch.setattr(servico, "get_config", fake)


def _pptx() -> bytes:
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    for texto in (
        f"Proposta comercial para a Empresa X. {SENTINELA}",
        "Atendimento de segunda a sexta das 8h às 18h pelo gerente de conta.",
        "Somos referência no setor há vinte anos, com clientes em todo o país.",
    ):
        s = prs.slides.add_slide(prs.slide_layouts[6])
        s.shapes.add_textbox(Inches(1), Inches(1), Inches(7), Inches(2)).text_frame.text = texto
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def resposta_ok():
    return {
        "resumo": "Padrão de teste.",
        "itens": [
            {
                "subpilar": "D1",
                "tipo": "forte",
                "texto": "Horário declarado.",
                "evidencias": [{"pagina": 2, "trecho": "segunda a sexta das 8h às 18h"}],
            },
            {"subpilar": "D1", "tipo": "falta", "texto": "Rota fora do horário.", "evidencias": []},
            {
                "subpilar": "A1",
                "tipo": "melhorar",
                "texto": "Referência afirmada sem quem a cite.",
                "evidencias": [{"pagina": 3, "trecho": "Somos referência no setor há vinte anos"}],
            },
        ],
    }


class Dublê:
    def __init__(self, respostas=None, quebra=False):
        self.respostas = list(respostas or [resposta_ok()])
        self.quebra = quebra
        self.chamadas = []
        self.messages = self

    def create(self, **kw):
        self.chamadas.append(kw)
        if self.quebra:
            raise ConnectionError("rede caiu")
        r = self.respostas.pop(0)
        texto = r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=texto)],
            usage=SimpleNamespace(
                input_tokens=3000,
                output_tokens=800,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
            ),
        )


@pytest.fixture
def empresa(db_session):
    e = Empresa(nome="Empresa Teste")
    db_session.add(e)
    db_session.commit()
    return e


@pytest.fixture
def teto(monkeypatch):
    config_avaliador(monkeypatch, AVALIADOR_TETO_MENSAL_USD=10.0)


def _criar(db_session, empresa, **kw):
    if not kw:
        kw = {"nome": "proposta.pptx", "dados": _pptx()}
    a = servico.criar_analise(db_session, empresa.id, None, DESCRICAO, **kw)
    db_session.commit()
    return a.id


def _rodar(db_session, aid, cli):
    servico.processar(aid, client=cli)
    db_session.expire_all()
    return db_session.get(AvaliadorAnalise, aid)


def test_teto_zero_desliga_antes_de_gravar(db_session, empresa):
    with pytest.raises(AvaliacaoRecusada, match="desligado"):
        servico.criar_analise(db_session, empresa.id, None, DESCRICAO, dados=_pptx())
    assert db_session.query(AvaliadorAnalise).count() == 0


def test_teto_estourado_recusa(db_session, empresa, monkeypatch):
    config_avaliador(monkeypatch, AVALIADOR_TETO_MENSAL_USD=0.0001)
    with pytest.raises(AvaliacaoRecusada, match="passaria do teto"):
        servico.criar_analise(db_session, empresa.id, None, DESCRICAO, dados=_pptx())


def test_descricao_e_uma_entrada_sao_obrigatorias(db_session, empresa, teto):
    with pytest.raises(AvaliacaoRecusada, match="o que é a peça"):
        servico.criar_analise(db_session, empresa.id, None, "  ", dados=_pptx())
    with pytest.raises(AvaliacaoRecusada, match="um dos dois"):
        servico.criar_analise(db_session, empresa.id, None, DESCRICAO)
    with pytest.raises(AvaliacaoRecusada, match="um dos dois"):
        servico.criar_analise(
            db_session, empresa.id, None, DESCRICAO, dados=_pptx(), texto="x" * 50
        )


def test_caminho_feliz_arquivo(db_session, empresa, teto):
    aid = _criar(db_session, empresa)
    cli = Dublê()
    a = _rodar(db_session, aid, cli)
    assert a.status == STATUS_PRONTA and a.resumo == "Padrão de teste."
    assert len(cli.chamadas) == 1  # UMA chamada
    assert DESCRICAO in cli.chamadas[0]["messages"][0]["content"]
    assert a.custo_usd > 0 and a.origem == "arquivo" and a.formato == "pptx"
    org = servico.organizar(servico.carregar_regua(), a)
    disp = org[1]["subpilares"][0]  # Disponibilidade → D1
    assert disp["subpilar"].codigo == "D1" and len(disp["por_tipo"]["forte"]) == 1
    assert org[0]["subpilares"][0]["vazio"] is True  # P1 sem observação, declarado


def test_texto_colado_usa_a_biblioteca_de_conversa(db_session, empresa, teto):
    conversa = "Cliente: com quem eu falo se der problema?\nVendedor: fica tranquilo, é rápido."
    aid = _criar(db_session, empresa, texto=conversa)
    cli = Dublê([{"resumo": "Faltou nome e prazo.", "itens": []}])
    a = _rodar(db_session, aid, cli)
    assert a.status == STATUS_PRONTA and a.origem == "texto" and a.formato == "texto"
    assert "Ele perguntou com quem fala" in cli.chamadas[0]["system"]
    assert "=== TEXTO COLADO ===" in cli.chamadas[0]["messages"][0]["content"]


def test_falha_fica_visivel_sem_vazar_texto_e_tentar_de_novo_funciona(
    db_session, empresa, teto, caplog
):
    aid = _criar(db_session, empresa)
    with caplog.at_level(logging.WARNING):
        a = _rodar(db_session, aid, Dublê(quebra=True))
    assert a.status == STATUS_FALHOU and a.erro_motivo == "leitura: ConnectionError"
    assert SENTINELA not in caplog.text
    servico.refazer(db_session, a)
    db_session.commit()
    a = _rodar(db_session, aid, Dublê())
    assert a.status == STATUS_PRONTA


def test_resposta_invalida_duas_vezes_cobra_e_falha(db_session, empresa, teto):
    aid = _criar(db_session, empresa)
    a = _rodar(db_session, aid, Dublê(["lixo", "lixo"]))
    assert a.status == STATUS_FALHOU and "RespostaInvalida" in a.erro_motivo
    assert a.tokens_in == 6000 and a.custo_usd > 0


def test_refazer_com_nova_descricao(db_session, empresa, teto):
    aid = _criar(db_session, empresa)
    a = _rodar(db_session, aid, Dublê())
    servico.refazer(db_session, a, "Apresentação institucional para um evento do setor")
    db_session.commit()
    cli = Dublê()
    a = _rodar(db_session, aid, cli)
    assert a.descricao.startswith("Apresentação institucional")
    assert "Apresentação institucional" in cli.chamadas[0]["messages"][0]["content"]
    assert a.tokens_in == 6000  # as duas leituras somam


def test_concluir_apaga_o_texto_e_depois_nao_se_rele(db_session, empresa, teto):
    aid = _criar(db_session, empresa)
    a = _rodar(db_session, aid, Dublê())
    servico.concluir(a)
    db_session.commit()
    assert a.texto_json is None and a.texto_apagado_motivo == "concluida"
    assert a.resumo and json.loads(a.itens_json)  # resultado fica
    with pytest.raises(AvaliacaoRecusada, match="já foi apagado"):
        servico.refazer(db_session, a)


def test_housekeeping_marca_orfa_e_apaga_texto_sem_uso(db_session, empresa, teto):
    agora = datetime.utcnow()
    orfa = db_session.get(AvaliadorAnalise, _criar(db_session, empresa))
    orfa.status, orfa.atualizado_em = STATUS_LENDO, agora - timedelta(minutes=30)
    velha = db_session.get(AvaliadorAnalise, _criar(db_session, empresa))
    velha.status, velha.usado_em = STATUS_PRONTA, agora - timedelta(days=8)
    nova = db_session.get(AvaliadorAnalise, _criar(db_session, empresa))
    nova.status, nova.usado_em = STATUS_PRONTA, agora - timedelta(days=6)
    db_session.commit()
    assert servico.housekeeping(db_session, agora) == {"orfas": 1, "textos_apagados": 1}
    assert orfa.status == STATUS_FALHOU and "reinício" in orfa.erro_motivo
    assert velha.texto_json is None and velha.texto_apagado_motivo == "expirada"
    assert nova.texto_json is not None
    assert servico.housekeeping(db_session, agora) == {"orfas": 0, "textos_apagados": 0}


def test_retencao_segue_a_constante_de_config(db_session, empresa, monkeypatch):
    config_avaliador(monkeypatch, AVALIADOR_TETO_MENSAL_USD=10.0, AVALIADOR_DIAS_RETENCAO_TEXTO=2)
    a = db_session.get(AvaliadorAnalise, _criar(db_session, empresa))
    a.status, a.usado_em = STATUS_PRONTA, datetime.utcnow() - timedelta(days=3)
    db_session.commit()
    assert servico.housekeeping(db_session)["textos_apagados"] == 1


def test_comando_do_watchdog_roda(client, empresa):
    r = client.application.test_cli_runner().invoke(args=["avaliador-housekeeping"])
    assert r.exit_code == 0, r.output
    assert "0 interrompida(s)" in r.output and "7 dias sem uso" in r.output


def test_modo_por_pilar_grava_versao_e_soma_o_custo(db_session, empresa, monkeypatch):
    from src.avaliador import motor

    config_avaliador(monkeypatch, AVALIADOR_TETO_MENSAL_USD=10.0, AVALIADOR_MODO="por_pilar")
    aid = _criar(db_session, empresa)
    assert db_session.get(AvaliadorAnalise, aid).prompt_versao == motor.PROMPT_VERSAO_POR_PILAR
    resp = [{"itens": []}] * 4 + [{"resumo": "Resumo por pilar."}]
    cli = Dublê(resp)
    _rodar(db_session, aid, cli)
    db_session.expire_all()
    a = db_session.get(AvaliadorAnalise, aid)
    assert a.status == STATUS_PRONTA and a.resumo == "Resumo por pilar."
    assert len(cli.chamadas) == 5 and a.tokens_in == 15000 and a.custo_usd > 0


def test_modo_desconhecido_recusa_antes_de_gravar(db_session, empresa, monkeypatch):
    config_avaliador(monkeypatch, AVALIADOR_TETO_MENSAL_USD=10.0, AVALIADOR_MODO="duas")
    with pytest.raises(AvaliacaoRecusada, match="AVALIADOR_MODO"):
        _criar(db_session, empresa)
    assert db_session.query(AvaliadorAnalise).count() == 0


def test_por_pilar_sem_resumo_fica_pronta_com_motivo(db_session, empresa, monkeypatch):
    config_avaliador(monkeypatch, AVALIADOR_TETO_MENSAL_USD=10.0, AVALIADOR_MODO="por_pilar")
    aid = _criar(db_session, empresa)
    _rodar(db_session, aid, Dublê([{"itens": []}] * 4 + ["x", "y"]))
    db_session.expire_all()
    a = db_session.get(AvaliadorAnalise, aid)
    assert a.status == STATUS_PRONTA and a.resumo is None
    assert a.erro_motivo == "resumo: RespostaInvalida" and a.custo_usd > 0
