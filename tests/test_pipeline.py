"""Testes do pipeline determinístico de coleta (``src/coletor/pipeline.py``).

Todos os testes deste arquivo **mockam** ``classificar()`` — não chamam a
API Anthropic real. O comportamento do classifier é validado separadamente
pelo golden set (``tests/test_classifier.py`` com marker ``golden``).
"""

from __future__ import annotations

import pytest

from src.classifier.classifier_v3 import ResultadoClassificacao
from src.coletor.pipeline import (
    MAX_TEXTO_CHARS_CLASSIFIER,
    computar_hash_dedup,
    processar_verbatim_coletado,
)
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.local import Local


# ── computar_hash_dedup ─────────────────────────────────────────────────


def test_hash_dedup_deterministico():
    assert computar_hash_dedup("t", 1, "M") == computar_hash_dedup("t", 1, "M")


def test_hash_dedup_difere_por_texto():
    assert computar_hash_dedup("a", 1, "M") != computar_hash_dedup("b", 1, "M")


def test_hash_dedup_difere_por_fonte():
    assert computar_hash_dedup("t", 1, "M") != computar_hash_dedup("t", 2, "M")


def test_hash_dedup_difere_por_autor():
    assert computar_hash_dedup("t", 1, "M") != computar_hash_dedup("t", 1, "J")


def test_hash_dedup_autor_none_idempotente():
    assert computar_hash_dedup("t", 1, None) == computar_hash_dedup("t", 1, None)


def test_hash_dedup_apenas_200_chars_contam():
    """Texto > 200 chars: apenas os 200 primeiros contam no hash."""
    assert computar_hash_dedup("x" * 500, 1, None) == computar_hash_dedup("x" * 200, 1, None)


# ── Fixtures de Fonte ───────────────────────────────────────────────────


@pytest.fixture
def fonte_local(db_session):
    """Fonte com ``entidade_tipo='local'`` apontando para um Local."""
    empresa = Empresa(nome="EmpresaLocal", setor="cafeteria")
    db_session.add(empresa)
    db_session.commit()
    local = Local(empresa_id=empresa.id, nome="Filial 1")
    db_session.add(local)
    db_session.commit()
    fonte = Fonte(
        empresa_id=empresa.id,
        entidade_tipo="local",
        entidade_id=local.id,
        conector_tipo="google",
        url="ChIJxxx",
    )
    db_session.add(fonte)
    db_session.commit()
    return fonte


@pytest.fixture
def fonte_empresa(db_session):
    """Fonte com ``entidade_tipo='empresa'`` (sem local específico)."""
    empresa = Empresa(nome="EmpresaSemLocal", setor="varejo")
    db_session.add(empresa)
    db_session.commit()
    fonte = Fonte(
        empresa_id=empresa.id,
        entidade_tipo="empresa",
        entidade_id=empresa.id,
        conector_tipo="reclame_aqui",
        url="https://www.reclameaqui.com.br/test",
    )
    db_session.add(fonte)
    db_session.commit()
    return fonte


@pytest.fixture
def mock_classificar_pa1(monkeypatch):
    """Substitui ``classificar()`` por mock que retorna Pa1/promotor."""

    def fake(
        texto,
        empresa_nome=None,
        empresa_setor=None,
        fonte_tipo=None,
        local_nome=None,
        local_tipo=None,
    ):
        return ResultadoClassificacao(
            subpilar="Pa1",
            tipo="promotor",
            confianca=0.9,
            justificativa="mock pipeline test",
        )

    monkeypatch.setattr("src.coletor.pipeline.classificar", fake)
    return fake


# ── processar_verbatim_coletado ─────────────────────────────────────────


def test_processar_texto_vazio_retorna_none(fonte_local, mock_classificar_pa1):
    assert processar_verbatim_coletado(texto="", fonte=fonte_local) is None
    assert processar_verbatim_coletado(texto="   ", fonte=fonte_local) is None


def test_processar_texto_curto_retorna_none(fonte_local, mock_classificar_pa1):
    """``MIN_CHARS_PARA_PROCESSAR = 3`` rejeita textos com <3 chars."""
    assert processar_verbatim_coletado(texto="ok", fonte=fonte_local) is None


def test_processar_local_via_fonte_local(fonte_local, mock_classificar_pa1):
    """Fonte com entidade_tipo='local' → verbatim recebe local_id determinístico."""
    local_id_esperado = fonte_local.entidade_id
    v = processar_verbatim_coletado(texto="Atendimento ótimo", fonte=fonte_local)
    assert v is not None
    assert v.local_id == local_id_esperado


def test_processar_sem_local_quando_fonte_empresa(fonte_empresa, mock_classificar_pa1):
    """Fonte com entidade_tipo='empresa' → verbatim com local_id=None."""
    v = processar_verbatim_coletado(texto="Atendimento ótimo", fonte=fonte_empresa)
    assert v is not None
    assert v.local_id is None


