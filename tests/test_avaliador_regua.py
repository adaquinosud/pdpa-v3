"""Régua do Avaliador: os dados de autor fecham com o modelo do PDPA e entre si."""

from __future__ import annotations

import copy

import pytest

from src.api.painel import NOME_SUBPILAR, SUBPILARES_ORDEM
from src.avaliador.regua import (
    GRUPO_PARTE_P1,
    Regua,
    ReguaInvalida,
    _ler,
    carregar_regua,
    validar,
)


def _crus():
    return _ler("regua.json"), _ler("frases_l1.json"), _ler("frases_ep.json")


def test_carrega_e_valida():
    r = carregar_regua()
    assert [p.codigo for p in r.perguntas] == SUBPILARES_ORDEM


def test_nome_vem_de_nome_subpilar_e_nao_do_json():
    r = carregar_regua()
    for p in r.perguntas:
        assert p.nome == NOME_SUBPILAR[p.codigo]
    regua, _, _ = _crus()
    assert all("nome_canonico" not in p for p in regua["perguntas"])


def test_so_a1_e_a2_sao_verificaveis_sozinho():
    r = carregar_regua()
    assert {p.codigo for p in r.perguntas if p.verificavel_sozinho} == {"A1", "A2"}


def test_contagens_das_bibliotecas():
    r = carregar_regua()
    assert sum(len(v) for v in r.frases_l1.values()) == 115
    assert sum(len(v) for v in r.frases_ep.values()) == 60


def test_p1_tem_as_quatro_partes_e_cada_parte_tem_frases():
    r = carregar_regua()
    assert {p["id"] for p in r.pergunta("P1").partes} == set(GRUPO_PARTE_P1)
    for parte in GRUPO_PARTE_P1:
        assert r.ids_sem_resposta("P1", parte)


def test_perguntas_que_valem_por_tipo():
    r = carregar_regua()
    assert r.perguntas_que_valem("proposta", discute_preco=False) == SUBPILARES_ORDEM
    assert r.perguntas_que_valem("diagnostico", discute_preco=True) == [
        c for c in SUBPILARES_ORDEM if c not in ("P1", "A1")
    ]
    inst = r.perguntas_que_valem("institucional", discute_preco=True)
    assert inst == ["D1", "Pa1", "Pa2", "A1", "A2", "A3"]
    # condicional do Pa2: sem discussão de preço, sai
    assert "Pa2" not in r.perguntas_que_valem("institucional", discute_preco=False)


def test_codigo_divergente_de_subpilares_ordem_levanta():
    regua, l1, ep = _crus()
    regua = copy.deepcopy(regua)
    regua["perguntas"][0]["codigo"] = "X9"
    with pytest.raises(ReguaInvalida, match="SUBPILARES_ORDEM"):
        validar(Regua(regua, l1, ep))


def test_id_repetido_ou_fora_do_padrao_levanta():
    regua, l1, ep = _crus()
    l1 = copy.deepcopy(l1)
    l1["frases"]["P2"][1]["id"] = l1["frases"]["P2"][0]["id"]
    with pytest.raises(ReguaInvalida, match="id repetido"):
        validar(Regua(regua, l1, ep))
    l1 = copy.deepcopy(_crus()[1])
    l1["frases"]["P2"][0]["id"] = "L1-P3-99"
    with pytest.raises(ReguaInvalida, match="fora do padrão"):
        validar(Regua(regua, l1, ep))


def test_grupo_faltando_levanta():
    regua, l1, ep = _crus()
    ep = copy.deepcopy(ep)
    del ep["frases"]["D3"]
    with pytest.raises(ReguaInvalida, match="em parte' sem o grupo D3"):
        validar(Regua(regua, l1, ep))


def test_condicional_desconhecida_levanta_em_vez_de_ser_ignorada():
    regua, l1, ep = _crus()
    regua = copy.deepcopy(regua)
    inst = next(t for t in regua["tipos"] if t["codigo"] == "institucional")
    inst["condicionais"]["D1"] = "só vale se..."
    r = Regua(regua, l1, ep)
    with pytest.raises(ReguaInvalida, match="condicional sem regra"):
        r.perguntas_que_valem("institucional", discute_preco=True)
