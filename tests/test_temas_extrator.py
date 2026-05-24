"""Testes do extrator de temas (Bloco 6 CP-2).

Mock do client Anthropic — não chama API real. Cobre fluxo de chamada,
parse com fence markdown, fallback truncado, filtro de confiança mínima,
cap de 3 temas, lista vazia em erro.
"""

from __future__ import annotations

import json

from src.temas.extrator import CONFIANCA_MINIMA, extrair_temas
from src.temas.slug import slugify


class _Block:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _Resp:
    def __init__(self, text: str) -> None:
        self.content = [_Block(text)]


def _fake_client(payload_text: str, capturas: list | None = None):
    """Cria um fake client que devolve `payload_text` em todas as chamadas.
    Se `capturas` for fornecida, anota cada `create()` call."""

    class _Client:
        class messages:
            @staticmethod
            def create(**kwargs):
                if capturas is not None:
                    capturas.append(kwargs)
                return _Resp(payload_text)

    return _Client()


# ── slugify ──────────────────────────────────────────────────────────


def test_slugify_basico():
    assert slugify("Fila no Check-in") == "fila-no-check-in"


def test_slugify_remove_acentos():
    assert slugify("Atendimento ÁGIL") == "atendimento-agil"


def test_slugify_normaliza_espacos_e_pontuacao():
    assert slugify("  WiFi/internet!!  ") == "wifi-internet"
    assert slugify("a,b,c") == "a-b-c"


def test_slugify_vazio():
    assert slugify("") == ""
    assert slugify(None) == ""  # type: ignore[arg-type]


def test_slugify_limita_80_chars():
    longo = "a" * 200
    assert len(slugify(longo)) == 80


# ── extrair_temas ────────────────────────────────────────────────────


def test_extrator_texto_vazio_devolve_lista_vazia():
    assert extrair_temas("", {}) == []
    assert extrair_temas("   ", {}) == []


def test_extrator_chama_haiku_com_contexto(monkeypatch):
    capturas: list = []
    fake = _fake_client(
        json.dumps(
            {
                "temas": [
                    {"nome": "Fila check-in", "confianca": 0.9, "evidencia_curta": "fila enorme"}
                ]
            }
        ),
        capturas,
    )
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: fake)

    contexto = {"subpilar": "D1", "tipo": "detrator", "setor": "aeroporto"}
    catalogo = [{"nome": "Fila check-in", "slug": "fila-check-in"}]
    res = extrair_temas("Fila enorme no check-in, demorei 40 minutos", contexto, catalogo)

    assert len(res) == 1
    assert res[0]["nome"] == "Fila check-in"
    assert res[0]["confianca"] == 0.9
    assert res[0]["evidencia_curta"] == "fila enorme"

    # User message recebido com contexto + catálogo
    assert len(capturas) == 1
    user_msg = json.loads(capturas[0]["messages"][0]["content"])
    assert user_msg["subpilar"] == "D1"
    assert user_msg["tipo"] == "detrator"
    assert user_msg["setor"] == "aeroporto"
    assert user_msg["catalogo_recente"][0]["slug"] == "fila-check-in"
    # System prompt presente
    assert "extrator de temas" in capturas[0]["system"]


def test_extrator_aceita_markdown_fence(monkeypatch):
    fake = _fake_client(
        '```json\n{"temas":[{"nome":"limpeza","confianca":0.7,'
        '"evidencia_curta":"banheiro sujo"}]}\n```'
    )
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: fake)
    res = extrair_temas("Banheiro sujo no terminal 2", {"subpilar": "P3"})
    assert len(res) == 1
    assert res[0]["nome"] == "limpeza"


