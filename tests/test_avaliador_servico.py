"""Serviço do Avaliador com cliente LLM DUBLADO (nenhuma chamada paga) e banco de teste."""

from __future__ import annotations

import io
import json
import logging
import re
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


def veredito_de(cod, ver="nao", trecho=None, pagina=1, onde=None, deveria="Dizer como e quando."):
    return {
        "subpilar": cod,
        "veredito": ver,
        "onde": onde or ("Esta conversa não existe na peça." if ver == "nao" else "Está na peça."),
        "deveria_ter": "" if ver == "sim" and deveria == "Dizer como e quando." else deveria,
        "evidencias": [{"pagina": pagina, "trecho": trecho}] if trecho else [],
    }


def resposta_v20(vereditos=None, situar=None, lastro="Padrão de teste. Comece pela Precisão."):
    """Leitura no formato 2, dublada: D1 "sim" e A1 "parcial" com trecho da peça do
    _pptx(), os outros dez "nao". ``vereditos`` troca subpilares; ``lastro=None`` faz a
    etapa final responder sem JSON (falha)."""
    from src.api.painel import SUBPILARES_ORDEM

    ver = {c: veredito_de(c) for c in SUBPILARES_ORDEM}
    ver["D1"] = veredito_de(
        "D1", "sim", "segunda a sexta das 8h às 18h", 2, onde="Horário declarado."
    )
    ver["A1"] = veredito_de(
        "A1",
        "parcial",
        "Somos referência no setor há vinte anos",
        3,
        onde="Referência afirmada sem quem a cite.",
        deveria="Quem cita a empresa como referência.",
    )
    ver.update(vereditos or {})
    sit = {
        "tipo_peca": "Proposta comercial.",
        "leitor": "Quem decide sozinho.",
        "situacao": "Lida antes da reunião.",
        "consequencia_cobertura": "",
        "achados": [],
        "contradicoes": [],
    }
    sit.update(situar or {})
    return {"v20": True, "situar": sit, "vereditos": ver, "lastro": lastro}


class Dublê:
    def __init__(self, respostas=None, quebra=False):
        self.respostas = list(respostas or [resposta_v20()])
        self.quebra = quebra
        self.chamadas = []
        self.messages = self

    def create(self, **kw):
        self.chamadas.append(kw)
        if self.quebra:
            raise ConnectionError("rede caiu")
        conteudo = kw["messages"][0]["content"]
        r = self.respostas[0]
        if isinstance(conteudo, list) and isinstance(r, dict) and r.get("v20"):
            # formato 2: responde pela etapa pedida no fim da mensagem; a resposta inteira
            # é consumida na etapa final válida (a inválida se repete na nova tentativa)
            pedido = conteudo[-1]["text"]
            if pedido.startswith("ETAPA 1"):
                r = r["situar"]
            elif pedido.startswith("ETAPA: A PEÇA INTEIRA"):
                r = {k: r["situar"][k] for k in ("achados", "contradicoes")}
            elif pedido.startswith("ETAPA FINAL"):
                if r["lastro"] is None:
                    r = "sem json"  # etapa final inválida: a leitura fica sem o texto
                else:
                    r = {"lastro": r["lastro"]}
                    self.respostas.pop(0)
            else:
                cods = re.search(r"subpilares ([A-Za-z0-9, ]+)\.", pedido).group(1).split(", ")
                r = {"vereditos": [r["vereditos"][c] for c in cods]}
        elif isinstance(conteudo, list) and isinstance(r, dict) and "resumo" in r and "itens" in r:
            # modo por pilar (o padrão): a mesma resposta completa, fatiada por pilar; o
            # pedido do resumo devolve só o resumo e consome a resposta
            pedido = conteudo[-1]["text"]
            if 'escreva só o "resumo"' in pedido:
                self.respostas.pop(0)
                r = {"resumo": r["resumo"]}
            else:
                cods = re.search(r"subpilares ([A-Za-z0-9, ]+)\.", pedido).group(1).split(", ")
                r = {"itens": [i for i in r["itens"] if i["subpilar"] in cods]}
        else:
            self.respostas.pop(0)
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
    with pytest.raises(AvaliacaoRecusada, match="um só"):
        servico.criar_analise(db_session, empresa.id, None, DESCRICAO)
    with pytest.raises(AvaliacaoRecusada, match="um só"):
        servico.criar_analise(
            db_session, empresa.id, None, DESCRICAO, dados=_pptx(), texto="x" * 50
        )


