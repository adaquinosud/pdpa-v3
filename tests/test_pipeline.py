"""Testes do pipeline determinístico de coleta (``src/coletor/pipeline.py``).

A coleta NÃO classifica via LLM inline: verbatins com texto entram com
``subpilar=None`` e são classificados no pós-coleta (``classificar_pendentes``).
Só o caminho ratings-only (sem texto + nota) é classificado inline, por
heurística determinística — sem chamar a API Anthropic.
"""

from __future__ import annotations

import pytest

from src.coletor.pipeline import (
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


# ── processar_verbatim_coletado ─────────────────────────────────────────


def test_processar_texto_vazio_retorna_none(fonte_local):
    assert processar_verbatim_coletado(texto="", fonte=fonte_local) is None
    assert processar_verbatim_coletado(texto="   ", fonte=fonte_local) is None


def test_processar_texto_curto_retorna_none(fonte_local):
    """``MIN_CHARS_PARA_PROCESSAR = 3`` rejeita textos com <3 chars."""
    assert processar_verbatim_coletado(texto="ok", fonte=fonte_local) is None


def test_processar_local_via_fonte_local(fonte_local):
    """Fonte com entidade_tipo='local' → verbatim recebe local_id determinístico."""
    local_id_esperado = fonte_local.entidade_id
    v = processar_verbatim_coletado(texto="Atendimento ótimo", fonte=fonte_local)
    assert v is not None
    assert v.local_id == local_id_esperado


def test_processar_sem_local_quando_fonte_empresa(fonte_empresa):
    """Fonte com entidade_tipo='empresa' → verbatim com local_id=None."""
    v = processar_verbatim_coletado(texto="Atendimento ótimo", fonte=fonte_empresa)
    assert v is not None
    assert v.local_id is None


def test_processar_dedup(fonte_local):
    """Segunda chamada com mesmo (texto, fonte, autor) retorna None."""
    v1 = processar_verbatim_coletado(texto="Bom", fonte=fonte_local, autor="Maria")
    assert v1 is not None
    v2 = processar_verbatim_coletado(texto="Bom", fonte=fonte_local, autor="Maria")
    assert v2 is None


def test_processar_dedup_diferentes_autores_inserem(fonte_local):
    """Mesmo texto + fonte mas autor diferente NÃO é duplicata."""
    v1 = processar_verbatim_coletado(texto="Bom", fonte=fonte_local, autor="Maria")
    v2 = processar_verbatim_coletado(texto="Bom", fonte=fonte_local, autor="João")
    assert v1 is not None
    assert v2 is not None


def test_processar_persiste_texto_integral_quando_grande(fonte_local):
    """Texto grande persiste íntegro no banco (sem truncar)."""
    texto_grande = "A" * 5000
    v = processar_verbatim_coletado(texto=texto_grande, fonte=fonte_local)
    assert v is not None
    assert len(v.texto) == len(texto_grande)  # íntegro
    assert v.texto == texto_grande


def test_processar_texto_entra_sem_classificacao(fonte_local):
    """Verbatim COM texto entra com subpilar=NULL — classificação fica para o
    pós-coleta (classificar_pendentes). A coleta não chama LLM inline."""
    v = processar_verbatim_coletado(texto="Atendimento ótimo da Maria", fonte=fonte_local)
    assert v is not None
    assert v.tem_texto is True
    assert v.subpilar is None
    assert v.tipo is None
    assert v.confianca is None
