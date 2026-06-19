"""Testes do CLI flask retencao-aplicar (Bloco 4 CP-D, MEC 2)."""

from __future__ import annotations

from datetime import datetime, timedelta

from src.models.evento_manutencao import EventoManutencao
from src.models.verbatim import Verbatim


def _criar_verbatim(db_session, fonte_id, empresa_id, dias_atras, texto="t"):
    v = Verbatim(
        empresa_id=empresa_id,
        fonte_id=fonte_id,
        texto=texto,
        data_criacao_original=datetime.utcnow() - timedelta(days=dias_atras),
        hash_dedup=f"h-{texto}-{dias_atras}",
    )
    db_session.add(v)
    db_session.commit()
    return v


def _setup_fonte(client_loyall):
    """Cria empresa+local+fonte mínima e devolve (empresa_id, fonte_id)."""
    import uuid

    sfx = uuid.uuid4().hex[:6]
    e = client_loyall.post("/api/empresas/", json={"nome": f"Eret-{sfx}"}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ-ret-{sfx}"},
    ).get_json()
    return e["id"], f["id"]


def _invocar_cli(app, args):
    """Roda o comando ``flask retencao-aplicar`` via test runner do Click."""
    runner = app.test_cli_runner()
    return runner.invoke(args=["retencao-aplicar"] + args)


def test_retencao_dry_run_nao_apaga(app, db_session, client_loyall):
    """--dry-run conta mas não remove; evento fica com dry_run=True."""
    emp_id, fonte_id = _setup_fonte(client_loyall)
    _criar_verbatim(db_session, fonte_id, emp_id, dias_atras=900, texto="velho")
    _criar_verbatim(db_session, fonte_id, emp_id, dias_atras=30, texto="novo")

    result = _invocar_cli(app, ["--meses", "18", "--dry-run"])
    assert result.exit_code == 0
    assert "1 verbatins afetados" in result.output
    assert "dry-run" in result.output

    # Nada foi removido
    db_session.expire_all()
    assert db_session.query(Verbatim).count() == 2
    # Evento registrado com dry_run=True
    eventos = (
        db_session.query(EventoManutencao)
        .filter_by(tipo="retencao_verbatins")
        .order_by(EventoManutencao.id.desc())
        .all()
    )
    assert eventos
    assert eventos[0].dry_run is True
    assert eventos[0].qtd_afetada == 1


def test_retencao_apaga_acima_do_threshold(app, db_session, client_loyall):
    """Sem --dry-run os antigos são removidos; recentes ficam."""
    emp_id, fonte_id = _setup_fonte(client_loyall)
    _criar_verbatim(db_session, fonte_id, emp_id, dias_atras=900, texto="muito_velho")
    _criar_verbatim(db_session, fonte_id, emp_id, dias_atras=800, texto="velho")
    _criar_verbatim(db_session, fonte_id, emp_id, dias_atras=30, texto="recente")

    result = _invocar_cli(app, ["--meses", "18"])
    assert result.exit_code == 0
    assert "2 verbatins afetados" in result.output

    db_session.expire_all()
    restantes = db_session.query(Verbatim).all()
    assert len(restantes) == 1
    assert restantes[0].texto == "recente"

    eventos = (
        db_session.query(EventoManutencao)
        .filter_by(tipo="retencao_verbatins")
        .order_by(EventoManutencao.id.desc())
        .all()
    )
    assert eventos[0].dry_run is False
    assert eventos[0].qtd_afetada == 2


def test_retencao_default_via_env(app, db_session, client_loyall, monkeypatch):
    """Sem --meses, usa env PDPA_RETENCAO_MESES."""
    monkeypatch.setenv("PDPA_RETENCAO_MESES", "12")
    emp_id, fonte_id = _setup_fonte(client_loyall)
    _criar_verbatim(db_session, fonte_id, emp_id, dias_atras=400, texto="400d_atras")
    _criar_verbatim(db_session, fonte_id, emp_id, dias_atras=30, texto="recente")

    # 12 meses ≈ 360 dias. 400d atrás é velho.
    result = _invocar_cli(app, ["--dry-run"])
    assert result.exit_code == 0
    assert "1 verbatins afetados" in result.output


def test_retencao_meses_zero_rejeitado(app, client_loyall):
    """--meses 0 é rejeitado (proteção contra remover tudo)."""
    result = _invocar_cli(app, ["--meses", "0"])
    assert result.exit_code == 2
    assert "deve ser >= 1" in result.output


def test_retencao_zero_afetados(app, db_session, client_loyall):
    """Banco sem verbatins antigos: qtd_afetada=0; evento ainda é registrado."""
    emp_id, fonte_id = _setup_fonte(client_loyall)
    _criar_verbatim(db_session, fonte_id, emp_id, dias_atras=10, texto="recente")

    result = _invocar_cli(app, ["--meses", "18"])
    assert result.exit_code == 0
    assert "0 verbatins afetados" in result.output

    eventos = (
        db_session.query(EventoManutencao)
        .filter_by(tipo="retencao_verbatins")
        .order_by(EventoManutencao.id.desc())
        .all()
    )
    assert eventos[0].qtd_afetada == 0


# ── calcular_data_inicio_coleta (CP-backfill-inicial) ───────────────────


def test_calcular_data_inicio_sem_historico_janela_padrao(monkeypatch, db_session, client_loyall):
    """Fonte sem histórico → hoje − 15 meses (janela padrão do sistema)."""
    from datetime import date, timedelta

    from src.coletor.incremental import COLETA_JANELA_MESES, calcular_data_inicio_coleta

    monkeypatch.delenv("PDPA_COLETA_DESDE_OVERRIDE", raising=False)
    _emp_id, fonte_id = _setup_fonte(client_loyall)
    esperado = (date.today() - timedelta(days=COLETA_JANELA_MESES * 30)).isoformat()
    assert calcular_data_inicio_coleta(fonte_id) == esperado


def test_calcular_data_inicio_override_forca_data(monkeypatch, db_session, client_loyall):
    """PDPA_COLETA_DESDE_OVERRIDE força a data mesmo sem histórico (recoleta)."""
    from src.coletor.incremental import calcular_data_inicio_coleta

    monkeypatch.setenv("PDPA_COLETA_DESDE_OVERRIDE", "2015-01-01")
    _emp_id, fonte_id = _setup_fonte(client_loyall)
    assert calcular_data_inicio_coleta(fonte_id) == "2015-01-01"


def test_calcular_data_inicio_incremental_max_menos_buffer(monkeypatch, db_session, client_loyall):
    """Com histórico → MAX(data_criacao_original) − INCREMENTAL_BUFFER_DAYS."""
    from datetime import datetime, timedelta

    from src.coletor.incremental import INCREMENTAL_BUFFER_DAYS, calcular_data_inicio_coleta
    from src.models.verbatim import Verbatim

    monkeypatch.delenv("PDPA_COLETA_DESDE_OVERRIDE", raising=False)
    emp_id, fonte_id = _setup_fonte(client_loyall)
    d = datetime(2026, 5, 1)
    db_session.add(
        Verbatim(
            empresa_id=emp_id,
            fonte_id=fonte_id,
            texto="x",
            tem_texto=True,
            data_criacao_original=d,
            hash_dedup="bk-incr-1",
        )
    )
    db_session.commit()
    esperado = (d.date() - timedelta(days=INCREMENTAL_BUFFER_DAYS)).isoformat()
    assert calcular_data_inicio_coleta(fonte_id) == esperado
