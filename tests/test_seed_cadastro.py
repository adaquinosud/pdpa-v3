"""CP-seed-cadastro-prod: round-trip do seed do cadastro (export → import).

Prova o MECANISMO num banco de teste (não toca prod): export preserva contagens
e IDs; import recria as 4 tabelas com IDs preservados, FKs íntegras, idempotente
(2x = mesmo estado), e as sequences não colidem (sob PG prova o setval; sob
SQLite o rowid já avança).
"""

from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from scripts.seed_export import exportar
from scripts.seed_import import importar
from src.models.agrupamento import Agrupamento
from src.models.base import Base
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.local import Local


def _source_com_cadastro():
    """Engine SQLite in-memory de ORIGEM com 1 empresa(4) + 1 agrup(10) +
    1 local(20) + 1 fonte(30) — FKs encadeadas, IDs fixos."""
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Empresa(id=4, nome="Seed Co"))
        s.add(Agrupamento(id=10, empresa_id=4, nome="Ramo X"))
        s.flush()
        s.add(Local(id=20, empresa_id=4, agrupamento_id=10, nome="Loja 1"))
        s.flush()
        s.add(
            Fonte(
                id=30,
                empresa_id=4,
                entidade_tipo="local",
                entidade_id=20,
                conector_tipo="google",
                url="ChIJ-x",
            )
        )
        s.commit()
    return eng


def test_export_conta_e_preserva_ids():
    data = exportar(_source_com_cadastro(), 4)
    contagens = {t: len(r) for t, r in data["tabelas"].items()}
    assert contagens == {"empresas": 1, "agrupamentos": 1, "locais": 1, "fontes": 1}
    assert data["tabelas"]["empresas"][0]["id"] == 4
    # FK preservada já no export (fonte aponta pro local 20)
    assert data["tabelas"]["fontes"][0]["entidade_id"] == 20
    assert data["tabelas"]["locais"][0]["agrupamento_id"] == 10


def test_import_recria_preserva_fk_e_e_idempotente(db_session):
    data = exportar(_source_com_cadastro(), 4)
    conn = db_session.connection()

    r1 = importar(data, conn)
    assert r1["status"] == "ok"
    assert r1["inseridos"] == {"empresas": 1, "agrupamentos": 1, "locais": 1, "fontes": 1}

    # IDs preservados + FKs íntegras no alvo
    assert db_session.get(Empresa, 4) is not None
    assert db_session.get(Local, 20).agrupamento_id == 10
    f = db_session.get(Fonte, 30)
    assert f.entidade_id == 20 and f.empresa_id == 4

    # Idempotente: 2ª execução é no-op (empresa já existe), sem duplicar
    r2 = importar(data, conn)
    assert r2["status"] == "skip"
    n = db_session.execute(
        select(func.count()).select_from(Empresa.__table__).where(Empresa.__table__.c.id == 4)
    ).scalar()
    assert n == 1


def test_import_sequence_nao_colide_com_id_migrado(db_session):
    """Após importar com IDs explícitos, um novo cadastro (sem id) recebe id >
    o maior migrado — sob PG prova o setval; sob SQLite o rowid já avança."""
    data = exportar(_source_com_cadastro(), 4)
    importar(data, db_session.connection())

    novo = Local(empresa_id=4, nome="Loja Nova")
    db_session.add(novo)
    db_session.flush()
    assert novo.id > 20
