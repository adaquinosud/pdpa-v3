"""CP-noturna-toggle: o cron genérico varre só as empresas LIGADAS
(coleta_noturna_ativa=TRUE) com ≥1 fonte ATIVA com coletor. Incremental por-fonte
fica intacto (reusa run_noturna.sh por empresa)."""

from __future__ import annotations

from scripts.coleta_noturna_todas import empresas_elegiveis
from src.models.empresa import Empresa
from src.models.fonte import Fonte


def _emp(db_session, nome, ativa):
    e = Empresa(nome=nome, coleta_noturna_ativa=ativa)
    db_session.add(e)
    db_session.flush()
    return e


def _fonte(db_session, emp_id, ativo=True, conector="google"):
    f = Fonte(
        empresa_id=emp_id,
        entidade_tipo="empresa",
        entidade_id=emp_id,
        conector_tipo=conector,
        url="x",
        ativo=ativo,
    )
    db_session.add(f)
    return f


def test_elegiveis_so_ligadas_com_fonte_ativa(db_session):
    on_ok = _emp(db_session, "LigadaComFonte", True)
    _fonte(db_session, on_ok.id, ativo=True)
    off = _emp(db_session, "DesligadaComFonte", False)
    _fonte(db_session, off.id, ativo=True)
    on_sem = _emp(db_session, "LigadaSemFonteAtiva", True)
    _fonte(db_session, on_sem.id, ativo=False)  # fonte inativa → não conta
    on_naocolet = _emp(db_session, "LigadaConectorSemColetor", True)
    _fonte(db_session, on_naocolet.id, ativo=True, conector="website")  # sem coletor
    db_session.commit()

    ids = {r[0] for r in empresas_elegiveis()}
    assert on_ok.id in ids  # ligada + fonte ativa coletável
    assert off.id not in ids  # desligada
    assert on_sem.id not in ids  # ligada mas sem fonte ATIVA
    assert on_naocolet.id not in ids  # ligada mas conector sem coletor (website)
