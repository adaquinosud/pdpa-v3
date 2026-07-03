"""F1 — modelo Caso + verbatins.caso_id (frente ReclameAqui, aditiva).

Cobre: persistência + defaults, unique (fonte_id, origem_id), CHECK do desfecho
(enum nosso), e o vínculo aditivo Verbatim.caso_id (o ÚNICO verbatim de valência
por caso = a description; nasce NULL nos verbatins legados).
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.caso import Caso
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim

_k = [0]


def _empresa_fonte(db_session, url="https://www.reclameaqui.com.br/club-med/"):
    e = Empresa(nome=f"ECaso-{id(db_session)}-{_k[0]}")
    _k[0] += 1
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="reclame_aqui",
        url=url,
        autenticacao_tipo="publica",
        status="ativa",
    )
    db_session.add(f)
    db_session.flush()
    return e, f


def _caso(db_session, e, f, origem_id="RA-1", **kw):
    c = Caso(empresa_id=e.id, fonte_id=f.id, origem_id=origem_id, **kw)
    db_session.add(c)
    db_session.flush()
    return c


def test_caso_persiste_com_defaults(db_session):
    e, f = _empresa_fonte(db_session)
    c = _caso(
        db_session,
        e,
        f,
        origem_id="EwRpootpeiLQRRw5",
        status="PENDING",
        status_label="Não respondida",
        solved=False,
        evaluated=False,
    )
    assert c.id is not None
    # defaults de bookkeeping preenchidos; campos lifecycle/classificador vazios
    assert c.primeira_coleta is not None and c.ultima_coleta is not None
    assert c.score is None and c.desfecho is None and c.thread_mudou_em is None


def test_unique_fonte_origem(db_session):
    """Mesma (fonte, origem_id) → viola o unique (idempotência do upsert)."""
    e, f = _empresa_fonte(db_session)
    _caso(db_session, e, f, origem_id="DUP")
    with pytest.raises(IntegrityError):
        _caso(db_session, e, f, origem_id="DUP")


def test_mesma_origem_em_fontes_distintas_ok(db_session):
    """O unique é POR fonte — a mesma id RA em outra fonte é permitida."""
    e, f1 = _empresa_fonte(db_session)
    _, f2 = _empresa_fonte(db_session, url="https://www.reclameaqui.com.br/outra/")
    _caso(db_session, e, f1, origem_id="X")
    _caso(db_session, e, f2, origem_id="X")  # não levanta


def test_desfecho_check(db_session):
    """desfecho aceita só o enum nosso; NULL passa; valor inventado viola CHECK."""
    e, f = _empresa_fonte(db_session)
    _caso(db_session, e, f, origem_id="ok1", desfecho="resolvido")
    _caso(db_session, e, f, origem_id="ok2", desfecho="abandonado")
    _caso(db_session, e, f, origem_id="ok3", desfecho=None)
    with pytest.raises(IntegrityError):
        _caso(db_session, e, f, origem_id="bad", desfecho="inventado")


def test_verbatim_caso_id_aditivo(db_session):
    """caso_id nasce NULL no verbatim legado; a description aponta pro Caso."""
    e, f = _empresa_fonte(db_session)
    c = _caso(db_session, e, f, origem_id="V1")
    # verbatim comum (legado): caso_id None
    v0 = Verbatim(empresa_id=e.id, fonte_id=f.id, texto="review comum", hash_dedup="h0")
    db_session.add(v0)
    db_session.flush()
    assert v0.caso_id is None
    # a description da reclamação = único verbatim de valência do caso
    v = Verbatim(
        empresa_id=e.id,
        fonte_id=f.id,
        texto="reclamação inicial",
        caso_id=c.id,
        review_id_externo="EwRpootpeiLQRRw5",
        hash_dedup="h1",
    )
    db_session.add(v)
    db_session.flush()
    assert v.caso_id == c.id