def test_caminho_feliz_arquivo(db_session, empresa, teto):
    aid = _criar(db_session, empresa)
    cli = Dublê()
    a = _rodar(db_session, aid, cli)
    assert a.status == STATUS_PRONTA and a.resumo is None and a.erro_motivo is None
    assert a.prompt_versao == "avaliador-v21-veredito"
    assert len(cli.chamadas) == 7  # situar, uma por pilar, achados e o Lastro
    assert DESCRICAO in cli.chamadas[0]["messages"][0]["content"][0]["text"]
    assert a.custo_usd > 0 and a.origem == "arquivo" and a.formato == "pptx"
    assert servico.formato_da_leitura(a) == servico.FORMATO_VEREDITO
    org = servico.organizar_veredito(servico.carregar_regua(), a)
    assert org["placar"] == {"sim": 1, "parcial": 1, "nao": 10}
    d1 = org["pilares"][1]["linhas"][0]  # Disponibilidade → D1
    assert d1["subpilar"].codigo == "D1" and d1["veredito"] == "sim"
    assert d1["evidencias"][0]["conferido"] and d1["evidencias"][0]["pagina_encontrada"] == 2
    assert org["lastro"]["texto"] == "Padrão de teste. Comece pela Precisão."
    assert org["lastro"]["ponto_de_partida"] == "Precisão" and not org["lastro"]["texto_diverge"]
    assert [x["subpilar"].codigo for x in org["vagas"]][:3] == ["P1", "P2", "P3"]
    assert org["cobertura"][0] == "Lidas 3 páginas."


def test_texto_colado_usa_a_biblioteca_de_conversa(db_session, empresa, teto):
    conversa = "Cliente: com quem eu falo se der problema?\nVendedor: fica tranquilo, é rápido."
    aid = _criar(db_session, empresa, texto=conversa)
    cli = Dublê()
    a = _rodar(db_session, aid, cli)
    assert a.status == STATUS_PRONTA and a.origem == "texto" and a.formato == "texto"
    assert "Ele perguntou com quem fala" in cli.chamadas[0]["system"]
    assert "=== TEXTO COLADO ===" in cli.chamadas[0]["messages"][0]["content"][0]["text"]


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
    assert "Apresentação institucional" in cli.chamadas[0]["messages"][0]["content"][0]["text"]
    assert a.tokens_in == 42000  # as duas leituras somam (7 chamadas de 3000 cada)


def test_concluir_apaga_o_texto_e_depois_nao_se_rele(db_session, empresa, teto):
    aid = _criar(db_session, empresa)
    a = _rodar(db_session, aid, Dublê())
    servico.concluir(a)
    db_session.commit()
    assert a.texto_json is None and a.texto_apagado_motivo == "concluida"
    assert len(json.loads(a.itens_json)["doze"]) == 12  # resultado fica
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


def test_leitura_que_estava_na_fila_na_virada_termina_no_formato_dela(db_session, empresa, teto):
    """Leitura criada em avaliador-v14-pilar antes do deploy da virada é processada no
    formato 1, com o pedido dela; a leitura nova é sempre o veredito."""
    from src.avaliador import motor

    aid = _criar(db_session, empresa)
    db_session.get(AvaliadorAnalise, aid).prompt_versao = motor.PROMPT_VERSAO_POR_PILAR
    db_session.commit()
    cli = Dublê([resposta_ok()])
    a = _rodar(db_session, aid, cli)
    assert a.status == STATUS_PRONTA and a.resumo == "Padrão de teste."
    assert servico.formato_da_leitura(a) == servico.FORMATO_ITENS
    assert '"forte"' in cli.chamadas[0]["system"]  # o pedido antigo, não o v20
    assert len(cli.chamadas) == 5


