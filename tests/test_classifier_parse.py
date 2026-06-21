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


def test_parse_resposta_array_levanta_valueerror():
    """Modelo às vezes devolve um array JSON em vez de objeto. Deve levantar
    ValueError (capturável pelo reroll), não AttributeError de '.get' em list."""
    raw = '[{"subpilar": "Pa1", "tipo": "promotor", "confianca": 0.9}]'
    with pytest.raises(ValueError, match="não é um objeto JSON"):
        _parse_response(raw)


def test_parse_resposta_array_com_markdown_fence_levanta_valueerror():
    """Array embrulhado em ```json — fence é removido, mas o conteúdo segue
    sendo list → ValueError de formato (não AttributeError)."""
    raw = '```json\n[{"subpilar": "Pa1", "tipo": "promotor", "confianca": 0.9}]\n```'
    with pytest.raises(ValueError, match="não é um objeto JSON"):
        _parse_response(raw)


# ── Problema 1: tipo='misto' (e variantes) → normaliza para conversivel ──────
@pytest.mark.parametrize("tipo_raw", ["misto", "misto_conversivel", "misto_com_destaque_positivo"])
def test_parse_tipo_misto_normaliza_para_conversivel(tipo_raw):
    """O modelo emite 'misto*' como rótulo (a palavra aparece no prompt). Na
    semântica PDPA misto ≡ conversível → normaliza antes de validar (não erra)."""
    raw = (
        f'{{"subpilar": "Pa1", "tipo": "{tipo_raw}", "confianca": 0.72, '
        '"justificativa_curta": "pros e contras"}'
    )
    r = _parse_response(raw)
    assert r.subpilar == "Pa1"
    assert r.tipo == "conversivel"


def test_parse_tipo_invalido_nao_misto_segue_rejeitando():
    """Garante que a normalização é só de 'misto*' — outros tipos inválidos
    continuam levantando (não viram conversível por acidente)."""
    raw = '{"subpilar": "Pa1", "tipo": "neutro", "confianca": 0.5, "justificativa_curta": "x"}'
    with pytest.raises(ValueError, match="tipo inválido"):
        _parse_response(raw)


# ── Problema 2: aspas duplas internas na justificativa → regex fallback ──────
def test_parse_aspas_duplas_internas_regex_salva():
    """justificativa com aspas duplas (modelo cita o review) quebra json.loads;
    o fallback regex recupera os campos de decisão (enum/número, à prova de aspas)."""
    raw = (
        '```json\n{"subpilar": "D1", "tipo": "conversivel", "confianca": 0.7, '
        '"justificativa_curta": "reclama da fila ("40 min"), mas elogia a limpeza"}\n```'
    )
    r = _parse_response(raw)
    assert r.subpilar == "D1"
    assert r.tipo == "conversivel"
    assert r.confianca == 0.7


def test_parse_truncado_com_aspas_internas_regex_salva():
    """Aspas internas + truncado no fim: repair falha (vírgula dentro da prosa),
    regex recupera subpilar/tipo e ainda normaliza o 'misto' do campo tipo."""
    raw = (
        '```json\n{"subpilar": "Pa1", "tipo": "misto", "confianca": 0.72, '
        '"justificativa_curta": "Elogio à atendente ("muito atenciosa"), '
        "mas crítica ao ambiente de des"
    )
    r = _parse_response(raw)
    assert r.subpilar == "Pa1"
    assert r.tipo == "conversivel"  # 'misto' normalizado


def test_parse_truncado_sem_aspas_nao_regride():
    """Truncamento puro (sem aspas internas) continua recuperado pelo repair —
    a justificativa parcial é preservada (best-effort), não regride."""
    raw = (
        '```json\n{"subpilar": "D1", "tipo": "conversivel", "confianca": 0.72, '
        '"justificativa_curta": "Cliente relata fila, espera longa, mas elogia o atend'
    )
    r = _parse_response(raw)
    assert r.subpilar == "D1"
    assert r.tipo == "conversivel"
    assert "Cliente relata fila" in r.justificativa
