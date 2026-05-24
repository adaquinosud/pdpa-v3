"""Testes unitários do parser do classifier (B5 CP-0).

Não chama API Anthropic — só testa _parse_response e _reparar_json_truncado
contra respostas raw conhecidas (incluindo casos reais que apareceram em
produção: JSON truncado por max_tokens + markdown fence).
"""

from __future__ import annotations

import pytest

from src.classifier.classifier_v3 import _parse_response, _reparar_json_truncado


def test_parse_resposta_json_simples():
    raw = (
        '{"subpilar": "Pa1", "tipo": "promotor", "confianca": 0.9, ' '"justificativa_curta": "ok"}'
    )
    r = _parse_response(raw)
    assert r.subpilar == "Pa1"
    assert r.tipo == "promotor"
    assert r.confianca == 0.9
    assert r.justificativa == "ok"


def test_parse_resposta_com_markdown_fence():
    raw = (
        "```json\n"
        '{"subpilar": "D1", "tipo": "detrator", "confianca": 0.7, '
        '"justificativa_curta": "fila enorme"}\n'
        "```"
    )
    r = _parse_response(raw)
    assert r.subpilar == "D1"
    assert r.tipo == "detrator"


def test_reparar_json_truncado_string_aberta():
    """Caso real B5 CP-0: max_tokens cortou no meio da justificativa."""
    truncado = (
        '{\n  "subpilar": "conversivel",\n  "tipo": "conversivel",\n'
        '  "confianca": 0.4,\n  "justificativa_curta": "Verbatim em francês'
    )
    reparado = _reparar_json_truncado(truncado)
    assert reparado is not None
    assert reparado["subpilar"] == "conversivel"
    assert reparado["justificativa_curta"].startswith("Verbatim em francês")


def test_reparar_json_truncado_apos_virgula():
    """JSON cortou logo após uma vírgula — recorta e fecha."""
    truncado = (
        '{\n  "subpilar": "Pa1",\n  "tipo": "promotor",\n  '
        '"confianca": 0.85,\n  "justificativa_curta": "ok",'
    )
    reparado = _reparar_json_truncado(truncado)
    assert reparado is not None
    assert reparado["subpilar"] == "Pa1"
    assert reparado["tipo"] == "promotor"


def test_parse_resposta_truncada_com_markdown_fence():
    """Caso real do Linx fonte 128: fence open + JSON truncado."""
    raw = (
        "```json\n"
        '{\n  "subpilar": "Pa1",\n  "tipo": "promotor",\n'
        '  "confianca": 0.92,\n  "justificativa_curta": "Elogio explícito ao '
        "atendimento humano específico (Artur nomeado, cordial, atencioso) "
        "caracteriza Pa"
    )
    # Antes do CP-0: levantava ValueError; agora reconstrói o JSON parcial.
    r = _parse_response(raw)
    assert r.subpilar == "Pa1"
    assert r.tipo == "promotor"
    assert r.confianca == 0.92
    # justificativa pode ter chegado truncada — não-vazia mas parcial é OK
    assert "Elogio" in r.justificativa


def test_reparar_devolve_none_pra_lixo():
    """Se a string for completamente inválida, devolve None — parser propaga erro."""
    assert _reparar_json_truncado("not json at all") is None


def test_parse_subpilar_invalido_levanta():
    raw = '{"subpilar": "INVALIDO", "tipo": "promotor", "confianca": 0.5}'
    with pytest.raises(ValueError, match="subpilar inválido"):
        _parse_response(raw)
