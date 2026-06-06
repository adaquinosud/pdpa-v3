"""Tests do CP purge-linkedin-dup: comando ``purgar-verbatins-fonte``.

Guarda fonte-inativa, dry-run, hard-delete + CASCADE (embeddings), e a remoção
opcional do cadastro (fonte + local órfão)."""

from __future__ import annotations

from datetime import datetime

from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.local import Local
from src.models.temas import VerbatimEmbedding
from src.models.verbatim import Verbatim


def _setup(db_session, fonte_ativa=False):
    ts = datetime.utcnow().timestamp()
    e = Empresa(nome=f"EPurge-{ts}", setor="aeroporto")
    db_session.add(e)
    db_session.commit()
    locA = Local(empresa_id=e.id, nome="Loja A (purge)")
    locB = Local(empresa_id=e.id, nome="Loja B (keep)")
    db_session.add_all([locA, locB])
    db_session.commit()
    f_purge = Fonte(
        empresa_id=e.id,
        entidade_tipo="local",
        entidade_id=locA.id,
        conector_tipo="linkedin",
        url="bh-airport",
        ativo=fonte_ativa,
    )
    f_keep = Fonte(
        empresa_id=e.id,
        entidade_tipo="local",
        entidade_id=locB.id,
        conector_tipo="google",
        url=f"ChIJkeep{ts}",
        ativo=True,
    )
    db_session.add_all([f_purge, f_keep])
    db_session.commit()
    vs = []
    for i in range(3):
        v = Verbatim(
            empresa_id=e.id,
            fonte_id=f_purge.id,
            local_id=locA.id,
            texto=f"dup{i}",
            subpilar="Pa1",
            tipo="conversivel",
            tem_texto=True,
            data_criacao_original=datetime(2026, 5, 1),
            hash_dedup=f"hp{i}-{ts}",
        )
        db_session.add(v)
        db_session.flush()
        db_session.add(VerbatimEmbedding(verbatim_id=v.id, modelo="m", vetor=b"\x00"))
        vs.append(v)
    vkeep = Verbatim(
        empresa_id=e.id,
        fonte_id=f_keep.id,
        local_id=locB.id,
        texto="keep",
        subpilar="D1",
        tipo="promotor",
        tem_texto=True,
        data_criacao_original=datetime(2026, 5, 1),
        hash_dedup=f"hk-{ts}",
    )
    db_session.add(vkeep)
    db_session.commit()
    return e.id, locA.id, locB.id, f_purge.id, f_keep.id, [v.id for v in vs], vkeep.id


def _cli(app, args):
    return app.test_cli_runner().invoke(args=["purgar-verbatins-fonte"] + args)


def test_guarda_recusa_fonte_ativa(app, db_session):
    e_id, locA_id, locB_id, fp_id, fk_id, ids, vkeep_id = _setup(db_session, fonte_ativa=True)
    res = _cli(app, ["--fonte-id", str(fp_id)])
    assert res.exit_code != 0
    assert "ATIVA" in res.output
    db_session.expire_all()
    assert db_session.query(Verbatim).filter_by(fonte_id=fp_id).count() == 3  # nada apagado


def test_dry_run_nao_apaga(app, db_session):
    e_id, locA_id, locB_id, fp_id, fk_id, ids, vkeep_id = _setup(db_session)
    res = _cli(app, ["--fonte-id", str(fp_id), "--dry-run"])
    assert res.exit_code == 0
    assert "verbatins a remover: 3" in res.output
    db_session.expire_all()
    assert db_session.query(Verbatim).filter_by(fonte_id=fp_id).count() == 3


def test_apaga_verbatins_e_cascade_embeddings(app, db_session):
    e_id, locA_id, locB_id, fp_id, fk_id, ids, vkeep_id = _setup(db_session)
    res = _cli(app, ["--fonte-id", str(fp_id)])
    assert res.exit_code == 0
    db_session.expire_all()
    assert db_session.query(Verbatim).filter_by(fonte_id=fp_id).count() == 0  # verbatins sumiram
    assert (
        db_session.query(VerbatimEmbedding).filter(VerbatimEmbedding.verbatim_id.in_(ids)).count()
        == 0
    )  # CASCADE removeu embeddings
    assert db_session.query(Verbatim).filter_by(fonte_id=fk_id).count() == 1  # outra fonte intacta
    assert db_session.get(Fonte, fp_id) is not None  # sem --remover-cadastro: fonte/local ficam
    assert db_session.get(Local, locA_id) is not None


def test_remover_cadastro_apaga_fonte_e_local_orfao(app, db_session):
    e_id, locA_id, locB_id, fp_id, fk_id, ids, vkeep_id = _setup(db_session)
    res = _cli(app, ["--fonte-id", str(fp_id), "--remover-cadastro"])
    assert res.exit_code == 0
    assert "[órfão]" in res.output
    db_session.expire_all()
    assert db_session.get(Fonte, fp_id) is None  # fonte removida
    assert db_session.get(Local, locA_id) is None  # local órfão removido
    assert db_session.get(Local, locB_id) is not None  # outro local intacto
    assert db_session.get(Fonte, fk_id) is not None  # outra fonte intacta
