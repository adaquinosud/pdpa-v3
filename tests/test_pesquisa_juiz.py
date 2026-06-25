"""Tests do LLM-juiz semântico (CP-Pesquisa-F1.4).

CI: juiz mockado (rede NUNCA roda). Cobre contrato/normalização, merge com o
determinístico, isenção da âncora, e que não chama o LLM sem perguntas
avaliáveis. O teste de calibração real (0 falso-positivo nos limpos) é LIVE,
pulado por padrão (precisa de PESQUISA_LIVE_JUIZ + chave).
"""

from __future__ import annotations

import json
import os

import pytest

from src.pesquisa.juiz import REGUA_JUIZ, avaliar_perguntas, validar_completo
from src.pesquisa.validador import tem_bloqueio
from tests.golden_set_pesquisa import GOLDEN_SET_JUIZ


def _p(ordem, enunciado, formato="aberta", subpilar_alvo=None, opcoes=None, ancora=False):
    return {
        "ordem": ordem,
        "enunciado": enunciado,
        "formato": formato,
        "subpilar_alvo": subpilar_alvo,
        "opcoes_json": json.dumps(opcoes) if opcoes else None,
        "gerada_por_ancora": ancora,
    }


def _juiz_fixo(veredito, captura=None):
    def _fn(system, user):
        if captura is not None:
            captura.append((system, user))
        return veredito

    return _fn


def test_contrato_normalizado():
    """Força severidade 'avisa', descarta passou=True e regra fora do juiz."""
    bruto = {
        "perguntas": [
            {
                "ordem": 1,
                "regras": [
                    {
                        "regra": 1,
                        "passou": False,
                        "severidade": "bloqueia",
                        "motivo": "induz",
                        "reescrita": "X?",
                    },
                    {"regra": 2, "passou": True},  # ok → descartado
                    {"regra": 5, "passou": False},  # regra do determinístico → descartado
                ],
            }
        ]
    }
    out = avaliar_perguntas([_p(1, "O quanto foi excelente?")], juiz_fn=_juiz_fixo(bruto))
    regras = out["perguntas"][0]["regras"]
    assert len(regras) == 1
    r = regras[0]
    assert r["regra"] == 1 and r["severidade"] == "avisa" and r["reescrita"] == "X?"


def test_limpo_sem_flag():
    bruto = {"perguntas": [{"ordem": 1, "regras": []}]}
    out = avaliar_perguntas([_p(1, "Como foi o atendimento?")], juiz_fn=_juiz_fixo(bruto))
    assert out["perguntas"][0]["regras"] == []


def test_merge_deterministico_mais_juiz():
    """Jargão (R5 bloqueia, determinístico) + valência (R1 avisa, juiz) coexistem."""
    bruto = {
        "perguntas": [
            {
                "ordem": 1,
                "regras": [
                    {
                        "regra": 1,
                        "passou": False,
                        "severidade": "avisa",
                        "motivo": "induz",
                        "reescrita": "Como foi?",
                    }
                ],
            }
        ]
    }
    perguntas = [_p(1, "O quanto o ratio foi excelente?")]  # 'ratio' → R5
    out = validar_completo(perguntas, juiz_fn=_juiz_fixo(bruto))
    regras = {r["regra"]: r for r in out["perguntas"][0]["regras"]}
    assert 5 in regras and regras[5]["severidade"] == "bloqueia"
    assert 1 in regras and regras[1]["severidade"] == "avisa"
    assert tem_bloqueio(out) is True


def test_ancora_isenta_do_juiz():
    captura: list = []
    bruto = {"perguntas": [{"ordem": 2, "regras": []}]}
    perguntas = [
        _p(1, "Qual unidade você avalia?", formato="fechada", ancora=True),
        _p(2, "Como foi o atendimento?"),
    ]
    out = avaliar_perguntas(perguntas, juiz_fn=_juiz_fixo(bruto, captura))
    # âncora não vai ao prompt do juiz
    assert "ordem 1" not in captura[0][1] and "ordem 2" in captura[0][1]
    # âncora presente no veredito, sem flags
    assert {p["ordem"] for p in out["perguntas"]} == {1, 2}
    assert out["perguntas"][0]["regras"] == []


def test_nao_chama_llm_sem_avaliaveis():
    """Só âncora → não chama o juiz (custo/rede zero)."""

    def _explode(system, user):
        raise AssertionError("juiz não deveria ser chamado")

    perguntas = [_p(1, "Qual unidade?", formato="fechada", ancora=True)]
    out = avaliar_perguntas(perguntas, juiz_fn=_explode)
    assert out["perguntas"][0]["regras"] == []


def test_user_prompt_lista_perguntas():
    captura: list = []
    bruto = {"perguntas": [{"ordem": 1, "regras": []}]}
    avaliar_perguntas(
        [
            _p(
                1,
                "Como avalia a rapidez?",
                formato="fechada",
                subpilar_alvo="D2",
                opcoes={"tipo": "nota", "pontos": 5},
            )
        ],
        juiz_fn=_juiz_fixo(bruto, captura),
    )
    user = captura[0][1]
    assert "ordem 1" in user and "Como avalia a rapidez?" in user
    assert "subpilar_alvo=D2" in user and "opcoes" in user


def test_system_prompt_tem_regras_e_ancoras_limpas():
    for marca in ("REGRA 1", "REGRA 2", "REGRA 7", "REGRA 4"):
        assert marca in REGUA_JUIZ
    assert "não sinalizar" in REGUA_JUIZ.lower()  # few-shot de limpos


@pytest.mark.skipif(
    not os.environ.get("PESQUISA_LIVE_JUIZ"),
    reason="calibração LIVE do juiz (precisa de PESQUISA_LIVE_JUIZ=1 + chave); fora do CI",
)
def test_juiz_live_calibracao():
    """Meta dura: 0 falso-positivo nos limpos + flag em cada violação semântica.
    Roda o juiz REAL contra GOLDEN_SET_JUIZ (não roda no CI)."""
    for cid, enun, fmt, sub, opcoes, regra in GOLDEN_SET_JUIZ:
        out = avaliar_perguntas([_p(1, enun, formato=fmt, subpilar_alvo=sub, opcoes=opcoes)])
        regras = {r["regra"] for r in out["perguntas"][0]["regras"]}
        if regra is None:
            assert not regras, f"{cid}: falso-positivo do juiz {regras}"
        else:
            assert regra in regras, f"{cid}: juiz não pegou regra {regra}"
