"""Serviço do Avaliador com cliente LLM DUBLADO (nenhuma chamada paga) e banco de teste:
gate de custo antes de gastar, processamento idempotente, falha visível, correção de
tipo que só chama o que falta, retenção do texto e housekeeping."""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.avaliador import servico
from src.avaliador.servico import AvaliacaoRecusada
from src.config import Config
from src.models.avaliador import STATUS_FALHOU, STATUS_LENDO, STATUS_PRONTA, AvaliadorAnalise
from src.models.empresa import Empresa

SENTINELA = "SENTINELA-DOCUMENTO-CONFIDENCIAL-9F3A"


def _pptx() -> bytes:
    import io

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


def _resp_pergunta(codigo):
    return {"veredito": "sem_resposta", "evidencias": [], "frase_id": f"L1-{codigo}-01"}


def _resp_p1():
    sem = lambda f: {"veredito": "sem_resposta", "evidencias": [], "frase_id": f}  # noqa: E731
    return {
        "partes": {"escopo": sem("L1-P1a-01"), "prazo": sem("L1-P1b-01"), "fora": sem("L1-P1c-01")},
        "frase_id_em_parte": "EP-P1-01",
        "frase_id_sem_anexo": "L1-P1d_sem_anexo-01",
        "confianca": "media",
    }


class Dublê:
    """Responde pelo CONTEÚDO do prompt (as perguntas rodam em paralelo). Thread-safe."""

    def __init__(self, tipo="institucional", secao=False, discute=False, ruins=(), quebra=()):
        self.tipo, self.secao, self.discute = tipo, secao, discute
        self.ruins, self.quebra = set(ruins), set(quebra)
        self.chamadas = []
        self._lock = threading.Lock()
        self.messages = self

    def perguntas_chamadas(self):
        out = []
        for kw in self.chamadas:
            u = kw["messages"][0]["content"]
            m = re.search(r"Pergunta (\w+): \"", u)
            if "A PERGUNTA P1" in u:
                out.append("P1")
            elif m:
                out.append(m.group(1))
        return out

    def create(self, **kw):
        with self._lock:
            self.chamadas.append(kw)
        u = kw["messages"][0]["content"]
        if "ETAPA 1" in u:
            r = {"tipo": self.tipo, "secao_comercial": self.secao, "discute_preco": self.discute}
        elif "A PERGUNTA P1" in u:
            r = _resp_p1()
        elif "LEITURA DO FIM" in u:
            r = {"leitura": "Padrão de teste."}
        else:
            c = re.search(r"Pergunta (\w+): \"", u).group(1)
            if c in self.quebra:
                raise ConnectionError("rede caiu")
            r = {"veredito": "talvez"} if c in self.ruins else _resp_pergunta(c)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(r))],
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=50,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=1000,
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
    monkeypatch.setattr(Config, "AVALIADOR_TETO_MENSAL_USD", 10.0)


def _criar(db_session, empresa):
    a = servico.criar_analise(db_session, empresa.id, None, "proposta.pptx", _pptx())
    db_session.commit()
    return a.id


def _rodar(db_session, aid, cli):
    servico.processar(aid, client=cli)
    db_session.expire_all()
    return db_session.get(AvaliadorAnalise, aid)


def test_teto_zero_desliga_antes_de_gravar_e_de_gastar(db_session, empresa):
    with pytest.raises(AvaliacaoRecusada, match="desligado"):
        servico.criar_analise(db_session, empresa.id, None, "x.pptx", _pptx())
    assert db_session.query(AvaliadorAnalise).count() == 0


def test_teto_estourado_recusa(db_session, empresa, monkeypatch):
    monkeypatch.setattr(Config, "AVALIADOR_TETO_MENSAL_USD", 0.0001)
    with pytest.raises(AvaliacaoRecusada, match="passaria do teto"):
        servico.criar_analise(db_session, empresa.id, None, "x.pptx", _pptx())


