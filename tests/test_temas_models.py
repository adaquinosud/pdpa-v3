"""Testes dos modelos de tema (Bloco 6 CP-1).

Cobre invariantes do schema: UNIQUE(empresa_id, slug), UNIQUE(verbatim_id, tema_id),
ON DELETE CASCADE empresa → temas, FK opcionais.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.local import Local
from src.models.temas import Tema, TemaMerge, VerbatimTema
from src.models.verbatim import Verbatim


def _empresa_local_verbatim(db_session, suffix):
    e = Empresa(nome=f"ETm-{suffix}", setor="varejo")
    db_session.add(e)
    db_session.commit()
    loc = Local(empresa_id=e.id, nome=f"L-{suffix}")
    db_session.add(loc)
    db_session.commit()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="local",
        entidade_id=loc.id,
        conector_tipo="google",
        url=f"ChIJ_tm_{suffix}",
    )
    db_session.add(f)
    db_session.commit()
    v = Verbatim(
        empresa_id=e.id,
        local_id=loc.id,
        fonte_id=f.id,
        texto=f"verbatim-{suffix}",
        data_criacao_original=datetime.utcnow() - timedelta(days=5),
        hash_dedup=f"h-tm-{suffix}",
        subpilar="Pa1",
        tipo="promotor",
    )
    db_session.add(v)
    db_session.commit()
    return e, loc, f, v


def test_tema_basico(db_session):
    e, _, _, _ = _empresa_local_verbatim(db_session, "basico")
    t = Tema(empresa_id=e.id, nome="Fila no check-in", slug="fila-no-check-in")
    db_session.add(t)
    db_session.commit()
    assert t.id is not None
    assert t.ativo is True
    assert t.descricao is None
    assert t.criado_por is None
    assert t.criado_em is not None


def test_tema_unique_slug_por_empresa(db_session):
    """B6 CP-1: UNIQUE(empresa_id, slug) impede duplicação no escopo da empresa."""
    e, _, _, _ = _empresa_local_verbatim(db_session, "uq1")
    db_session.add(Tema(empresa_id=e.id, nome="Fila check-in", slug="fila-check-in"))
    db_session.commit()
    db_session.add(Tema(empresa_id=e.id, nome="Fila no check-in", slug="fila-check-in"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_tema_mesmo_slug_em_empresas_diferentes_ok(db_session):
    """slug é único só dentro da empresa — outras empresas podem ter o mesmo."""
    e1, _, _, _ = _empresa_local_verbatim(db_session, "uq2a")
    e2, _, _, _ = _empresa_local_verbatim(db_session, "uq2b")
    db_session.add(Tema(empresa_id=e1.id, nome="Fila", slug="fila"))
    db_session.add(Tema(empresa_id=e2.id, nome="Fila", slug="fila"))
    db_session.commit()
    assert db_session.query(Tema).filter_by(slug="fila").count() == 2


def test_verbatim_tema_basico(db_session):
    e, _, _, v = _empresa_local_verbatim(db_session, "vt1")
    t = Tema(empresa_id=e.id, nome="Atendimento ágil", slug="atendimento-agil")
    db_session.add(t)
    db_session.commit()
    vt = VerbatimTema(
        verbatim_id=v.id,
        tema_id=t.id,
        confianca=0.85,
        origem="llm",
        evidencia_curta="resolvido em 5 minutos",
    )
    db_session.add(vt)
    db_session.commit()
    assert vt.id is not None
    assert vt.confianca == 0.85
    assert vt.origem == "llm"


def test_verbatim_tema_unique_pareado(db_session):
    """UNIQUE(verbatim_id, tema_id) — extrator pode rodar 2x sem duplicar."""
    e, _, _, v = _empresa_local_verbatim(db_session, "vt2")
    t = Tema(empresa_id=e.id, nome="Limpeza", slug="limpeza")
    db_session.add(t)
    db_session.commit()
    db_session.add(VerbatimTema(verbatim_id=v.id, tema_id=t.id, confianca=0.7, origem="llm"))
    db_session.commit()
    db_session.add(VerbatimTema(verbatim_id=v.id, tema_id=t.id, confianca=0.9, origem="llm"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_tema_merge_basico(db_session):
    e, _, _, _ = _empresa_local_verbatim(db_session, "mg1")
    t_origem = Tema(empresa_id=e.id, nome="Demora", slug="demora")
    t_destino = Tema(empresa_id=e.id, nome="Lentidão", slug="lentidao")
    db_session.add_all([t_origem, t_destino])
    db_session.commit()
    merge = TemaMerge(
        tema_origem_id=t_origem.id,
        tema_destino_id=t_destino.id,
        motivo="sinônimos — Loyall consolidou em 2026-05-24",
    )
    db_session.add(merge)
    db_session.commit()
    assert merge.id is not None
    assert merge.executado_em is not None


def test_tema_merge_cascade_quando_tema_origem_deletado(db_session):
    """Se algum dia o tema origem for deletado (CASCADE), o log também vai."""
    e, _, _, _ = _empresa_local_verbatim(db_session, "mg2")
    t_o = Tema(empresa_id=e.id, nome="A", slug="a-tm")
    t_d = Tema(empresa_id=e.id, nome="B", slug="b-tm")
    db_session.add_all([t_o, t_d])
    db_session.commit()
    m = TemaMerge(tema_origem_id=t_o.id, tema_destino_id=t_d.id)
    db_session.add(m)
    db_session.commit()
    m_id = m.id
    db_session.delete(t_o)
    db_session.commit()
    assert db_session.query(TemaMerge).filter_by(id=m_id).first() is None


def test_cascade_delete_empresa_remove_temas(db_session):
    """ON DELETE CASCADE no schema: empresa apagada → temas vão junto."""
    from sqlalchemy import text

    e, _, _, _ = _empresa_local_verbatim(db_session, "cas1")
    empresa_id = e.id  # captura antes do DELETE invalidar a instance
    db_session.add_all(
        [
            Tema(empresa_id=empresa_id, nome="T1", slug="t1-cas"),
            Tema(empresa_id=empresa_id, nome="T2", slug="t2-cas"),
        ]
    )
    db_session.commit()
    assert db_session.query(Tema).filter_by(empresa_id=empresa_id).count() == 2

    db_session.execute(text("DELETE FROM empresas WHERE id = :id"), {"id": empresa_id})
    db_session.commit()
    assert db_session.query(Tema).filter_by(empresa_id=empresa_id).count() == 0


def test_cascade_delete_verbatim_remove_verbatim_temas(db_session):
    """Apagar verbatim apaga vinculações em verbatim_temas (preserva temas)."""
    from sqlalchemy import text

    e, _, _, v = _empresa_local_verbatim(db_session, "cas2")
    t = Tema(empresa_id=e.id, nome="X", slug="x-cas")
    db_session.add(t)
    db_session.commit()
    db_session.add(VerbatimTema(verbatim_id=v.id, tema_id=t.id, confianca=0.6, origem="llm"))
    db_session.commit()
    v_id = v.id
    db_session.execute(text("DELETE FROM verbatins WHERE id = :id"), {"id": v_id})
    db_session.commit()
    assert db_session.query(VerbatimTema).filter_by(verbatim_id=v_id).count() == 0
    # Tema persiste
    assert db_session.query(Tema).filter_by(id=t.id).first() is not None
