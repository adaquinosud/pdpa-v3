"""Motor do Avaliador com cliente LLM DUBLADO — nenhuma chamada paga. Prova a mecânica
determinística: id de frase no conjunto certo, citação conferida, agregação do P1,
nova tentativa, custo contado mesmo na falha, modelo sem preço recusado."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from src.avaliador import motor
from src.avaliador.extracao import Documento, Pagina
from src.avaliador.motor import (
    ModeloSemPreco,
    RespostaInvalida,
    agregar_p1,
    estimar_custo_usd,
    etapa1,
    ler_pergunta,
    leitura_do_fim,
    montar_sistema,
)
from src.avaliador.regua import carregar_regua

MODELO = "claude-sonnet-4-6"
SENTINELA = "Atendimento de segunda a sexta das 8h às 18h pelo gerente Fulano."


def _doc():
    return Documento(
        "pptx",
        [
            Pagina(1, "Proposta para a Empresa X. " + SENTINELA),
            Pagina(2, "Entregaremos o diagnóstico completo em 30 dias corridos."),
            Pagina(3, ""),
        ],
    )


class Dublê:
    """Devolve, em ordem, as respostas enfileiradas; registra cada chamada."""

    def __init__(self, respostas):
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
                input_tokens=1000,
                output_tokens=200,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=5000,
            ),
        )


@pytest.fixture
def regua():
    return carregar_regua()


def test_prefixo_cacheado_tem_regras_perguntas_nomes_e_documento(regua):
    sistema = montar_sistema(regua, _doc())
    assert len(sistema) == 2
    assert all(b["cache_control"] == {"type": "ephemeral"} for b in sistema)
    moldura, documento = sistema[0]["text"], sistema[1]["text"]
    assert "A evidência só conta se for compromisso com ESTE cliente" in moldura
    assert "D1 (Acessibilidade)" in moldura  # nome de NOME_SUBPILAR, não do JSON
    assert "=== PÁGINA 2 ===" in documento and "[página sem texto legível]" in documento


def test_etapa1_valida_tipo(regua):
    sistema = montar_sistema(regua, _doc())
    ok = {"tipo": "proposta", "secao_comercial": False, "discute_preco": False}
    out, uso = etapa1(Dublê([ok]), MODELO, sistema, regua, _doc())
    assert out["tipo"] == "proposta" and uso.custo_usd > 0
    with pytest.raises(RespostaInvalida, match="tipo fora da lista"):
        etapa1(Dublê([{"tipo": "folder"}]), MODELO, sistema, regua, _doc())


def test_pergunta_em_parte_com_citacao_conferida(regua):
    sistema = montar_sistema(regua, _doc())
    r = {
        "veredito": "em_parte",
        "evidencias": [{"pagina": 1, "trecho": "segunda a sexta das 8h às 18h"}],
        "frase_id": "EP-D1-04",
        "complemento": "Diga o caminho de escalada.",
        "confianca": "alta",
    }
    res, uso = ler_pergunta(Dublê([r]), MODELO, sistema, regua, _doc(), "D1", True)
    assert res["veredito"] == "em_parte" and res["frase_id"] == "EP-D1-04"
    assert res["evidencias"][0]["conferido"] is True and res["alerta"] is None
    assert res["tentativas"] == 1


def test_frase_de_outro_conjunto_gera_nova_tentativa_e_depois_aceita(regua):
    sistema = montar_sistema(regua, _doc())
    errado = {"veredito": "sem_resposta", "evidencias": [], "frase_id": "L1-D2-01"}
    certo = {"veredito": "sem_resposta", "evidencias": [], "frase_id": "L1-D1-08"}
    cli = Dublê([errado, certo])
    res, uso = ler_pergunta(cli, MODELO, sistema, regua, _doc(), "D1", True)
    assert res["frase_id"] == "L1-D1-08" and res["tentativas"] == 2
    assert "foi recusada" in cli.chamadas[1]["messages"][0]["content"]
    assert uso.tokens_in == 2000  # as duas chamadas contam


def test_duas_falhas_levantam_com_o_custo_acumulado(regua):
    sistema = montar_sistema(regua, _doc())
    errado = {"veredito": "talvez"}
    with pytest.raises(RespostaInvalida) as exc:
        ler_pergunta(Dublê([errado, "sem json"]), MODELO, sistema, regua, _doc(), "P2", True)
    assert exc.value.uso.tokens_in == 2000 and exc.value.uso.custo_usd > 0


def test_respondida_sem_citacao_conferida_fica_com_alerta_e_nao_e_reescrita(regua):
    sistema = montar_sistema(regua, _doc())
    r = {
        "veredito": "respondida",
        "evidencias": [{"pagina": 1, "trecho": "atende 24 horas por dia"}],
    }
    res, _ = ler_pergunta(Dublê([r]), MODELO, sistema, regua, _doc(), "D1", True)
    assert res["veredito"] == "respondida"
    assert res["alerta"] == "sem citação conferida no documento"
    assert res["frase_id"] is None


def _p1_sem_secao():
    parte = lambda v, f=None: {"veredito": v, "evidencias": [], "frase_id": f}  # noqa: E731
    return {
        "partes": {
            "escopo": {
                "veredito": "respondida",
                "evidencias": [{"pagina": 2, "trecho": "Entregaremos o diagnóstico completo"}],
            },
            "prazo": {
                "veredito": "respondida",
                "evidencias": [{"pagina": 2, "trecho": "completo em 30 dias corridos"}],
            },
            "fora": parte("sem_resposta", "L1-P1c-01"),
        },
        "frase_id_em_parte": "EP-P1-01",
        "frase_id_sem_anexo": "L1-P1d_sem_anexo-02",
        "confianca": "media",
    }


def test_p1_sem_secao_comercial_nao_julga_preco_e_agrega_pelo_anexo(regua):
    sistema = montar_sistema(regua, _doc())
    cli = Dublê([_p1_sem_secao()])
    res, _ = ler_pergunta(cli, MODELO, sistema, regua, _doc(), "P1", False)
    assert res["partes"]["preco"] is None
    prompt = cli.chamadas[0]["messages"][0]["content"]
    assert "NÃO julgue o preço" in prompt and "L1-P1d_sem_anexo-01" in prompt
    # sem resposta da pessoa: preço fora da conta, tela pergunta
    a = agregar_p1(res, preco_em_anexo=None)
    assert a["veredito"] == "em_parte" and a["pergunta_anexo"] is True
    assert a["frase_id"] == "EP-P1-01"
    # "está em anexo": continua fora, pergunta some — SEM nova chamada
    b = agregar_p1(res, preco_em_anexo=True)
    assert b["pergunta_anexo"] is False and b["veredito"] == "em_parte"
    assert len(cli.chamadas) == 1


def test_p1_nao_ha_anexo_entra_como_sem_resposta_com_frase_escolhida_de_antemao(regua):
    res, _ = ler_pergunta(
        Dublê([_p1_sem_secao()]), MODELO, montar_sistema(regua, _doc()), regua, _doc(), "P1", False
    )
    res["partes"]["escopo"] = {**res["partes"]["fora"]}
    res["partes"]["prazo"] = {**res["partes"]["fora"]}
    a = agregar_p1(res, preco_em_anexo=False)
    assert a["veredito"] == "sem_resposta"
    assert a["frase_id"] == "L1-P1c-01"  # primeira parte aberta na ordem escopo→preço
    res["partes"]["fora"] = {"veredito": "respondida", "evidencias": [], "frase_id": None}
    res["partes"]["escopo"] = res["partes"]["prazo"] = res["partes"]["fora"]
    b = agregar_p1(res, preco_em_anexo=False)
    assert b["veredito"] == "em_parte"  # três respondidas + preço sem resposta


def test_p1_frase_sem_anexo_fora_do_conjunto_e_recusada(regua):
    ruim = _p1_sem_secao()
    ruim["frase_id_sem_anexo"] = "L1-P1d-01"
    with pytest.raises(RespostaInvalida, match="sem anexo"):
        ler_pergunta(
            Dublê([ruim, ruim]), MODELO, montar_sistema(regua, _doc()), regua, _doc(), "P1", False
        )


def test_leitura_do_fim_nao_reabre_o_documento(regua):
    cli = Dublê([{"leitura": "Padrão X. Consequência Y."}])
    res = [
        {"codigo": "D1", "veredito": "em_parte", "complemento": "Falta escalada."},
        {"codigo": "A1", "veredito": "respondida", "complemento": None},
    ]
    leitura, uso = leitura_do_fim(cli, MODELO, regua, "proposta", res)
    assert leitura == "Padrão X. Consequência Y."
    enviado = json.dumps(cli.chamadas[0], ensure_ascii=False, default=str)
    assert SENTINELA not in enviado
    assert "verificável sozinho: sim" in enviado  # A1


def test_modelo_sem_preco_e_recusado(regua):
    sistema = montar_sistema(regua, _doc())
    with pytest.raises(ModeloSemPreco):
        estimar_custo_usd(sistema, 12, "claude-modelo-inexistente")
    with pytest.raises(ModeloSemPreco):
        etapa1(Dublê([{"tipo": "proposta"}]), "claude-modelo-inexistente", sistema, regua, _doc())


def test_estimativa_cresce_com_o_numero_de_perguntas(regua):
    sistema = montar_sistema(regua, _doc())
    assert 0 < estimar_custo_usd(sistema, 6, MODELO) < estimar_custo_usd(sistema, 12, MODELO)


def test_prompt_da_pergunta_nao_recebe_o_tipo(regua):
    u = motor._usuario_pergunta(regua, "D1", True)
    for t in regua.tipos.values():
        assert t.nome not in u
