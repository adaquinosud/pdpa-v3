"""CP-noturna-toggle: campo empresas.coleta_noturna_ativa + toggle UI (loyall-only).
O cron varre só as empresas ligadas — testado em test_coleta_noturna_todas.py."""

from __future__ import annotations


def _empresa(client_loyall, nome):
    return client_loyall.post("/api/empresas/", json={"nome": nome}).get_json()


def test_default_desligada(client_loyall, db_session):
    """Empresa nova nasce com coleta_noturna_ativa=FALSE (não coleta até ligar)."""
    from src.models.empresa import Empresa

    e = _empresa(client_loyall, "TogDefault")
    assert db_session.get(Empresa, e["id"]).coleta_noturna_ativa is False


def test_toggle_liga_e_desliga_loyall(client_loyall, db_session):
    from src.models.empresa import Empresa

    e = _empresa(client_loyall, "TogLoyall")
    # liga
    r = client_loyall.post(f"/ui/empresas/{e['id']}/toggle-coleta-noturna")
    assert r.status_code == 200
    assert "<b>ligada</b>" in r.get_data(as_text=True)
    db_session.expire_all()
    assert db_session.get(Empresa, e["id"]).coleta_noturna_ativa is True
    # desliga
    r2 = client_loyall.post(f"/ui/empresas/{e['id']}/toggle-coleta-noturna")
    assert "<b>desligada</b>" in r2.get_data(as_text=True)
    db_session.expire_all()
    assert db_session.get(Empresa, e["id"]).coleta_noturna_ativa is False


def test_toggle_cliente_bloqueado(client_loyall, client_cliente_factory):
    """CP-O2: só admin_loyall mexe no toggle (cadastro é interno)."""
    e = _empresa(client_loyall, "TogCli")
    cli = client_cliente_factory(e["id"])
    r = cli.post(f"/ui/empresas/{e['id']}/toggle-coleta-noturna")
    assert r.status_code == 403