def test_falha_so_no_texto_do_lastro_fica_pronta_com_motivo(db_session, empresa, teto):
    aid = _criar(db_session, empresa)
    a = _rodar(db_session, aid, Dublê([resposta_v20(lastro=None)]))
    assert a.status == STATUS_PRONTA and a.erro_motivo == "lastro: RespostaInvalida"
    g = json.loads(a.itens_json)
    assert g["lastro"]["texto"] is None and g["lastro"]["ponto_de_partida"] == "P"
    assert a.custo_usd > 0


def test_reler_leitura_antiga_gera_o_formato_novo(db_session, empresa, teto):
    from src.avaliador import motor

    aid = _criar(db_session, empresa)
    db_session.get(AvaliadorAnalise, aid).prompt_versao = motor.PROMPT_VERSAO_POR_PILAR
    db_session.commit()
    a = _rodar(db_session, aid, Dublê([resposta_ok()]))
    servico.refazer(db_session, a)
    db_session.commit()
    a = _rodar(db_session, aid, Dublê())
    assert a.prompt_versao == "avaliador-v21-veredito"
    assert servico.formato_da_leitura(a) == servico.FORMATO_VEREDITO and a.resumo is None


def test_gate_cobra_as_seis_chamadas(db_session, empresa, monkeypatch):
    from src.avaliador import veredito

    cobrado = {}
    monkeypatch.setattr(servico, "checar_teto", lambda s, e, est: cobrado.setdefault("usd", est))
    config_avaliador(monkeypatch, AVALIADOR_TETO_MENSAL_USD=10.0)
    a = db_session.get(AvaliadorAnalise, _criar(db_session, empresa))
    from src.avaliador.extracao import Documento

    regua = servico.carregar_regua()
    sistema, usuario = servico._pedido(
        regua, a.origem, a.descricao, Documento.de_json(a.texto_json), a.prompt_versao
    )
    assert cobrado["usd"] == pytest.approx(
        veredito.estimar_custo_usd(sistema, usuario, a.modelo, 4)
    )


def test_pagina_da_web_vira_analise_com_o_endereco_lido(db_session, empresa, teto, monkeypatch):
    from tests.test_avaliador_pagina_web import HTML, Resp, Sessao, _resolve_para

    _resolve_para(monkeypatch, "93.184.216.34")
    s = Sessao(
        {
            "https://exemplo.com.br": Resp(301, headers={"Location": "/inicio"}),
            "https://exemplo.com.br/inicio": Resp(200, HTML.encode()),
        }
    )
    a = servico.criar_analise(
        db_session, empresa.id, None, DESCRICAO, url="exemplo.com.br", sessao_http=s
    )
    assert a.origem == "pagina" and a.formato == "web" and a.n_paginas == 3
    assert a.arquivo_nome == "https://exemplo.com.br/inicio"  # o que foi LIDO
    from src.avaliador.extracao import Documento

    doc = Documento.de_json(a.texto_json)
    sistema, _ = servico._pedido(
        servico.carregar_regua(), a.origem, a.descricao, doc, a.prompt_versao
    )
    assert "Há canal, não há horário." in sistema  # página é documento: biblioteca 1


def test_duas_entradas_ao_mesmo_tempo_sao_recusadas(db_session, empresa, teto):
    with pytest.raises(AvaliacaoRecusada, match="um só"):
        servico.criar_analise(
            db_session, empresa.id, None, DESCRICAO, texto="Cliente: oi", url="exemplo.com"
        )


def test_leitura_v20_na_fila_e_lida_com_o_pedido_de_hoje(db_session, empresa, teto):
    aid = _criar(db_session, empresa)
    db_session.get(AvaliadorAnalise, aid).prompt_versao = "avaliador-v20-veredito"
    db_session.commit()
    cli = Dublê()
    a = _rodar(db_session, aid, cli)
    assert a.status == STATUS_PRONTA and a.prompt_versao == "avaliador-v21-veredito"
    assert len(cli.chamadas) == 7
