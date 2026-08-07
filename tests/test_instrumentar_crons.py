"""Fatia 1 — instrumentação dos crons pagos: cada coleta REAL vira ColetaExecucao
(falha Apify → status='erro' → visível no Monitoramento), e o reaper fecha órfãs.
Coletor mockado (devolve dict, não toca DB no thread) — NENHUM run Apify.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.models.coleta_execucao import ColetaExecucao
from src.models.empresa import Empresa
from src.models.fonte import Fonte


def _emp(db_session, nome):
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.flush()
    return e


def _fonte_ra(db_session, e, **kw):
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="reclame_aqui",
        url="https://www.reclameaqui.com.br/x/",
        status="ativa",
        **kw,
    )
    db_session.add(f)
    db_session.flush()
    return f


# ── Scorecard ──────────────────────────────────────────────────────────────


def test_scorecard_cron_falha_cria_execucao_erro(db_session, monkeypatch):
    from scripts.coleta_scorecard_todas import main

    e = _emp(db_session, "SCfalha")
    f = _fonte_ra(db_session, e)
    db_session.commit()
    monkeypatch.setattr(
        "scripts.coleta_scorecard_todas.coletar_scorecard",
        lambda fo, **k: {"falhou_apify": True, "reputacao": False},
    )
    main(dry_run=False)
    db_session.expire_all()
    exe = db_session.query(ColetaExecucao).filter_by(fonte_id=f.id).one()
    assert exe.status == "erro"


def test_scorecard_cron_sucesso_cria_execucao_concluido(db_session, monkeypatch):
    from scripts.coleta_scorecard_todas import main

    e = _emp(db_session, "SCok")
    f = _fonte_ra(db_session, e)
    db_session.commit()
    monkeypatch.setattr(
        "scripts.coleta_scorecard_todas.coletar_scorecard",
        lambda fo, **k: {"reputacao": True, "coletados": 1},
    )
    main(dry_run=False)
    db_session.expire_all()
    exe = db_session.query(ColetaExecucao).filter_by(fonte_id=f.id).one()
    assert exe.status == "concluido"


def test_scorecard_cron_cadencia_nao_cria_execucao(db_session, monkeypatch):
    """Skip de cadência (7d) → nem chama o coletor, nem cria execução (sem ruído diário)."""
    from scripts.coleta_scorecard_todas import main
    from src.models.fonte_reputacao import FonteReputacao

    e = _emp(db_session, "SCcad")
    f = _fonte_ra(db_session, e)
    db_session.add(
        FonteReputacao(
            fonte_id=f.id, empresa_id=e.id, provedor="reclame_aqui", coletado_em=datetime.utcnow()
        )
    )
    db_session.commit()
    chamou = []
    monkeypatch.setattr(
        "scripts.coleta_scorecard_todas.coletar_scorecard",
        lambda fo, **k: chamou.append(1) or {"reputacao": True},
    )
    main(dry_run=False)
    db_session.expire_all()
    assert db_session.query(ColetaExecucao).filter_by(fonte_id=f.id).count() == 0
    assert chamou == []


# ── Coortes ────────────────────────────────────────────────────────────────


def _stub_coortes(monkeypatch, fonte_id, plano):
    monkeypatch.setattr(
        "scripts.coleta_coortes_todas.fontes_ra_elegiveis", lambda modo=None: [fonte_id]
    )
    monkeypatch.setattr("scripts.coleta_coortes_todas._volume_mes", lambda s, fid: 100)
    monkeypatch.setattr(
        "scripts.coleta_coortes_todas.planejar_coortes", lambda s, fonte, force=False: plano
    )


def test_coortes_amostra_falha_cria_execucao_erro(db_session, monkeypatch):
    from scripts.coleta_coortes_todas import main

    e = _emp(db_session, "COamostra")
    f = _fonte_ra(db_session, e, ra_coortes_ativas=1, ra_modo="completo")
    db_session.commit()
    _stub_coortes(monkeypatch, f.id, [{"acao": "amostra", "cap": 250}])
    monkeypatch.setattr(
        "scripts.coleta_coortes_todas.coletar_amostra",
        lambda fo, force=False: {"casos_novos": 0, "casos_atualizados": 0, "falhou_apify": True},
    )
    main(dry_run=False)
    db_session.expire_all()
    exe = db_session.query(ColetaExecucao).filter_by(fonte_id=f.id).one()
    assert exe.status == "erro"


def test_coortes_multibloco_qualquer_falha_agrega_erro(db_session, monkeypatch):
    """Multi-bloco: 1 execução por-fonte; se QUALQUER coorte falhou → agregado 'erro'."""
    from scripts.coleta_coortes_todas import main

    e = _emp(db_session, "COmulti")
    f = _fonte_ra(db_session, e, ra_coortes_ativas=2, ra_modo="completo")
    db_session.commit()
    plano = [
        {
            "acao": "coletar",
            "coorte": 202606,
            "date_from": "2026-06-01",
            "date_to": "2026-06-30",
            "idade_meses": 2,
            "n_nao_terminais": 0,
        },
        {
            "acao": "coletar",
            "coorte": 202607,
            "date_from": "2026-07-01",
            "date_to": "2026-07-31",
            "idade_meses": 1,
            "n_nao_terminais": 0,
        },
    ]
    _stub_coortes(monkeypatch, f.id, plano)
    calls = {"n": 0}

    def _coorte(fo, p, **k):
        calls["n"] += 1
        falhou = calls["n"] == 2  # 2º bloco falha
        return {"casos_novos": 0, "casos_atualizados": 0, "fechada": True, "falhou_apify": falhou}

    monkeypatch.setattr("scripts.coleta_coortes_todas.coletar_coorte", _coorte)
    main(dry_run=False)
    db_session.expire_all()
    exe = db_session.query(ColetaExecucao).filter_by(fonte_id=f.id).one()
    assert exe.status == "erro"  # qualquer bloco falhou → agregado erro
    assert calls["n"] == 2  # os dois blocos rodaram (1 execução, não 2)


def test_coortes_multibloco_todos_ok_concluido(db_session, monkeypatch):
    from scripts.coleta_coortes_todas import main

    e = _emp(db_session, "COok")
    f = _fonte_ra(db_session, e, ra_coortes_ativas=1, ra_modo="completo")
    db_session.commit()
    plano = [
        {
            "acao": "coletar",
            "coorte": 202606,
            "date_from": "2026-06-01",
            "date_to": "2026-06-30",
            "idade_meses": 2,
            "n_nao_terminais": 0,
        },
    ]
    _stub_coortes(monkeypatch, f.id, plano)
    monkeypatch.setattr(
        "scripts.coleta_coortes_todas.coletar_coorte",
        lambda fo, p, **k: {"casos_novos": 0, "casos_atualizados": 0, "fechada": True},
    )
    main(dry_run=False)
    db_session.expire_all()
    exe = db_session.query(ColetaExecucao).filter_by(fonte_id=f.id).one()
    assert exe.status == "concluido"


# ── Reaper (housekeeping — só UPDATE, sem Apify) ────────────────────────────


def test_reaper_marca_orfa_e_preserva_recente(db_session):
    from src.coletor.orquestrador import re_marca_orfas

    e = _emp(db_session, "Reaper")
    f = _fonte_ra(db_session, e)
    db_session.add(
        ColetaExecucao(
            empresa_id=e.id,
            fonte_id=f.id,
            status="rodando",
            iniciado_em=datetime.utcnow() - timedelta(hours=2),  # órfã (>1h)
        )
    )
    db_session.add(
        ColetaExecucao(
            empresa_id=e.id,
            fonte_id=f.id,
            status="rodando",
            iniciado_em=datetime.utcnow() - timedelta(minutes=5),  # recente
        )
    )
    db_session.commit()
    n = re_marca_orfas(limite_segundos=3600)  # 1h
    db_session.expire_all()
    assert n == 1
    assert db_session.query(ColetaExecucao).filter_by(status="erro").count() == 1
    assert db_session.query(ColetaExecucao).filter_by(status="rodando").count() == 1