def test_caminho_feliz_institucional(db_session, empresa, teto):
    aid = _criar(db_session, empresa)
    cli = Dublê(tipo="institucional", secao=False, discute=False)
    a = _rodar(db_session, aid, cli)
    assert a.status == STATUS_PRONTA and a.leitura_fim == "Padrão de teste."
    # institucional sem discussão de preço: D1, Pa1, A1, A2, A3 (Pa2 sai pela condicional)
    assert sorted(cli.perguntas_chamadas()) == sorted(["D1", "Pa1", "A1", "A2", "A3"])
    assert len(cli.chamadas) == 1 + 5 + 1
    assert a.custo_usd > 0 and a.tokens_cache_leitura == 7000
    assert [v["codigo"] for v in servico.vereditos_visiveis(servico.carregar_regua(), a)] == [
        "D1",
        "Pa1",
        "A1",
        "A2",
        "A3",
    ]


def test_pergunta_invalida_deixa_falhou_sem_leitura_e_retomar_so_refaz_ela(
    db_session, empresa, teto, caplog
):
    aid = _criar(db_session, empresa)
    with caplog.at_level(logging.WARNING):
        a = _rodar(db_session, aid, Dublê(ruins={"A2"}))
    assert a.status == STATUS_FALHOU and "A2" in a.erro_motivo and a.leitura_fim is None
    assert a.custo_usd > 0  # as duas tentativas da A2 foram cobradas
    assert SENTINELA not in caplog.text and SENTINELA not in (a.erro_motivo or "")
    servico.retomar(a)
    db_session.commit()
    cli = Dublê()
    a = _rodar(db_session, aid, cli)
    assert cli.perguntas_chamadas() == ["A2"]  # só a que faltava; etapa 1 não repete
    assert a.status == STATUS_PRONTA and a.leitura_fim


def test_erro_de_rede_numa_pergunta_nao_descarta_as_outras(db_session, empresa, teto):
    aid = _criar(db_session, empresa)
    a = _rodar(db_session, aid, Dublê(quebra={"Pa1"}))
    res = json.loads(a.resultado_json)
    assert a.status == STATUS_FALHOU and "Pa1" in a.erro_motivo
    assert res["Pa1"]["erro"] == "erro na chamada (ConnectionError)"
    assert all("veredito" in res[c] for c in ("D1", "A1", "A2", "A3"))


def test_corrigir_tipo_chama_so_as_que_faltam_e_refaz_a_leitura(db_session, empresa, teto):
    aid = _criar(db_session, empresa)
    a = _rodar(db_session, aid, Dublê())
    servico.corrigir_tipo(db_session, a, "proposta")
    db_session.commit()
    cli = Dublê()
    a = _rodar(db_session, aid, cli)
    assert sorted(cli.perguntas_chamadas()) == sorted(["P1", "P2", "P3", "D2", "D3", "Pa2", "Pa3"])
    assert a.tipo == "proposta" and a.status == STATUS_PRONTA
    assert "LEITURA DO FIM" in cli.chamadas[-1]["messages"][0]["content"]
    # P1 sem seção comercial: a tela pergunta o anexo
    p1 = servico.vereditos_visiveis(servico.carregar_regua(), a)[0]
    assert p1["codigo"] == "P1" and p1["pergunta_anexo"] is True


def test_resposta_do_anexo_sem_chamada_e_leitura_refeita_se_o_p1_mudar(db_session, empresa, teto):
    aid = _criar(db_session, empresa)
    a = _rodar(db_session, aid, Dublê(tipo="proposta"))
    p1 = servico.vereditos_visiveis(servico.carregar_regua(), a)[0]
    assert p1["veredito"] == "sem_resposta"  # escopo/prazo/fora todos sem resposta
    # "está em anexo": preço continua fora → P1 não muda → leitura fica
    assert servico.responder_anexo(a, True) is False and a.leitura_fim
    # "não há anexo": preço entra como sem resposta → P1 continua sem resposta
    assert servico.responder_anexo(a, False) is False
    p1 = servico.vereditos_visiveis(servico.carregar_regua(), a)[0]
    assert p1["veredito"] == "sem_resposta" and p1["pergunta_anexo"] is False


