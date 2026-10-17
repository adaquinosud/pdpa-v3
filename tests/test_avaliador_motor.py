"""O que é comum a toda leitura do Avaliador (``motor.py``): pedido montado do Manual e das
pistas, conferência de citação, custo, travessão. A leitura em si (o veredito) está em
``test_avaliador_veredito.py``. Nenhuma chamada paga.

Fatia 4 (17/10): os testes da geração do formato 1 (forte, falta e melhorar, limite de
três, vaga de forte, coerência, chamada única, resumo) saíram junto com o código."""

from __future__ import annotations

import re

import pytest

from src.avaliador import veredito
from src.avaliador.extracao import Documento, Pagina
from src.avaliador.motor import (
    ModeloSemPreco,
    _evidencias,
    garantir_preco,
    montar_usuario,
    sem_travessao,
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


def test_pedido_leva_manual_regras_pistas_e_descricao():
    r = carregar_regua()
    sistema = veredito.montar_sistema(r, ORIGEM_ARQUIVO)
    assert "D2 — Eficácia Operacional: quando algo dá errado" in sistema  # Manual literal
    assert "não conta como prova para este cliente aqui" in sistema
    assert "vem com o trecho citado literalmente da peça" in sistema
    assert "Há canal, não há horário." in sistema  # pista da biblioteca 1
    assert "Ele perguntou com quem fala" not in sistema  # biblioteca 3 só para texto
    assert "Ele perguntou com quem fala" in veredito.montar_sistema(r, ORIGEM_TEXTO)
    u = montar_usuario("Proposta de renovação para cliente de TI", _doc())
    assert "Proposta de renovação para cliente de TI" in u and "=== PÁGINA 2 ===" in u


def test_cada_citacao_e_conferida_na_peca():
    evid = _evidencias(
        _doc(),
        [
            {"pagina": 1, "trecho": "segunda a sexta das 8h às 18h"},
            {"pagina": 1, "trecho": "trinta dias de prazo"},  # não existe na peça
            {"pagina": 1, "trecho": "diagnóstico completo em 30 dias"},  # está na p. 2
        ],
    )
    assert [e["conferido"] for e in evid] == [True, False, True]
    assert evid[2]["pagina_encontrada"] == 2  # a tela mostra onde o trecho FOI achado


def test_modelo_sem_preco_e_recusado():
    with pytest.raises(ModeloSemPreco):
        garantir_preco("claude-modelo-inexistente")
    with pytest.raises(ModeloSemPreco):
        veredito.estimar_custo_usd("s", "u", "claude-modelo-inexistente", 4)


def test_estimativa_cresce_com_o_tamanho_da_peca():
    pequena = veredito.estimar_custo_usd("s", "u" * 1000, MODELO, 4)
    assert 0 < pequena < veredito.estimar_custo_usd("s", "u" * 100000, MODELO, 4)


def test_travessao_sai_do_texto_do_modelo_mas_nao_da_citacao():
    doc = Documento("texto", [Pagina(1, "Prazo — 30 dias corridos para a entrega final.")])
    assert sem_travessao("Prazo declarado – claro.") == "Prazo declarado, claro."
    evid = _evidencias(doc, [{"pagina": 1, "trecho": "Prazo — 30 dias corridos"}])
    assert evid[0]["trecho"] == "Prazo — 30 dias corridos" and evid[0]["conferido"] is True


def test_pedido_tem_as_regras_de_conta_e_unidade_e_nenhum_travessao_proprio():
    r = carregar_regua()
    s = veredito.montar_sistema(r, ORIGEM_ARQUIVO)
    assert "SE a peça disser que o cliente tem mais de uma unidade" in s
    assert "R$ 96.000 no ano, R$ 11.520 de desconto e R$ 84.480 líquidos" in s  # $ escapado
    assert "Não invente base que a peça não dá" in s
    assert "Conta começada é conta terminada" in s
    for antigo in ('"forte"', '"falta"', '"melhorar"', "três itens", "Coerência"):
        assert antigo not in s, antigo
    # travessão só pode vir das linhas literais do Manual (e da regra que o proíbe)
    manual = {p.titulo for p in r.pilares} | {p.descricao for p in r.pilares}
    manual |= {f"- {sp.texto}" for p in r.pilares for sp in p.subpilares}
    traco = re.compile("[—–]")
    proprios = [
        ln
        for ln in s.splitlines()
        if traco.search(ln) and ln not in manual and "Não use travessão" not in ln
    ]
    assert proprios == []
