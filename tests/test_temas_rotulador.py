"""Tests CP-9 do Caminho A: rotulador de cluster (mock LLM)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from src.temas.rotulador import _normalizar_label, rotular_cluster


def _mock_anthropic(json_str: str):
    """Cria um cliente fake que devolve ``json_str`` no content."""
    fake_block = MagicMock(type="text", text=json_str)
    fake_resp = MagicMock(content=[fake_block])
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_resp
    return fake_client


def test_normalizar_label_strip_e_whitespace():
    assert _normalizar_label("  fila  check-in  ") == "fila check-in"
    assert _normalizar_label("demora\tbagagem") == "demora bagagem"


def test_rotular_cluster_devolve_label_canonica():
    fake = _mock_anthropic('{"nome": "demora bagagem"}')
    with patch("src.classifier.classifier_v3._get_client", return_value=fake):
        nome = rotular_cluster(
            {
                "subpilar": "D2",
                "tipo": "detrator",
                "setor": "aeroporto",
                "agrupamento": "Aeroporto",
            },
            [
                {"texto": "Esperei 1h30 pela bagagem"},
                {"texto": "Bagagem demorou demais"},
                {"texto": "Demorou pra sair a mala"},
            ],
        )
    assert nome == "demora bagagem"


def test_rotular_cluster_devolve_none_quando_llm_diz_null():
    """Cluster ininteligível (só elogios genéricos) → LLM devolve null → função None."""
    fake = _mock_anthropic('{"nome": null}')
    with patch("src.classifier.classifier_v3._get_client", return_value=fake):
        nome = rotular_cluster(
            {"subpilar": "Pa1", "tipo": "promotor"},
            [{"texto": "Muito bom"}, {"texto": "Excelente"}],
        )
    assert nome is None


def test_rotular_cluster_normaliza_resposta_com_espaco_e_caixa():
    """LLM às vezes devolve com whitespace — normalizamos."""
    fake = _mock_anthropic('{"nome": "  Fila  Check-In  "}')
    with patch("src.classifier.classifier_v3._get_client", return_value=fake):
        nome = rotular_cluster(
            {"subpilar": "D1", "tipo": "detrator"},
            [{"texto": "Fila enorme no check-in"}],
        )
    # _normalizar_label não baixa caixa de propósito (preserva nomes próprios);
    # só strip + collapse whitespace.
    assert nome == "Fila Check-In"


def test_rotular_cluster_aceita_fence_json_no_output():
    """Algumas chamadas Haiku devolvem dentro de fence ```json ... ```."""
    fake = _mock_anthropic('```json\n{"nome": "atendimento personalizado"}\n```')
    with patch("src.classifier.classifier_v3._get_client", return_value=fake):
        nome = rotular_cluster(
            {"subpilar": "Pa1", "tipo": "promotor"},
            [{"texto": "Sócrates lembrou meu nome"}],
        )
    assert nome == "atendimento personalizado"


def test_rotular_cluster_tolera_prosa_apos_json():
    """Haiku às vezes anexa '**Justificativa**: ...' depois do JSON (mesmo
    dentro de fence). O parser deve extrair o objeto e ignorar a prosa.

    Regressão do CP-11 smoke: o bucket 10:P2:detrator perdeu 'condição
    veículo' e 'qualidade comida' exatamente por esse motivo.
    """
    raw = (
        '```json\n{"nome": "condição veículo"}\n```\n\n'
        "**Justificativa**: Os representativos convergem para problemas de "
        "estado físico do veículo (danos, manutenção inadequada,"
    )
    fake = _mock_anthropic(raw)
    with patch("src.classifier.classifier_v3._get_client", return_value=fake):
        nome = rotular_cluster(
            {"subpilar": "P2", "tipo": "detrator"},
            [{"texto": "Carro veio com risco na lataria"}],
        )
    assert nome == "condição veículo"


def test_rotular_cluster_null_com_justificativa_vira_none():
    """{"nome": null} seguido de prosa ainda resulta em None (descartado)."""
    raw = '```json\n{"nome": null}\n```\n\n**Justificativa**: só elogios genéricos.'
    fake = _mock_anthropic(raw)
    with patch("src.classifier.classifier_v3._get_client", return_value=fake):
        nome = rotular_cluster(
            {"subpilar": "Pa1", "tipo": "promotor"},
            [{"texto": "muito bom"}],
        )
    assert nome is None


def test_rotular_cluster_descarta_quando_json_invalido():
    """JSON malformado → None (caller descarta cluster)."""
    fake = _mock_anthropic("isso não é json")
    with patch("src.classifier.classifier_v3._get_client", return_value=fake):
        nome = rotular_cluster(
            {"subpilar": "D2", "tipo": "detrator"},
            [{"texto": "qualquer"}],
        )
    assert nome is None


def test_rotular_cluster_descarta_quando_exception_llm():
    """Erro de rede → None (não levanta — pipeline continua)."""
    fake = MagicMock()
    fake.messages.create.side_effect = ConnectionError("rede")
    with patch("src.classifier.classifier_v3._get_client", return_value=fake):
        nome = rotular_cluster(
            {"subpilar": "D2", "tipo": "detrator"},
            [{"texto": "qualquer"}],
        )
    assert nome is None


def test_rotular_cluster_sem_representativos_devolve_none_sem_chamar_llm():
    fake = MagicMock()
    with patch("src.classifier.classifier_v3._get_client", return_value=fake):
        nome = rotular_cluster({"subpilar": "D2"}, [])
    assert nome is None
    fake.messages.create.assert_not_called()


def test_rotular_cluster_filtra_representativos_sem_texto():
    """Reps com texto vazio são puladas. Se todos forem vazios → None."""
    fake = MagicMock()
    with patch("src.classifier.classifier_v3._get_client", return_value=fake):
        nome = rotular_cluster(
            {"subpilar": "D2"},
            [{"texto": ""}, {"texto": "   "}, {}],
        )
    assert nome is None
    fake.messages.create.assert_not_called()


def test_rotular_cluster_payload_inclui_apenas_campos_preenchidos():
    """Bucket sem agrupamento não vai no payload (verifica via inspect do call)."""
    fake = _mock_anthropic('{"nome": "qualquer"}')
    with patch("src.classifier.classifier_v3._get_client", return_value=fake):
        rotular_cluster(
            {"subpilar": "Pa1", "tipo": "promotor"},  # sem setor, sem agrupamento
            [{"texto": "t1"}],
        )
    # Inspect: messages.create foi chamada com 1 user msg cujo content é JSON
    _args, kwargs = fake.messages.create.call_args
    user_content = kwargs["messages"][0]["content"]
    body = json.loads(user_content)
    assert "subpilar" in body["bucket"]
    assert "tipo" in body["bucket"]
    assert "agrupamento" not in body["bucket"]
    assert "setor" not in body["bucket"]


def test_rotular_cluster_trunca_representativo_longo():
    """Texto >220 chars é truncado."""
    fake = _mock_anthropic('{"nome": "t"}')
    longo = "a" * 500
    with patch("src.classifier.classifier_v3._get_client", return_value=fake):
        rotular_cluster({"subpilar": "D2"}, [{"texto": longo}])
    _, kwargs = fake.messages.create.call_args
    body = json.loads(kwargs["messages"][0]["content"])
    assert len(body["representativos"][0]["texto"]) <= 220
