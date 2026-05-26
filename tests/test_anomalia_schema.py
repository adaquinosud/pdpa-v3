"""Tests do Bloco 8 / Monitoramento ML CP-1: schema de anomalias + histórico."""

from __future__ import annotations

from src.models.anomalia import (
    AnomaliaDetectada,
    CruzamentoSnapshot,
    RatioMensal,
    TemaSnapshot,
)


def _empresa(client_loyall, nome):
    return client_loyall.post("/api/empresas/", json={"nome": nome}).get_json()["id"]


def test_anomalia_tema_sem_local(client_loyall, db_session):
    """Anomalia de tipo 'tema' não tem local_id (era NOT NULL no schema v2)."""
    e = _empresa(client_loyall, "EAnomTema")
    a = AnomaliaDetectada(
        empresa_id=e,
        tipo="tema",
        local_id=None,
        subpilar=None,
        chave="tema: demora bagagem",
        score_final=0.82,
        magnitude=3.1,
        direcao="negativa",
        severidade="critico",
        estado_validacao="pendente",
        periodo="2026-05",
    )
    db_session.add(a)
    db_session.commit()
    got = db_session.query(AnomaliaDetectada).filter_by(empresa_id=e).one()
    assert got.tipo == "tema"
    assert got.local_id is None
    assert got.severidade == "critico"
    assert got.direcao == "negativa"
    assert got.estado_validacao == "pendente"


def test_snapshots_e_ratio_roundtrip(client_loyall, db_session):
    e = _empresa(client_loyall, "ESnap")
    db_session.add_all(
        [
            TemaSnapshot(
                empresa_id=e,
                periodo="2026-05",
                tema_slug="demora-bagagem",
                tema_label="demora bagagem",
                volume=10,
                detrator=8,
                promotor=1,
                conversivel=1,
            ),
            CruzamentoSnapshot(
                empresa_id=e,
                periodo="2026-05",
                tema_label="infraestrutura aeroporto",
                tema_slug="infraestrutura-aeroporto",
                peso=22.3,
                n_subpilares_distintos=3,
                eh_semantico=False,
            ),
            RatioMensal(
                empresa_id=e,
                subpilar="D2",
                periodo="2026-05",
                promotor=3,
                conversivel=0,
                detrator=6,
                total=9,
                ratio=0.5,
            ),
        ]
    )
    db_session.commit()
    assert db_session.query(TemaSnapshot).filter_by(empresa_id=e).one().detrator == 8
    assert db_session.query(CruzamentoSnapshot).filter_by(empresa_id=e).one().peso == 22.3
    assert db_session.query(RatioMensal).filter_by(empresa_id=e).one().ratio == 0.5
