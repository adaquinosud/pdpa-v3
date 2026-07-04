"""Correção retroativa de grão RA: casos/verbatins de um local viram empresa-wide
(local_id=NULL) e o cache de temas do agrupamento órfão é removido — sem tocar o
cache company-wide (NULL)."""

from __future__ import annotations

from datetime import date

from src.coletor.regrao_ra import regrao_empresa_wide
from src.models.agrupamento import Agrupamento
from src.models.caso import Caso
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.local import Local
from src.models.temas import TemaCache
from src.models.verbatim import Verbatim


def _cache(empresa_id, agrupamento_id, label):
    return TemaCache(
        empresa_id=empresa_id,
        agrupamento_id=agrupamento_id,
        subpilar="D2",
        tipo="detrator",
        tema_label=label,
        volume=3,
        percentual=0.5,
        periodo_inicio=date(2026, 1, 1),
        periodo_fim=date(2026, 6, 1),
        hash_escopo=f"h-{agrupamento_id}-{label}",
    )


def _setup(db_session):
    e = Empresa(nome=f"ERAgr-{id(db_session)}")
    db_session.add(e)
    db_session.flush()
    ag = Agrupamento(empresa_id=e.id, nome="Institucional")
    db_session.add(ag)
    db_session.flush()
    loc = Local(empresa_id=e.id, agrupamento_id=ag.id, nome="ReclameAqui")
    db_session.add(loc)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="local",
        entidade_id=loc.id,
        conector_tipo="reclame_aqui",
        url="https://www.reclameaqui.com.br/empresa/club-med/",
        status="ativa",
    )
    db_session.add(f)
    db_session.flush()
    return e, ag, loc, f


def test_regrao_move_grao_e_limpa_cache_do_agrupamento(db_session):
    e, ag, loc, f = _setup(db_session)
    # 2 casos + verbatins carimbados no local (grão errado)
    for oid in ("R1", "R2"):
        c = Caso(empresa_id=e.id, fonte_id=f.id, origem_id=oid, local_id=loc.id)
        db_session.add(c)
        db_session.flush()
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                caso_id=c.id,
                local_id=loc.id,
                texto="x",
                tem_texto=True,
            )
        )
    db_session.add(_cache(e.id, ag.id, "reserva"))  # cache do RA (Institucional)
    db_session.add(_cache(e.id, None, "geral"))  # cache company-wide — deve sobreviver
    db_session.commit()

    r = regrao_empresa_wide(f.id)
    assert r == {
        "empresa_id": e.id,
        "agrupamento_antigo": ag.id,
        "verbatins": 2,
        "casos": 2,
        "cache_removido": 1,
    }
    db_session.expire_all()
    assert db_session.query(Verbatim).filter_by(fonte_id=f.id, local_id=None).count() == 2
    assert db_session.query(Caso).filter_by(fonte_id=f.id, local_id=None).count() == 2
    # cache do agrupamento sumiu; o company-wide continua
    assert db_session.query(TemaCache).filter_by(empresa_id=e.id, agrupamento_id=ag.id).count() == 0
    assert db_session.query(TemaCache).filter_by(empresa_id=e.id, agrupamento_id=None).count() == 1


def test_regrao_idempotente(db_session):
    e, ag, loc, f = _setup(db_session)
    c = Caso(empresa_id=e.id, fonte_id=f.id, origem_id="R1", local_id=loc.id)
    db_session.add(c)
    db_session.flush()
    db_session.add(
        Verbatim(
            empresa_id=e.id, fonte_id=f.id, caso_id=c.id, local_id=loc.id, texto="x", tem_texto=True
        )
    )
    db_session.commit()
    regrao_empresa_wide(f.id)
    r2 = regrao_empresa_wide(f.id)  # 2ª vez: nada a mover
    assert r2["verbatins"] == 0 and r2["casos"] == 0 and r2["cache_removido"] == 0