def test_processar_dedup(fonte_local, mock_classificar_pa1):
    """Segunda chamada com mesmo (texto, fonte, autor) retorna None."""
    v1 = processar_verbatim_coletado(texto="Bom", fonte=fonte_local, autor="Maria")
    assert v1 is not None
    v2 = processar_verbatim_coletado(texto="Bom", fonte=fonte_local, autor="Maria")
    assert v2 is None


def test_processar_dedup_diferentes_autores_inserem(fonte_local, mock_classificar_pa1):
    """Mesmo texto + fonte mas autor diferente NÃO é duplicata."""
    v1 = processar_verbatim_coletado(texto="Bom", fonte=fonte_local, autor="Maria")
    v2 = processar_verbatim_coletado(texto="Bom", fonte=fonte_local, autor="João")
    assert v1 is not None
    assert v2 is not None


def test_processar_persiste_texto_integral_quando_grande(fonte_local, mock_classificar_pa1):
    """Texto > MAX_TEXTO_CHARS_CLASSIFIER persiste íntegro no banco."""
    texto_grande = "A" * (MAX_TEXTO_CHARS_CLASSIFIER + 1000)
    v = processar_verbatim_coletado(texto=texto_grande, fonte=fonte_local)
    assert v is not None
    assert len(v.texto) == len(texto_grande)  # íntegro
    assert v.texto == texto_grande


def test_processar_classificacao_recebe_texto_truncado(fonte_local, monkeypatch):
    """Pipeline trunca o texto em MAX_TEXTO_CHARS_CLASSIFIER ao chamar classifier."""
    capturado: dict = {}

    def fake(
        texto,
        empresa_nome=None,
        empresa_setor=None,
        fonte_tipo=None,
        local_nome=None,
        local_tipo=None,
    ):
        capturado["texto_recebido"] = texto
        return ResultadoClassificacao(
            subpilar="Pa1", tipo="promotor", confianca=0.9, justificativa=""
        )

    monkeypatch.setattr("src.coletor.pipeline.classificar", fake)

    texto_grande = "B" * (MAX_TEXTO_CHARS_CLASSIFIER + 500)
    v = processar_verbatim_coletado(texto=texto_grande, fonte=fonte_local)
    assert v is not None
    assert len(capturado["texto_recebido"]) == MAX_TEXTO_CHARS_CLASSIFIER


def test_processar_propaga_hints_classifier(fonte_local, monkeypatch):
    """Pipeline propaga empresa_nome, empresa_setor, fonte_tipo ao classifier."""
    capturado: dict = {}

    def fake(
        texto,
        empresa_nome=None,
        empresa_setor=None,
        fonte_tipo=None,
        local_nome=None,
        local_tipo=None,
    ):
        capturado.update(
            {
                "empresa_nome": empresa_nome,
                "empresa_setor": empresa_setor,
                "fonte_tipo": fonte_tipo,
            }
        )
        return ResultadoClassificacao(
            subpilar="Pa1", tipo="promotor", confianca=0.9, justificativa=""
        )

    monkeypatch.setattr("src.coletor.pipeline.classificar", fake)

    processar_verbatim_coletado(texto="Hello", fonte=fonte_local)

    assert capturado["empresa_nome"] == "EmpresaLocal"
    assert capturado["empresa_setor"] == "cafeteria"
    assert capturado["fonte_tipo"] == "google"


def test_processar_classificar_falha_persiste_sem_classificacao(fonte_local, monkeypatch):
    """Se classificar() levanta, verbatim persiste sem subpilar/tipo/confianca."""

    def fail(texto, **kwargs):
        raise RuntimeError("mock: classificador quebrou")

    monkeypatch.setattr("src.coletor.pipeline.classificar", fail)

    v = processar_verbatim_coletado(texto="Algum texto", fonte=fonte_local)
    assert v is not None
    assert v.subpilar is None
    assert v.tipo is None
    assert v.confianca is None
    # prompt_versao: o model tem ``default="v3.0"`` no column-level. Passar
    # explicitamente None ainda pode resolver pro default na ORM 2.x. O
    # importante é que os 3 campos acima estão NULL — sinal de "não
    # classificado". ``prompt_versao`` é só metadata de qual prompt rodaria.


def test_processar_classifier_resultado_populado(fonte_local, mock_classificar_pa1):
    """Em sucesso, verbatim recebe subpilar/tipo/confianca/prompt_versao."""
    v = processar_verbatim_coletado(texto="Atendimento ótimo da Maria", fonte=fonte_local)
    assert v is not None
    assert v.subpilar == "Pa1"
    assert v.tipo == "promotor"
    assert v.confianca == 0.9
    assert v.prompt_versao == "v3.1"  # bump: prompt local-aware (CP local-no-prompt)
