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
    assert "conversível" in termos_proibidos("Você é um cliente conversivel?")  # accent-insens.
    assert "Capital Relacional" in termos_proibidos("Mede o Capital Relacional.")
    assert termos_proibidos("Como foi o atendimento na loja?") == []  # limpo
    # fronteira de palavra: 'pilar' não casa dentro de 'pilares'... mas casa isolado
    assert "pilar" in termos_proibidos("Qual pilar você valoriza?")


def test_blocklist_podada_nao_bloqueia_comuns():
    """Prune da R5: nomes de pilar / palavras comuns NÃO bloqueiam mais."""
    assert termos_proibidos("Como você avalia a precisão da entrega?") == []
    assert termos_proibidos("A disponibilidade de produtos foi boa?") == []
    assert termos_proibidos("Como foi o caminho até a loja?") == []
    assert termos_proibidos("Qual a origem do produto?") == []  # 'origem' minúsculo é livre


def test_blocklist_origem_case_sensitive():
    """'ORIGEM' (modelo, maiúsculo) bloqueia; 'origem' (comum) não."""
    assert "ORIGEM" in termos_proibidos("Avalie o modelo ORIGEM no atendimento.")
    assert termos_proibidos("Qual a origem da sua visita?") == []


def test_blocklist_curadoria_bloqueia():
    """Termos J da curadoria (regra A/B/C) bloqueiam pela raiz correta."""
    # C) frase-jargão / token distintivo
    assert "Proximity" in termos_proibidos("Qual o Proximity Index da loja?")
    assert "Gini" in termos_proibidos("Como está o Gini?")
    assert "Índice Geral" in termos_proibidos("Avalie o Índice Geral.")
    assert "Selo Ouro" in termos_proibidos("Você conhece o Selo Ouro?")
    assert "Concentração de detratores" in termos_proibidos("Há concentração de detratores aqui?")
    # tokens de sistema
    assert "anomalia" in termos_proibidos("Houve alguma anomalia?")
    assert "cruzamento de temas" in termos_proibidos("Qual o cruzamento de temas?")
    assert "bucket" in termos_proibidos("Em qual bucket caiu?")
    assert "agrupamento" in termos_proibidos("A loja virou um agrupamento?")
    # A) código isolado (case-sensitive), nunca o nome embutido
    assert "D2" in termos_proibidos("Como avalia o D2 da unidade?")
    assert "N5" in termos_proibidos("Isso é uma ação N5?")
    assert "Pa1" in termos_proibidos("Qual o Pa1 da loja?")


def test_blocklist_guard_palavras_comuns():
    """GUARD: palavras-líder comuns dos compostos curados NUNCA bloqueiam
    (senão volta o falso-bloqueio que a poda eliminou)."""
    comuns = [
        "Como você avalia a precisão da entrega?",
        "A acessibilidade da loja foi boa?",
        "Sentiu empatia no atendimento?",
        "Como foi a calibração da promessa feita?",
        "A orientação recebida ajudou?",
        "Houve consistência no atendimento?",
        "A disponibilidade de produtos foi boa?",
        "Qual tema você prefere?",  # 'tema' é C
        "Ganhou algum selo?",  # 'selo' isolado é livre (só as frases bloqueiam)
        "Qual o índice de satisfação?",  # 'índice' isolado livre (só 'Índice Geral')
        "O serviço foi bom?",  # rótulo de faixa é C
        "A loja fica perto do cruzamento da avenida?",  # 'cruzamento' (rua) é livre
    ]
    for q in comuns:
        assert termos_proibidos(q) == [], f"falso-bloqueio em: {q}"
    # código minúsculo natural não bloqueia (CS): 'a2', 'd1' soltos
    assert termos_proibidos("vou de a2 ate a 1 no formulario") == []


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
