"""Tests do validador determinístico (CP-Pesquisa-F1.3): R5/R3/R4 + golden set.

Sem LLM — camada 100% determinística. Cobre o golden set (meta: 0 falso-bloqueio
nos limpos) + unidades de cada regra + isenção da âncora.
"""

from __future__ import annotations

import json

import pytest

from src.pesquisa.blocklist import termos_proibidos
from src.pesquisa.validador import (
    checar_escala,
    pergunta_dupla,
    tem_bloqueio,
    validar_perguntas,
)
from tests.golden_set_pesquisa import GOLDEN_SET


def _pergunta(enunciado, formato, opcoes, ordem=1, ancora=False):
    return {
        "ordem": ordem,
        "enunciado": enunciado,
        "formato": formato,
        "opcoes_json": json.dumps(opcoes) if opcoes else None,
        "gerada_por_ancora": ancora,
    }


@pytest.mark.parametrize("caso", GOLDEN_SET, ids=[c[0] for c in GOLDEN_SET])
def test_golden_set(caso):
    _id, enunciado, formato, opcoes, regra_violada, sev_esp = caso
    veredito = validar_perguntas([_pergunta(enunciado, formato, opcoes)])
    regras = veredito["perguntas"][0]["regras"]
    if regra_violada is None:
        assert regras == [], f"{_id}: falso-positivo determinístico {regras}"
    else:
        achadas = {r["regra"]: r for r in regras}
        assert (
            regra_violada in achadas
        ), f"{_id}: esperava regra {regra_violada}, veio {list(achadas)}"
        assert achadas[regra_violada]["severidade"] == sev_esp


def test_zero_falso_bloqueio_nos_limpos():
    """Meta do CP: nenhum caso limpo produz bloqueio."""
    limpos = [c for c in GOLDEN_SET if c[4] is None]
    perguntas = [_pergunta(c[1], c[2], c[3]) for c in limpos]
    veredito = validar_perguntas(perguntas)
    assert tem_bloqueio(veredito) is False
    assert all(p["regras"] == [] for p in veredito["perguntas"])


def test_blocklist_jargao():
    assert "ratio" in termos_proibidos("Como avalia o ratio?")
    assert "Precisão" in termos_proibidos("A precisao foi boa?")  # accent-insensitive
    assert "Capital Relacional" in termos_proibidos("Mede o Capital Relacional.")
    assert termos_proibidos("Como foi o atendimento na loja?") == []  # limpo
    # fronteira de palavra: 'pilar' não casa dentro de 'pilares'... mas casa isolado
    assert "pilar" in termos_proibidos("Qual pilar você valoriza?")


def test_pergunta_dupla():
    assert pergunta_dupla("O atendimento foi rápido e cordial?") is True
    assert pergunta_dupla("Gostou? Recomendaria?") is True  # 2 '?'
    assert pergunta_dupla("Como foi sua experiência na retirada?") is False
    assert pergunta_dupla("Como você avalia a rapidez do atendimento?") is False


def test_checar_escala():
    ok = {"tipo": "nota", "pontos": 5, "rotulos": ["a", "b", "c", "d", "e"], "ponto_medio_idx": 2}
    assert checar_escala(ok) is None
    assert checar_escala(
        {"tipo": "nota", "pontos": 4, "rotulos": list("abcd"), "ponto_medio_idx": 2}
    )
    assert checar_escala(None) is not None  # escala ausente
    assert checar_escala({"tipo": "multipla", "rotulos": ["x", "y"]}) is None
    assert checar_escala({"tipo": "multipla", "rotulos": ["x"]}) is not None  # <2 opções


def test_ancora_isenta():
    """Pergunta-âncora (sistema) não é validada — opções vazias não bloqueiam."""
    ancora = _pergunta(
        "Qual unidade você está avaliando?",
        "fechada",
        {"tipo": "unidade", "rotulos": []},
        ancora=True,
    )
    veredito = validar_perguntas([ancora])
    assert veredito["perguntas"][0]["regras"] == []
    assert tem_bloqueio(veredito) is False


def test_reescrita_na_escala():
    """R4 devolve uma escala equilibrada como reescrita sugerida."""
    v = validar_perguntas(
        [
            _pergunta(
                "Como avalia?",
                "fechada",
                {"tipo": "nota", "pontos": 4, "rotulos": list("abcd"), "ponto_medio_idx": 2},
            )
        ]
    )
    r4 = next(r for r in v["perguntas"][0]["regras"] if r["regra"] == 4)
    assert json.loads(r4["reescrita"])["pontos"] == 5
