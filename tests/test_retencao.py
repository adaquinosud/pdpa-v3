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


# ── MEC 1: janela de coleta via env ─────────────────────────────────────


def test_janela_meses_default_15(monkeypatch):
    """Sem env, fallback é 15 meses."""
    from src.coletor.incremental import _janela_meses

    monkeypatch.delenv("PDPA_COLETA_JANELA_MESES", raising=False)
    assert _janela_meses() == 15


def test_janela_meses_via_env(monkeypatch):
    """Env PDPA_COLETA_JANELA_MESES é respeitada."""
    from src.coletor.incremental import _janela_meses

    monkeypatch.setenv("PDPA_COLETA_JANELA_MESES", "24")
    assert _janela_meses() == 24


def test_janela_meses_env_invalida_fallback(monkeypatch):
    """Env não-numérica cai no fallback 15."""
    from src.coletor.incremental import _janela_meses

    monkeypatch.setenv("PDPA_COLETA_JANELA_MESES", "abc")
    assert _janela_meses() == 15


def test_calcular_data_inicio_usa_janela_env(monkeypatch, db_session, client_loyall):
    """``calcular_data_inicio_coleta`` usa a janela do env quando não há
    verbatim anterior nem PDPA_COLETA_DESDE."""
    from datetime import date, timedelta

    from src.coletor.incremental import calcular_data_inicio_coleta

    monkeypatch.delenv("PDPA_COLETA_DESDE_OVERRIDE", raising=False)
    monkeypatch.delenv("PDPA_COLETA_DESDE", raising=False)
    monkeypatch.setenv("PDPA_COLETA_JANELA_MESES", "6")

    _emp_id, fonte_id = _setup_fonte(client_loyall)
    # Fonte sem verbatins ainda → cai no fallback
    resultado = calcular_data_inicio_coleta(fonte_id)
    esperado = (date.today() - timedelta(days=6 * 30)).isoformat()
    assert resultado == esperado
