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
    assert "nunca nega o que a peça tem" in sistema and "não para serem copiadas" in sistema
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


def test_travessao_sai_do_texto_do_modelo_mas_nao_da_citacao():
    from src.avaliador.motor import validar_saida

    doc = Documento("texto", [Pagina(1, "Prazo — 30 dias corridos para a entrega final.")])
    obj = {
        "resumo": "Bom documento — mas falta prazo.",
        "itens": [
            {
                "subpilar": "P1",
                "tipo": "forte",
                "texto": "Prazo declarado – claro.",
                "evidencias": [{"pagina": 1, "trecho": "Prazo — 30 dias corridos"}],
            }
        ],
    }
    res = validar_saida(doc, obj)
    assert res["resumo"] == "Bom documento, mas falta prazo."
    assert res["itens"][0]["texto"] == "Prazo declarado, claro."
    assert res["itens"][0]["evidencias"][0]["trecho"] == "Prazo — 30 dias corridos"  # literal
    assert res["itens"][0]["evidencias"][0]["conferido"] is True


def test_pedido_tem_as_regras_novas_e_nenhum_travessao_proprio():
    import re

    r = carregar_regua()
    s = montar_sistema(r, ORIGEM_ARQUIVO)
    assert "Contradição interna da peça" in s and "é sempre P1" in s
    assert "SE a peça disser que o cliente tem mais de uma unidade" in s
    assert "No máximo três itens por subpilar" in s and "não podem se contradizer" in s
    assert "R$ 96.000 no ano, R$ 11.520 de desconto e R$ 84.480 líquidos" in s  # $ escapado
    assert "Não invente base que a peça não dá" in s
    # o exemplo do "falta" não vem de peça real (a Office Total trazia nome e e-mail)
    assert "nome e um e-mail" not in s and "plantão no fim de semana" in s
    # travessão só pode vir das linhas literais do Manual (e da regra que o proíbe)
    manual = {p.titulo for p in r.pilares} | {p.descricao for p in r.pilares}
    manual |= {f"- {sp.texto}" for p in r.pilares for sp in p.subpilares}
    traco = re.compile("[\u2014\u2013]")
    proprios = [
        ln
        for ln in s.splitlines()
        if traco.search(ln) and ln not in manual and "Não use travessão" not in ln
    ]
    assert proprios == []


# ── leitura por pilar ──────────────────────────────────────────────────────


def _por_pilar_ok():
    return [
        {
            "itens": [
                {
                    "subpilar": "P1",
                    "tipo": "melhorar",
                    "texto": "Prazo sem início.",
                    "evidencias": [{"pagina": 2, "trecho": "diagnóstico completo em 30 dias"}],
                }
            ]
        },
        {
            "itens": [
                {
                    "subpilar": "D1",
                    "tipo": "forte",
                    "texto": "Horário — declarado.",
                    "evidencias": [{"pagina": 1, "trecho": "segunda a sexta das 8h às 18h"}],
                }
            ]
        },
        {"itens": []},
        {"itens": []},
        {"resumo": "Junte prazo e horário — num só lugar."},
    ]


def test_por_pilar_faz_uma_chamada_por_pilar_e_uma_de_resumo():
    from src.avaliador.motor import ler_por_pilar

    r = carregar_regua()
    cli = Dublê(_por_pilar_ok())
    res, uso = ler_por_pilar(cli, MODELO, r, "s", "peça", _doc())
    assert len(cli.chamadas) == 5 and uso.tokens_in == 15000
    assert [i["subpilar"] for i in res["itens"]] == ["P1", "D1"]
    assert res["itens"][1]["texto"] == "Horário, declarado."
    assert res["resumo"] == "Junte prazo e horário, num só lugar."
    # a peça vai num bloco em cache, igual em todas; a instrução do pilar vem depois
    blocos = [c["messages"][0]["content"] for c in cli.chamadas]
    assert all(
        b[0] == {"type": "text", "text": "peça", "cache_control": {"type": "ephemeral"}}
        for b in blocos
    )
    assert "subpilares P1, P2, P3" in blocos[0][1]["text"]
    assert "contradição interna é sempre P1" in blocos[0][1]["text"]
    assert "subpilares D1, D2, D3" in blocos[1][1]["text"]
    assert "não a traga aqui" in blocos[1][1]["text"]
    assert "Prazo sem início." in blocos[4][1]["text"]  # o resumo vê os itens


