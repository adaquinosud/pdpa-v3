"""Modelo AvaliadorAnalise: defaults que importam (custo nunca nulo) e tipo efetivo."""

from __future__ import annotations

from src.models.avaliador import STATUS_PENDENTE, AvaliadorAnalise
from src.models.empresa import Empresa


def test_defaults_e_tipo_efetivo(db_session):
    emp = Empresa(nome="Empresa Teste")
    db_session.add(emp)
    db_session.flush()
    a = AvaliadorAnalise(
        empresa_id=emp.id,
        arquivo_nome="proposta.pptx",
        arquivo_hash="0" * 64,
        arquivo_formato="pptx",
        n_paginas=3,
        modelo="claude-sonnet-4-5-20250929",
        regua_versao="2026-10-12f",
        prompt_versao="v1",
    )
    db_session.add(a)
    db_session.flush()
    db_session.refresh(a)
    assert a.custo_usd == 0.0 and a.tokens_in == 0
    assert a.status == STATUS_PENDENTE
    assert a.resultado_json == "{}" and a.paginas_sem_texto_json == "[]"
    a.tipo_detectado = "institucional"
    assert a.tipo == "institucional"
    a.tipo_corrigido = "proposta"
    assert a.tipo == "proposta"