def test_extrator_filtra_confianca_abaixo_do_minimo(monkeypatch):
    """B6 decisão 6: confiança < 0.4 não persiste."""
    fake = _fake_client(
        json.dumps(
            {
                "temas": [
                    {"nome": "tema_forte", "confianca": 0.85, "evidencia_curta": "x"},
                    {"nome": "tema_fronteira", "confianca": 0.41, "evidencia_curta": "y"},
                    {"nome": "tema_fraco", "confianca": 0.35, "evidencia_curta": "z"},
                    {"nome": "tema_nada", "confianca": 0.1, "evidencia_curta": "w"},
                ]
            }
        )
    )
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: fake)
    res = extrair_temas("texto qualquer", {})
    nomes = [r["nome"] for r in res]
    assert "tema_forte" in nomes
    assert "tema_fronteira" in nomes
    assert "tema_fraco" not in nomes
    assert "tema_nada" not in nomes


def test_extrator_cap_de_3_temas(monkeypatch):
    """B6 decisão 6: até 3 temas por verbatim — se LLM devolver 5, pega só 3."""
    fake = _fake_client(
        json.dumps(
            {
                "temas": [
                    {"nome": f"tema_{i}", "confianca": 0.7, "evidencia_curta": f"ev_{i}"}
                    for i in range(5)
                ]
            }
        )
    )
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: fake)
    res = extrair_temas("texto multi-tema", {})
    assert len(res) == 3
    # Primeiros 3
    assert [r["nome"] for r in res] == ["tema_0", "tema_1", "tema_2"]


def test_extrator_resposta_vazia_devolve_lista_vazia(monkeypatch):
    """Quando o modelo decide que não há temas extraíveis (verbatim genérico)."""
    fake = _fake_client('{"temas": []}')
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: fake)
    res = extrair_temas("Muito bom!", {"subpilar": "Pa1"})
    assert res == []


def test_extrator_falha_anthropic_devolve_lista_vazia(monkeypatch):
    """Robusto a falha de rede — pipeline continua."""

    def boom():
        raise RuntimeError("anthropic down")

    monkeypatch.setattr("src.classifier.classifier_v3._get_client", boom)
    res = extrair_temas("qualquer texto", {})
    assert res == []


def test_extrator_json_truncado_repara(monkeypatch):
    """B5 CP-0 deu o padrão — _reparar_json_truncado fecha estrutura."""
    truncado = '{"temas":[{"nome":"fila","confianca":0.8,"evidencia_curta":"muito grande'
    fake = _fake_client(truncado)
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: fake)
    res = extrair_temas("texto", {})
    # parser tenta reparar — pode recuperar 1 tema ou devolver vazio
    # essencial: NÃO levanta exceção
    assert isinstance(res, list)


def test_extrator_ignora_temas_sem_nome(monkeypatch):
    """Defesa: LLM devolve item sem nome → ignora silenciosamente."""
    fake = _fake_client(
        json.dumps(
            {
                "temas": [
                    {"nome": "valido", "confianca": 0.8},
                    {"nome": "", "confianca": 0.9},
                    {"confianca": 0.9},  # sem chave 'nome'
                ]
            }
        )
    )
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: fake)
    res = extrair_temas("texto", {})
    assert len(res) == 1
    assert res[0]["nome"] == "valido"


def test_extrator_evidencia_truncada_em_200_chars(monkeypatch):
    longa = "a" * 500
    fake = _fake_client(
        json.dumps({"temas": [{"nome": "t", "confianca": 0.8, "evidencia_curta": longa}]})
    )
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: fake)
    res = extrair_temas("texto", {})
    assert len(res[0]["evidencia_curta"]) == 200


def test_extrator_confianca_clampa_em_0_1(monkeypatch):
    """Defesa contra LLM bugado devolver confianca > 1.0 ou < 0."""
    fake = _fake_client(
        json.dumps(
            {
                "temas": [
                    {"nome": "supra", "confianca": 1.5, "evidencia_curta": ""},
                    {"nome": "negativo", "confianca": -0.3, "evidencia_curta": ""},
                ]
            }
        )
    )
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: fake)
    res = extrair_temas("texto", {})
    # 1.5 vira 1.0 (clamp), -0.3 < CONFIANCA_MINIMA → filtrado
    assert len(res) == 1
    assert res[0]["nome"] == "supra"
    assert res[0]["confianca"] == 1.0
    assert CONFIANCA_MINIMA == 0.4  # documenta o valor canônico