def test_concluir_apaga_o_texto_e_depois_nao_se_rele(db_session, empresa, teto):
    aid = _criar(db_session, empresa)
    a = _rodar(db_session, aid, Dublê())
    servico.concluir(a)
    db_session.commit()
    assert a.texto_json is None and a.texto_apagado_motivo == "concluida"
    assert a.texto_apagado_em is not None and json.loads(a.resultado_json)  # vereditos ficam
    with pytest.raises(AvaliacaoRecusada, match="já foi apagado"):
        servico.retomar(a)


def test_housekeeping_marca_orfa_e_apaga_texto_sem_uso(db_session, empresa, teto):
    agora = datetime.utcnow()
    orfa = db_session.get(AvaliadorAnalise, _criar(db_session, empresa))
    orfa.status, orfa.atualizado_em = STATUS_LENDO, agora - timedelta(minutes=30)
    velha = db_session.get(AvaliadorAnalise, _criar(db_session, empresa))
    velha.status, velha.usado_em = STATUS_PRONTA, agora - timedelta(days=8)
    nova = db_session.get(AvaliadorAnalise, _criar(db_session, empresa))
    nova.status, nova.usado_em = STATUS_PRONTA, agora - timedelta(days=6)
    db_session.commit()
    r = servico.housekeeping(db_session, agora)
    assert r == {"orfas": 1, "textos_apagados": 1}
    assert orfa.status == STATUS_FALHOU and "reinício" in orfa.erro_motivo
    assert velha.texto_json is None and velha.texto_apagado_motivo == "expirada"
    assert nova.texto_json is not None
    assert servico.housekeeping(db_session, agora) == {"orfas": 0, "textos_apagados": 0}


def test_retencao_segue_a_constante_de_config(db_session, empresa, teto, monkeypatch):
    monkeypatch.setattr(Config, "AVALIADOR_DIAS_RETENCAO_TEXTO", 2)
    a = db_session.get(AvaliadorAnalise, _criar(db_session, empresa))
    a.status, a.usado_em = STATUS_PRONTA, datetime.utcnow() - timedelta(days=3)
    db_session.commit()
    assert servico.housekeeping(db_session)["textos_apagados"] == 1


def test_nao_ha_anexo_que_muda_o_p1_reabre_a_leitura_do_fim(db_session, empresa, teto):
    aid = _criar(db_session, empresa)
    a = _rodar(db_session, aid, Dublê(tipo="proposta"))
    res = json.loads(a.resultado_json)
    ok = {"veredito": "respondida", "evidencias": [], "frase_id": None, "complemento": None}
    res["P1"]["partes"].update(escopo=ok, prazo=ok, fora=ok)
    a.resultado_json = json.dumps(res)
    assert servico.vereditos_visiveis(servico.carregar_regua(), a)[0]["veredito"] == "respondida"
    assert servico.responder_anexo(a, False) is True  # preço entra aberto → em parte
    assert a.leitura_fim is None and a.status == "pendente"
    p1 = servico.vereditos_visiveis(servico.carregar_regua(), a)[0]
    assert p1["veredito"] == "em_parte" and p1["frase_id"] == "EP-P1-01"
    assert p1["frase_id_preco"] == "L1-P1d_sem_anexo-01"


def test_comando_do_watchdog_roda(client, empresa):
    r = client.application.test_cli_runner().invoke(args=["avaliador-housekeeping"])
    assert r.exit_code == 0, r.output
    assert "0 interrompida(s)" in r.output and "7 dias sem uso" in r.output
