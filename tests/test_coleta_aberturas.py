"""Frente ra-cron-aberturas: cron semanal de aberturas RA (modo padrão).

Testa a SELEÇÃO (filtro de modo, anti-colisão com o cron de coortes), o gate de 6d,
a instrumentação (ColetaExecucao + custo), a digestão pós-coleta e o exit code.
NENHUM run Apify: o coletor é mockado; _rodar_async não entra (chamada síncrona).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from scripts.coleta_aberturas_todas import main
from scripts.coleta_coortes_todas import fontes_ra_elegiveis
from src.models.caso import Caso
from src.models.coleta_execucao import ColetaExecucao
from src.models.empresa import Empresa
from src.models.fonte import Fonte


def _empresa(db_session: Session, nome: str) -> int:
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.commit()
    return e.id


def _fonte(db_session: Session, empresa_id: int, *, ra_modo="padrao", coortes=1, cap=None) -> int:
    f = Fonte(
        empresa_id=empresa_id,
        entidade_tipo="empresa",
        entidade_id=empresa_id,
        conector_tipo="reclame_aqui",
        url="https://www.reclameaqui.com.br/x/",
        ra_modo=ra_modo,
        ra_coortes_ativas=coortes,
        ra_max_casos=cap,
    )
    db_session.add(f)
    db_session.commit()
    return f.id


def _fake_amostra_ok(fonte, **kwargs):
    return {
        "modo": "amostra",
        "casos_novos": 5,
        "casos_atualizados": 2,
        "abandonados": 0,
        "nao_rastreado": 0,
        "custo_apify_centavos": 18,
        "amostra_cap": 250,
    }


def _fake_amostra_falha(fonte, **kwargs):
    return {"modo": "amostra", "casos_novos": 0, "casos_atualizados": 0, "falhou_apify": True}


def _mock_coleta(monkeypatch, fake, pos_recorder=None):
    monkeypatch.setattr("scripts.coleta_aberturas_todas.coletar_amostra", fake)
    rec = pos_recorder if pos_recorder is not None else []
    monkeypatch.setattr(
        "src.temas.pos_coleta.executar_pos_coleta", lambda eid, **kw: rec.append(eid) or None
    )
    return rec


def test_fontes_elegiveis_filtro_modo(db_session):
    """O seletor compartilhado filtra por modo: padrão inclui NULL; completo só completo."""
    emp = _empresa(db_session, "Filtro")
    pad = _fonte(db_session, emp, ra_modo="padrao")
    comp = _fonte(db_session, emp, ra_modo="completo")
    off = _fonte(db_session, emp, ra_modo="padrao", coortes=0)  # coortes=0 → fora
    nul = _fonte(db_session, emp, ra_modo="padrao")
    # server_default só age no INSERT — força NULL via UPDATE p/ testar o "NULL=padrão".
    db_session.query(Fonte).filter_by(id=nul).update({"ra_modo": None})
    db_session.commit()

    padrao = fontes_ra_elegiveis(modo="padrao")
    completo = fontes_ra_elegiveis(modo="completo")
    assert pad in padrao and nul in padrao  # padrão + NULL
    assert comp not in padrao and off not in padrao
    assert comp in completo and pad not in completo and nul not in completo


def test_aberturas_dry_run_nao_coleta(db_session, monkeypatch):
    """--dry-run não cria ColetaExecucao nem chama pós-coleta; retorna 0."""
    emp = _empresa(db_session, "Dry")
    _fonte(db_session, emp)
    rec = _mock_coleta(monkeypatch, _fake_amostra_ok)
    code = main(dry_run=True)
    assert code == 0
    db_session.expire_all()
    assert db_session.query(ColetaExecucao).count() == 0
    assert rec == []


def test_aberturas_coleta_instrumenta_e_digere(db_session, monkeypatch):
    """Coleta real (mock): cria ColetaExecucao com custo e roda o pós-coleta da empresa."""
    emp = _empresa(db_session, "Coleta")
    fid = _fonte(db_session, emp)
    rec = _mock_coleta(monkeypatch, _fake_amostra_ok)
    code = main(dry_run=False)
    assert code == 0
    db_session.expire_all()
    exe = db_session.query(ColetaExecucao).filter_by(fonte_id=fid).one()
    assert exe.status == "concluido" and exe.custo_apify_centavos == 18
    assert rec == [emp]  # pós-coleta rodou p/ a empresa coletada


def test_aberturas_gate_6d_pula(db_session, monkeypatch):
    """Fonte coletada há <6d → PULADA (não dispara, não cria ColetaExecucao)."""
    emp = _empresa(db_session, "Gate")
    fid = _fonte(db_session, emp)
    db_session.add(
        Caso(
            empresa_id=emp,
            fonte_id=fid,
            origem_id="G1",
            ultima_coleta=datetime.utcnow() - timedelta(days=3),  # dentro do cooldown de 6d
        )
    )
    db_session.commit()
    rec = _mock_coleta(monkeypatch, _fake_amostra_ok)
    code = main(dry_run=False)
    assert code == 0
    db_session.expire_all()
    assert db_session.query(ColetaExecucao).count() == 0  # pulada antes do dispatch
    assert rec == []


def test_aberturas_gate_6d_coleta_se_antigo(db_session, monkeypatch):
    """Última coleta há >6d → coleta normalmente."""
    emp = _empresa(db_session, "Gate antigo")
    fid = _fonte(db_session, emp)
    db_session.add(
        Caso(
            empresa_id=emp,
            fonte_id=fid,
            origem_id="G2",
            ultima_coleta=datetime.utcnow() - timedelta(days=8),
        )
    )
    db_session.commit()
    _mock_coleta(monkeypatch, _fake_amostra_ok)
    main(dry_run=False)
    db_session.expire_all()
    assert db_session.query(ColetaExecucao).filter_by(fonte_id=fid).count() == 1


def test_aberturas_exit_1_quando_tudo_falha(db_session, monkeypatch):
    """Elegíveis > 0 e nenhuma coletou (todas falharam) → exit 1 (Render marca failed)."""
    emp = _empresa(db_session, "Falha")
    _fonte(db_session, emp)
    _mock_coleta(monkeypatch, _fake_amostra_falha)
    assert main(dry_run=False) == 1


def test_aberturas_exit_0_quando_tudo_pulado(db_session, monkeypatch):
    """Todas puladas por cadência (sem falha) → exit 0 (pular é legítimo, não é erro)."""
    emp = _empresa(db_session, "Pulado")
    fid = _fonte(db_session, emp)
    db_session.add(
        Caso(
            empresa_id=emp,
            fonte_id=fid,
            origem_id="P1",
            ultima_coleta=datetime.utcnow() - timedelta(days=2),
        )
    )
    db_session.commit()
    _mock_coleta(monkeypatch, _fake_amostra_falha)
    assert main(dry_run=False) == 0


def test_coortes_seleciona_completo(db_session):
    """Anti-colisão: o cron de coortes passa a selecionar só ra_modo='completo'."""
    emp = _empresa(db_session, "Coortes")
    pad = _fonte(db_session, emp, ra_modo="padrao")
    comp = _fonte(db_session, emp, ra_modo="completo")
    completo = fontes_ra_elegiveis(modo="completo")
    assert comp in completo and pad not in completo
