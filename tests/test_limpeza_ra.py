"""Limpeza da contaminação RA (slug errado): apaga casos + verbatins + derivados
(verbatim_temas) da fonte + zera o TemaCache da empresa; preserva o resto.
Prova com contagens antes/depois (a limpeza real roda em prod via script)."""

from __future__ import annotations

from datetime import date

from src.coletor.limpeza_ra import limpar_contaminacao_ra
from src.models.caso import Caso
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.temas import Tema, TemaCache, VerbatimTema
from src.models.verbatim import Verbatim

_k = [0]


def _fonte(db_session, e, conector, url):
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo=conector,
        url=url,
        autenticacao_tipo="publica",
        status="ativa",
    )
    db_session.add(f)
    db_session.flush()
    return f


def _verb(db_session, e, f, sub="D2", tipo="detrator"):
    _k[0] += 1
    v = Verbatim(
        empresa_id=e.id, fonte_id=f.id, texto="x", subpilar=sub, tipo=tipo, hash_dedup=f"h{_k[0]}"
    )
    db_session.add(v)
    db_session.flush()
    return v


def test_limpeza_zera_contaminacao_e_preserva_legitimo(db_session):
    e = Empresa(nome=f"ClubMed-{id(db_session)}")
    db_session.add(e)
    db_session.flush()
    # fonte RA contaminada (Sebracom): 3 casos + 3 verbatins + verbatim_temas
    ra = _fonte(db_session, e, "reclame_aqui", "https://www.reclameaqui.com.br/empresa/club-med/")
    tema = Tema(empresa_id=e.id, nome="cobrança indevida", slug="cobranca-indevida")
    db_session.add(tema)
    db_session.flush()
    for i in range(3):
        v = _verb(db_session, e, ra)
        db_session.add(Caso(empresa_id=e.id, fonte_id=ra.id, origem_id=f"S{i}"))
        db_session.add(VerbatimTema(verbatim_id=v.id, tema_id=tema.id, confianca=0.9, origem="llm"))
    # TemaCache da empresa (cluster contaminado)
    db_session.add(
        TemaCache(
            empresa_id=e.id,
            agrupamento_id=None,
            subpilar="D2",
            tipo="detrator",
            tema_label="cobrança",
            volume=3,
            percentual=0.5,
            periodo_inicio=date(2026, 1, 1),
            periodo_fim=date(2026, 6, 1),
            hash_escopo="h",
        )
    )
    # fonte LEGÍTIMA (google) — 2 verbatins que devem sobreviver
    g = _fonte(db_session, e, "google", "u")
    _verb(db_session, e, g, sub="Pa1", tipo="promotor")
    _verb(db_session, e, g, sub="Pa1", tipo="promotor")
    db_session.commit()

    r = limpar_contaminacao_ra(ra.id)
    assert r["empresa_id"] == e.id and "empresa/club-med" in r["url"]
    # ANTES tinha contaminação; DEPOIS zerou
    assert r["antes"] == {
        "casos_fonte": 3,
        "verbatins_fonte": 3,
        "verbatim_temas_fonte": 3,
        "tema_cache_empresa": 1,
    }
    assert r["depois"] == {
        "casos_fonte": 0,
        "verbatins_fonte": 0,
        "verbatim_temas_fonte": 0,
        "tema_cache_empresa": 0,
    }

    db_session.expire_all()
    # contaminação some
    assert db_session.query(Caso).filter_by(fonte_id=ra.id).count() == 0
    assert db_session.query(Verbatim).filter_by(fonte_id=ra.id).count() == 0
    assert db_session.query(TemaCache).filter_by(empresa_id=e.id).count() == 0
    # legítimo preservado
    assert db_session.query(Verbatim).filter_by(fonte_id=g.id).count() == 2


def test_limpeza_fonte_inexistente(db_session):
    assert "erro" in limpar_contaminacao_ra(999999)
