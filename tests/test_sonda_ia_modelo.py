"""G1 — modelo de dados da Reputação em IA (sonda_ia_*).

Cobre persistência + defaults, unique mensal (empresa, competência), os CHECKs
dos enums nossos (status, pergunta_tipo, subpilar/tipo da avaliação) e o unique
da leitura por execução. FRONTEIRA: zero FK pra verbatins (só empresa).
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.empresa import Empresa
from src.models.sonda_ia import (
    SondaIAAvaliacao,
    SondaIAExecucao,
    SondaIALeitura,
    SondaIAResposta,
)

_k = [0]


def _empresa(db_session):
    e = Empresa(nome=f"EIA-{id(db_session)}-{_k[0]}")
    _k[0] += 1
    db_session.add(e)
    db_session.flush()
    return e


def _exec(db_session, e, competencia="2026-07", status="pendente", **kw):
    x = SondaIAExecucao(empresa_id=e.id, competencia=competencia, status=status, **kw)
    db_session.add(x)
    db_session.flush()
    return x


def _resposta(db_session, e, x, pergunta_tipo="avaliacao"):
    r = SondaIAResposta(
        execucao_id=x.id,
        empresa_id=e.id,
        vendor="claude",
        modelo="claude-sonnet-4-6",
        pergunta_tipo=pergunta_tipo,
        repeticao=1,
        resposta_texto="…",
        tokens_in=100,
        tokens_out=200,
    )
    db_session.add(r)
    db_session.flush()
    return r


# ── Execução ─────────────────────────────────────────────────────────────────


def test_execucao_persiste_e_defaults(db_session):
    e = _empresa(db_session)
    x = _exec(db_session, e, modelos_json='["claude","gpt","gemini"]', repeticoes=3)
    assert x.id is not None and x.iniciado_em is not None
    assert x.status == "pendente" and x.concluido_em is None


def test_execucao_unica_por_mes(db_session):
    e = _empresa(db_session)
    _exec(db_session, e, "2026-07")
    with pytest.raises(IntegrityError):
        _exec(db_session, e, "2026-07")  # 2 execuções no mesmo mês → viola unique


def test_execucao_status_check(db_session):
    e = _empresa(db_session)
    with pytest.raises(IntegrityError):
        _exec(db_session, e, "2026-08", status="inventado")


# ── Resposta ─────────────────────────────────────────────────────────────────


def test_resposta_pergunta_check(db_session):
    e = _empresa(db_session)
    x = _exec(db_session, e)
    assert _resposta(db_session, e, x, "identidade").id is not None
    bad = SondaIAResposta(
        execucao_id=x.id,
        empresa_id=e.id,
        vendor="gpt",
        modelo="gpt-5",
        pergunta_tipo="lixo",
        repeticao=1,
    )
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        db_session.flush()


# ── Avaliação (régua PDPA) ───────────────────────────────────────────────────


def test_avaliacao_subpilar_e_tipo_check(db_session):
    e = _empresa(db_session)
    x = _exec(db_session, e)
    r = _resposta(db_session, e, x)
    ok = SondaIAAvaliacao(
        resposta_id=r.id, empresa_id=e.id, subpilar="D2", tipo="detrator", tema_label="demora"
    )
    db_session.add(ok)
    db_session.flush()
    assert ok.id is not None
    bad = SondaIAAvaliacao(resposta_id=r.id, empresa_id=e.id, subpilar="ZZ", tipo="detrator")
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        db_session.flush()


# ── Leitura (síntese mensal) ─────────────────────────────────────────────────


def test_leitura_unica_por_execucao(db_session):
    e = _empresa(db_session)
    x = _exec(db_session, e)
    db_session.add(SondaIALeitura(execucao_id=x.id, empresa_id=e.id, competencia="2026-07"))
    db_session.flush()
    db_session.add(SondaIALeitura(execucao_id=x.id, empresa_id=e.id, competencia="2026-07"))
    with pytest.raises(IntegrityError):
        db_session.flush()
