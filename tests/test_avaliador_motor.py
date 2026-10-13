"""Motor do Avaliador com cliente LLM DUBLADO — nenhuma chamada paga."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from src.avaliador.extracao import Documento, Pagina
from src.avaliador.motor import (
    ModeloSemPreco,
    RespostaInvalida,
    estimar_custo_usd,
    ler,
    montar_sistema,
    montar_usuario,
)
from src.avaliador.regua import ORIGEM_ARQUIVO, ORIGEM_TEXTO, carregar_regua

MODELO = "claude-sonnet-4-6"


def _doc():
    return Documento(
        "pdf",
        [
            Pagina(1, "Proposta para a Empresa X. Atendimento de segunda a sexta das 8h às 18h."),
            Pagina(2, "Entregaremos o diagnóstico completo em 30 dias corridos."),
        ],
    )


class Dublê:
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
                input_tokens=3000,
                output_tokens=800,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
            ),
        )


def _ok():
    return {
        "resumo": "Falta dizer o que acontece fora do horário.",
        "itens": [
            {
                "subpilar": "D1",
                "tipo": "forte",
                "texto": "Horário de atendimento declarado.",
                "evidencias": [{"pagina": 1, "trecho": "segunda a sexta das 8h às 18h"}],
            },
            {"subpilar": "D1", "tipo": "falta", "texto": "Rota fora do horário.", "evidencias": []},
            {
                "subpilar": "P1",
                "tipo": "melhorar",
                "texto": "Prazo sem data de início.",
                "evidencias": [{"pagina": 1, "trecho": "trinta dias de prazo"}],
            },
        ],
    }


def test_pedido_leva_manual_regras_pistas_e_descricao():
    r = carregar_regua()
    sistema = montar_sistema(r, ORIGEM_ARQUIVO)
    assert "D2 — Eficácia Operacional: quando algo dá errado" in sistema  # Manual literal
    assert "não conta como prova para este cliente aqui" in sistema
    assert "Toda afirmação vem com o trecho citado literalmente da peça" in sistema
    assert "Há canal, não há horário." in sistema  # pista da biblioteca 1
    assert "Ele perguntou com quem fala" not in sistema  # biblioteca 3 só para texto
    assert "Ele perguntou com quem fala" in montar_sistema(r, ORIGEM_TEXTO)
    u = montar_usuario("Proposta de renovação para cliente de TI", _doc())
    assert "Proposta de renovação para cliente de TI" in u and "=== PÁGINA 2 ===" in u


def test_leitura_valida_e_confere_cada_citacao():
    r = carregar_regua()
    res, uso = ler(Dublê([_ok()]), MODELO, montar_sistema(r, ORIGEM_ARQUIVO), "u", _doc())
    forte, falta, melhorar = res["itens"]
    assert forte["evidencias"][0]["conferido"] is True and forte["alerta"] is None
    assert falta["evidencias"] == [] and falta["alerta"] is None  # ausência não se cita
    assert melhorar["evidencias"][0]["conferido"] is False  # trecho inventado
    assert melhorar["alerta"] == "sem citação conferida na peça"
    assert uso.custo_usd > 0


@pytest.mark.parametrize(
    "estrago, msg",
    [
        ({"subpilar": "X9"}, "fora do modelo"),
        ({"tipo": "neutro"}, "tipo de item"),
        ({"texto": ""}, "sem texto"),
    ],
)
def test_item_invalido_gera_nova_tentativa(estrago, msg):
    ruim = _ok()
    ruim["itens"][0].update(estrago)
    cli = Dublê([ruim, _ok()])
    res, uso = ler(cli, MODELO, "s", "u", _doc())
    assert len(res["itens"]) == 3 and uso.tokens_in == 6000
    assert msg in cli.chamadas[1]["messages"][0]["content"]


def test_duas_falhas_levantam_com_o_custo_acumulado():
    with pytest.raises(RespostaInvalida) as exc:
        ler(Dublê(["sem json", {"itens": []}]), MODELO, "s", "u", _doc())
    assert exc.value.uso.tokens_in == 6000 and exc.value.uso.custo_usd > 0


def test_modelo_sem_preco_e_recusado():
    with pytest.raises(ModeloSemPreco):
        estimar_custo_usd("s", "u", "claude-modelo-inexistente")
    with pytest.raises(ModeloSemPreco):
        ler(Dublê([_ok()]), "claude-modelo-inexistente", "s", "u", _doc())


def test_estimativa_cresce_com_o_tamanho_da_peca():
    assert (
        0
        < estimar_custo_usd("s", "u" * 1000, MODELO)
        < estimar_custo_usd("s", "u" * 100000, MODELO)
    )
