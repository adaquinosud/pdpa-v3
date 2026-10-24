"""A verificação do trecho que se entende sozinho (24/10), primeira parte: as vizinhas na
peça, o pedido, a validação da resposta e a junção. Texto inventado: os casos reais das #31 e
#32 são o gabarito e não viram fixture. Sem modelo de verdade, sem gasto."""

from __future__ import annotations

import pytest

from src.avaliador import motor
from src.avaliador import sozinho as S
from src.avaliador.extracao import Documento, Pagina, vizinhas
from src.avaliador.motor import RespostaInvalida
from tests.test_avaliador_rascunho import Modelo

PAGINA = (
    "A entrega padrão leva cinco dias úteis. Esse prazo vale também para pedidos urgentes.\n"
    "Os benefícios incluem:\n"
    "Seguro, manutenção e carro reserva.\n"
    "Para quem precisa de mais.\n"
    "FALE CONOSCO"
)


def _doc():
    return Documento("web", [Pagina(1, PAGINA)])


def test_vizinhas_na_mesma_linha_e_atravessando_linha():
    v = vizinhas(_doc(), 1, "Esse prazo vale também para pedidos urgentes.")
    assert v["antes"] == "A entrega padrão leva cinco dias úteis." and not v["antes_outra_linha"]
    assert v["depois"] == "Os benefícios incluem:" and v["depois_outra_linha"]
    v = vizinhas(_doc(), 1, "Os benefícios incluem:")
    assert v["depois"] == "Seguro, manutenção e carro reserva." and v["depois_outra_linha"]


def test_vizinhas_no_comeco_e_no_fim_da_pagina_e_texto_nao_achado():
    assert vizinhas(_doc(), 1, "A entrega padrão leva cinco dias úteis.")["antes"] is None
    assert vizinhas(_doc(), 1, "FALE CONOSCO")["depois"] is None
    assert vizinhas(_doc(), 1, "Uma frase que a peça não tem em lugar nenhum.") is None


def test_itens_um_por_texto_impresso_com_as_vizinhas():
    evs = [
        {"pagina_encontrada": 1, "trecho": "Os benefícios incluem:"},
        {"pagina_encontrada": 1, "trecho": "Os  benefícios incluem:"},  # outra marca, mesmo texto
        {"pagina_encontrada": 1, "trecho": "Para quem precisa de mais."},
    ]
    lista = S.itens(evs, _doc())
    assert [x["n"] for x in lista] == [1, 2]
    assert lista[1]["antes"] == "Seguro, manutenção e carro reserva."
    texto = S.entrada(lista)
    assert "depois: (na linha de baixo) “Seguro, manutenção e carro reserva.”" in texto
    assert "depois: (na linha de baixo) “FALE CONOSCO”" in texto


def test_itens_sem_o_texto_da_peca_vai_sem_vizinhas():
    lista = S.itens([{"pagina_encontrada": 1, "trecho": "Os benefícios incluem:"}], None)
    assert lista[0]["antes"] is None and lista[0]["depois"] is None
    assert "antes: nenhuma" in S.entrada(lista)


def _lista():
    return S.itens(
        [
            {"pagina_encontrada": 1, "trecho": "A entrega padrão leva cinco dias úteis."},
            {"pagina_encontrada": 1, "trecho": "Esse prazo vale também para pedidos urgentes."},
            {"pagina_encontrada": 1, "trecho": "Os benefícios incluem:"},
            {"pagina_encontrada": 1, "trecho": "Para quem precisa de mais."},
        ],
        _doc(),
    )


def _resposta(*decs):
    return {"trechos": [{"n": i, "decisao": d, "tipo": t, "por_que": "porque sim"}
                        for i, (d, t) in enumerate(decs, 1)]}  # fmt: skip


BOA = _resposta(("passa", None), ("anterior", None), ("seguinte", None), ("exclui", "sem_vizinha"))


def test_validacao_e_juncao_pela_frase_literal_da_peca():
    lista = _lista()
    d = S.validador(lista)(BOA)
    textos = [S.aplicar(x, d[x["n"]]) for x in lista]
    assert textos == [
        "A entrega padrão leva cinco dias úteis.",
        "A entrega padrão leva cinco dias úteis. Esse prazo vale também para pedidos urgentes.",
        "Os benefícios incluem: Seguro, manutenção e carro reserva.",
        None,
    ]


@pytest.mark.parametrize(
    "resposta, erro",
    [
        ({"outra": []}, "trechos"),
        (_resposta(("passa", None)), "faltam"),
        (_resposta(*[("talvez", None)] * 4), "desconhecida"),
        (_resposta(("exclui", None), *[("passa", None)] * 3), "não combina"),
        (_resposta(("passa", "lista"), *[("passa", None)] * 3), "não combina"),
        (_resposta(("anterior", None), *[("passa", None)] * 3), "frase de antes"),
    ],
)
def test_validacao_recusa_resposta_errada(resposta, erro):
    with pytest.raises(RespostaInvalida, match=erro):
        S.validador(_lista())(resposta)


def test_vizinha_que_nao_existe_e_recusada_e_nao_vira_exclusao():
    # a última frase da página não tem frase de depois
    lista = S.itens([{"pagina_encontrada": 1, "trecho": "FALE CONOSCO e mais nada"}], _doc())
    assert lista[0]["depois"] is None
    with pytest.raises(RespostaInvalida):
        S.validador(lista)(_resposta(("seguinte", None)))


def test_chamada_com_temperatura_zero_e_nova_tentativa_quando_recusa():
    lista = _lista()
    m = Modelo(_resposta(("passa", None)), BOA)
    orc = {"total": motor.Uso(), "limite": None}
    d = motor._chamar(m, "claude-sonnet-4-6", S.sistema(), S.entrada(lista), S.PEDIDO,
                      S.max_tokens(lista), S.validador(lista), orc, S.TEMPERATURA)  # fmt: skip
    assert d[4]["tipo"] == "sem_vizinha" and len(m.chamadas) == 2
    assert all(c["temperature"] == 0.0 for c in m.chamadas)
    assert "faltam" in m.chamadas[1]["messages"][0]["content"][1]["text"]


def test_prompt_nao_traz_codigo_nem_trecho_de_cliente():
    s = S.sistema()
    assert "inventados" in s
    # nem expressão tirada dos casos do gabarito: o prompt não pode ensinar a resposta da prova
    for proibido in ("Localiza", "E2Carbon", "Fibrav", "EPTV", "agência", "essa mudança",
                     "a que", "antes disso", "pequenas empresas", "Veja como"):  # fmt: skip
        assert proibido not in s