def test_por_pilar_recusa_item_de_outro_pilar():
    from src.avaliador.motor import ler_por_pilar

    respostas = _por_pilar_ok()
    intruso = {"itens": [{"subpilar": "A1", "tipo": "falta", "texto": "x", "evidencias": []}]}
    respostas.insert(0, intruso)
    cli = Dublê(respostas)
    res, _ = ler_por_pilar(cli, MODELO, carregar_regua(), "s", "peça", _doc())
    assert len(cli.chamadas) == 6
    assert "fora do pilar pedido" in cli.chamadas[1]["messages"][0]["content"][1]["text"]
    assert "A1" not in [i["subpilar"] for i in res["itens"]]


def test_por_pilar_para_antes_de_passar_do_orcamento():
    from src.avaliador.motor import (
        MAX_TOKENS_PILAR,
        OrcamentoEsgotado,
        _pior_caso_usd,
        ler_por_pilar,
    )

    # cabe a primeira chamada no pior caso, não a segunda depois do gasto da primeira
    pior = _pior_caso_usd(MODELO, 200, MAX_TOKENS_PILAR)
    cli = Dublê(_por_pilar_ok())
    with pytest.raises(OrcamentoEsgotado) as exc:
        ler_por_pilar(cli, MODELO, carregar_regua(), "s", "peça", _doc(), orcamento_usd=pior * 1.2)
    assert len(cli.chamadas) == 1 and exc.value.uso.custo_usd > 0  # gasto conta


def test_estimativa_por_pilar_cobre_o_pior_caso_das_cinco_chamadas():
    from src.avaliador.motor import MAX_TOKENS_PILAR, _pior_caso_usd, estimar_custo_por_pilar_usd

    est = estimar_custo_por_pilar_usd("s" * 4000, "u" * 4000, MODELO, 4)
    assert est > 4 * _pior_caso_usd(MODELO, 8000, MAX_TOKENS_PILAR)


def test_quarto_item_do_subpilar_fica_descartado_sem_nova_tentativa():
    from src.avaliador.motor import validos

    item = {"subpilar": "D1", "tipo": "falta", "texto": "x", "evidencias": []}
    demais = {"resumo": "r", "itens": [dict(item, texto=f"x{n}") for n in range(5)]}
    cli = Dublê([demais])
    res, _ = ler(cli, MODELO, "s", "u", _doc())
    assert len(cli.chamadas) == 1  # sem nova tentativa
    assert [i["descartado"] for i in res["itens"]] == [False, False, False, True, True]
    assert [i["texto"] for i in validos(res["itens"])] == ["x0", "x1", "x2"]  # a ordem manda


def test_por_pilar_falha_so_no_resumo_guarda_os_itens(caplog):
    from src.avaliador.motor import ler_por_pilar

    respostas = _por_pilar_ok()[:4] + ["sem json", "de novo sem json"]
    res, uso = ler_por_pilar(Dublê(respostas), MODELO, carregar_regua(), "s", "peça", _doc())
    assert [i["subpilar"] for i in res["itens"]] == ["P1", "D1"]
    assert res["resumo"] is None and res["resumo_falhou"] == "RespostaInvalida"
    assert uso.tokens_in == 18000  # as 6 chamadas contam
    assert "resumo não gerado: RespostaInvalida" in caplog.text


def test_pedido_por_pilar_tem_as_regras_de_dentro_do_pilar():
    from src.avaliador.motor import _instrucao_pilar

    r = carregar_regua()
    p1, d = _instrucao_pilar(r.pilares[0]), _instrucao_pilar(r.pilares[1])
    assert "é o primeiro item do P1, à frente de qualquer outro" in p1
    for s in (p1, d):
        assert "Dentro deste pilar, cada item traz um achado diferente" in s
        assert "Um item nunca desdiz outro" in s and "no máximo duas frases" in s
    s = montar_sistema(r, ORIGEM_ARQUIVO)
    assert "do que mais muda a peça para o que menos muda" in s
    assert "é sempre o primeiro item do P1" in s and "tem no máximo duas frases" in s


def test_por_pilar_passa_os_itens_anteriores_para_nao_repetir():
    from src.avaliador.motor import ler_por_pilar

    cli = Dublê(_por_pilar_ok())
    ler_por_pilar(cli, MODELO, carregar_regua(), "s", "peça", _doc())
    sufixos = [c["messages"][0]["content"][1]["text"] for c in cli.chamadas]
    assert "JÁ APONTADO" not in sufixos[0]
    assert "JÁ APONTADO" in sufixos[1] and "P1 (melhorar): Prazo sem início." in sufixos[1]
    assert "D1 (forte): Horário, declarado." in sufixos[2]
