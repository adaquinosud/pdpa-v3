"""G2 — sonda multi-modelo: orquestra modelos × perguntas × N reps → respostas.

Callers injetados (fakes) — zero gasto de API. Cobre a gravação das respostas,
o custo agregado, a idempotência (execução concluída → skip) e a tolerância a
erro de um modelo. Os adapters reais (com cap de saída) são validados por smoke
live à parte.
"""

from __future__ import annotations

from src.models.empresa import Empresa
from src.models.sonda_ia import SondaIAExecucao, SondaIAResposta
from src.sonda_ia import adapters
from src.sonda_ia.sonda import PERGUNTAS, sondar_empresa


def _fake(vendor, modelo, tin=100, tout=200):
    def _c(prompt):
        return {
            "vendor": vendor,
            "modelo": modelo,
            "texto": f"{vendor}: {prompt[:15]}",
            "tokens_in": tin,
            "tokens_out": tout,
        }

    return _c


def _empresa(db_session, nome="Club Med"):
    e = Empresa(nome=f"{nome}-{id(db_session)}")
    db_session.add(e)
    db_session.commit()
    return e


def test_sondar_grava_respostas_e_custo(db_session):
    e = _empresa(db_session)
    callers = {
        "claude": _fake("claude", adapters.CLAUDE_MODEL),
        "gpt": _fake("gpt", adapters.GPT_MODEL),
    }
    stats = sondar_empresa(e.id, "2026-07", modelos=("claude", "gpt"), n=3, callers=callers)
    # 2 modelos × 3 perguntas × 3 reps = 18
    assert stats["respostas"] == 18 and stats["erros"] == 0
    assert stats["custo_usd"] > 0  # custo agregado dos tokens
    db_session.expire_all()
    assert db_session.query(SondaIAResposta).filter_by(empresa_id=e.id).count() == 18
    x = db_session.query(SondaIAExecucao).filter_by(empresa_id=e.id).one()
    assert x.status == "concluida" and x.concluido_em is not None and x.repeticoes == 3
    # todas as 3 perguntas presentes, por vendor
    tipos = {r.pergunta_tipo for r in db_session.query(SondaIAResposta).filter_by(empresa_id=e.id)}
    assert tipos == set(PERGUNTAS)


def test_sondar_idempotente(db_session):
    e = _empresa(db_session)
    callers = {"claude": _fake("claude", adapters.CLAUDE_MODEL)}
    sondar_empresa(e.id, "2026-07", modelos=("claude",), n=2, callers=callers)
    # 2ª chamada na mesma competência → skip (execução já concluída)
    stats = sondar_empresa(e.id, "2026-07", modelos=("claude",), n=2, callers=callers)
    assert stats["pulado"] is True and stats["respostas"] == 0
    db_session.expire_all()
    assert db_session.query(SondaIAResposta).filter_by(empresa_id=e.id).count() == 6  # 1×3×2


def test_sondar_tolera_erro_de_um_modelo(db_session):
    e = _empresa(db_session)

    def _boom(prompt):
        raise RuntimeError("api down")

    callers = {"claude": _fake("claude", adapters.CLAUDE_MODEL), "gemini": _boom}
    stats = sondar_empresa(e.id, "2026-07", modelos=("claude", "gemini"), n=2, callers=callers)
    # claude: 3×2=6 ok; gemini: 6 erros → não derruba o lote
    assert stats["respostas"] == 6 and stats["erros"] == 6
    db_session.expire_all()
    x = db_session.query(SondaIAExecucao).filter_by(empresa_id=e.id).one()
    assert x.status == "concluida"  # conclui mesmo com erros parciais


def test_adapters_registry_e_cap():
    """Estrutura: os 3 vendors registrados, cap de saída setado, preço p/ cada modelo."""
    assert set(adapters.ADAPTERS) == {"claude", "gpt", "gemini"}
    assert 0 < adapters.MAX_OUT_TOKENS <= 1000
    for m in (adapters.CLAUDE_MODEL, adapters.GPT_MODEL, adapters.GEMINI_MODEL):
        assert m in adapters.PRECO
