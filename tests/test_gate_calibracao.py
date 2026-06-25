"""Tests do gate de calibração do juiz (CP-Pesquisa-F1.4) — lógica de decisão.

Sem rede: o juiz é mockado (juiz_fn). Cobre o caminho de aprovação e os dois de
bloqueio (falso-positivo nos limpos / violação esperada não flagada). A chamada
real do juiz só acontece no preDeployCommand, nunca no CI.
"""

from __future__ import annotations

from scripts.gate_calibracao_juiz import main, rodar_gate
from src.pesquisa.calibracao import GOLDEN_SET_JUIZ


def _juiz_de(por_ordem):
    """juiz_fn que devolve, por ordem, a lista de regras (ints) a sinalizar."""

    def _fn(system, user):
        return {
            "perguntas": [
                {
                    "ordem": ordem,
                    "regras": [
                        {
                            "regra": r,
                            "passou": False,
                            "severidade": "avisa",
                            "motivo": "x",
                            "reescrita": "y",
                        }
                        for r in regras
                    ],
                }
                for ordem, regras in por_ordem.items()
            ]
        }

    return _fn


def _gabarito():
    """Veredito PERFEITO: cada caso sinaliza exatamente a regra esperada."""
    por_ordem = {}
    for i, (_cid, _e, _f, _s, _o, regra) in enumerate(GOLDEN_SET_JUIZ, 1):
        por_ordem[i] = [regra] if regra is not None else []
    return por_ordem


def test_gate_aprova_com_gabarito():
    ok, fps, faltas = rodar_gate(juiz_fn=_juiz_de(_gabarito()))
    assert ok is True and fps == [] and faltas == []


def test_gate_bloqueia_falso_positivo_em_limpo():
    gab = _gabarito()
    # acha o 1º caso limpo (regra None) e injeta um flag indevido
    idx_limpo = next(i for i, c in enumerate(GOLDEN_SET_JUIZ, 1) if c[5] is None)
    gab[idx_limpo] = [1]  # juiz acusa pergunta boa de valência
    ok, fps, faltas = rodar_gate(juiz_fn=_juiz_de(gab))
    assert ok is False and len(fps) == 1 and faltas == []


def test_gate_bloqueia_falta_de_flag():
    gab = _gabarito()
    # acha o 1º caso com violação e remove o flag esperado
    idx_viol = next(i for i, c in enumerate(GOLDEN_SET_JUIZ, 1) if c[5] is not None)
    gab[idx_viol] = []  # juiz não pegou a violação
    ok, fps, faltas = rodar_gate(juiz_fn=_juiz_de(gab))
    assert ok is False and faltas and fps == []


# ── main(): exit codes dos 3 caminhos ──────────────────────────────────────


def test_main_calibrado_retorna_0():
    assert main(juiz_fn=_juiz_de(_gabarito())) == 0


def test_main_regressao_retorna_1():
    """Falso-positivo nos limpos → bloqueia o deploy (exit 1)."""
    gab = _gabarito()
    idx_limpo = next(i for i, c in enumerate(GOLDEN_SET_JUIZ, 1) if c[5] is None)
    gab[idx_limpo] = [1]
    assert main(juiz_fn=_juiz_de(gab)) == 1


def test_main_erro_infra_fail_open_retorna_0(capsys):
    """API fora / chave ausente → fail-open: avisa e NÃO bloqueia (exit 0)."""

    def _juiz_explode(system, user):
        raise RuntimeError("API indisponível")

    assert main(juiz_fn=_juiz_explode) == 0
    assert "fail-open" in capsys.readouterr().err
