"""CP-5b: coleta on-demand fire-and-forget (fonte/local) + gate do agrupamento.

Os botões da tela (htmx) deixam de ser síncronos: disparam numa daemon-thread e
retornam 202/'coletando…' na hora (não travam na cauda do google). Em TESTING o
dispatch é no-op (SQLite não é thread-safe) — aqui testamos o CAMINHO do handler
(202, guards, gate), não a coleta real. O agrupamento on-demand é bloqueado em
produção (a coleta completa é a noturna).
"""

from __future__ import annotations

from datetime import datetime

from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from src.models.agrupamento import Agrupamento
from src.models.coleta_execucao import ColetaExecucao
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.local import Local


def _empresa(db_session: Session, nome: str) -> int:
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.commit()
    return e.id


def _fonte(db_session: Session, empresa_id: int, conector: str = "google") -> int:
    f = Fonte(
        empresa_id=empresa_id,
        entidade_tipo="empresa",
        entidade_id=empresa_id,
        conector_tipo=conector,
        url="ChIJ-x",
    )
    db_session.add(f)
    db_session.commit()
    return f.id


def test_disparar_fonte_fire_and_forget_retorna_202(client_loyall: FlaskClient, db_session):
    emp = _empresa(db_session, "FAF Fonte")
    fid = _fonte(db_session, emp)

    r = client_loyall.post(f"/ui/fontes/{fid}/disparar")

    assert r.status_code == 202
    assert "Coletando" in r.get_data(as_text=True)


def test_disparar_fonte_duplo_clique_barra(client_loyall: FlaskClient, db_session):
    """Já há uma execução 'rodando' → o guard barra antes de spawnar a 2ª thread."""
    emp = _empresa(db_session, "FAF Dup")
    fid = _fonte(db_session, emp)
    db_session.add(
        ColetaExecucao(
            empresa_id=emp, fonte_id=fid, status="rodando", iniciado_em=datetime.utcnow()
        )
    )
    db_session.commit()

    r = client_loyall.post(f"/ui/fontes/{fid}/disparar")

    assert r.status_code == 200  # não-202: barrado
    assert "andamento" in r.get_data(as_text=True)


def _fonte_ra(db_session: Session, empresa_id: int, *, ra_modo="padrao", ra_max_casos=None) -> int:
    f = Fonte(
        empresa_id=empresa_id,
        entidade_tipo="empresa",
        entidade_id=empresa_id,
        conector_tipo="reclame_aqui",
        url="https://www.reclameaqui.com.br/x/",
        ra_modo=ra_modo,
        ra_max_casos=ra_max_casos,
    )
    db_session.add(f)
    db_session.commit()
    return f.id


def test_aberturas_padrao_retorna_202(client_loyall: FlaskClient, db_session):
    """Fonte RA padrão, cap default → dispara (202) e diz 'aberturas'. Em TESTING o
    dispatch é no-op → NENHUM run Apify; testa-se o caminho do handler."""
    emp = _empresa(db_session, "Ab 202")
    fid = _fonte_ra(db_session, emp)  # cap None → default 250
    r = client_loyall.post(f"/ui/fontes/{fid}/aberturas")
    assert r.status_code == 202
    assert "aberturas" in r.get_data(as_text=True).lower()


def test_aberturas_cap_alto_manda_pro_cron(client_loyall: FlaskClient, db_session):
    """Cap > 2000 → recusa no botão e manda pro cron (worker web arriscaria OOM)."""
    emp = _empresa(db_session, "Ab cron")
    fid = _fonte_ra(db_session, emp, ra_max_casos=5000)
    r = client_loyall.post(f"/ui/fontes/{fid}/aberturas")
    assert r.status_code == 200  # não-202: barrado
    assert "cron" in r.get_data(as_text=True)


def test_aberturas_cap_zero_recusa(client_loyall: FlaskClient, db_session):
    """Cap = 0 (não coletar) → recusa."""
    emp = _empresa(db_session, "Ab zero")
    fid = _fonte_ra(db_session, emp, ra_max_casos=0)
    r = client_loyall.post(f"/ui/fontes/{fid}/aberturas")
    assert r.status_code == 200
    assert "não coletar" in r.get_data(as_text=True)


def test_aberturas_completo_recusa(client_loyall: FlaskClient, db_session):
    """Modo completo não tem coleta de aberturas pelo botão (vai pelo cron de coortes)."""
    emp = _empresa(db_session, "Ab compl")
    fid = _fonte_ra(db_session, emp, ra_modo="completo")
    r = client_loyall.post(f"/ui/fontes/{fid}/aberturas")
    assert r.status_code == 400


def test_aberturas_nao_ra_recusa(client_loyall: FlaskClient, db_session):
    """Fonte não-RA (google) → 400."""
    emp = _empresa(db_session, "Ab google")
    fid = _fonte(db_session, emp)  # google
    r = client_loyall.post(f"/ui/fontes/{fid}/aberturas")
    assert r.status_code == 400


def test_aberturas_duplo_clique_barra(client_loyall: FlaskClient, db_session):
    """Execução 'rodando' → o guard barra antes de spawnar a 2ª thread."""
    emp = _empresa(db_session, "Ab dup")
    fid = _fonte_ra(db_session, emp)
    db_session.add(
        ColetaExecucao(
            empresa_id=emp, fonte_id=fid, status="rodando", iniciado_em=datetime.utcnow()
        )
    )
    db_session.commit()
    r = client_loyall.post(f"/ui/fontes/{fid}/aberturas")
    assert r.status_code == 200
    assert "andamento" in r.get_data(as_text=True)


def test_disparar_local_fire_and_forget_retorna_202(client_loyall: FlaskClient, db_session):
    emp = _empresa(db_session, "FAF Local")
    loc = Local(empresa_id=emp, nome="Loja 1")
    db_session.add(loc)
    db_session.commit()

    r = client_loyall.post(f"/ui/locais/{loc.id}/disparar")

    assert r.status_code == 202
    assert "Coletando" in r.get_data(as_text=True)


def test_agrupamento_on_demand_bloqueado_em_producao(
    client_loyall: FlaskClient, db_session, monkeypatch
):
    emp = _empresa(db_session, "Ag Prod")
    ag = Agrupamento(empresa_id=emp, nome="Ramo X")
    db_session.add(ag)
    db_session.commit()

    monkeypatch.setenv("FLASK_ENV", "production")
    r = client_loyall.post(f"/ui/agrupamentos/{ag.id}/disparar")
    assert r.status_code == 403
    assert "noturna" in r.get_data(as_text=True)


def test_agrupamento_on_demand_funciona_em_dev(client_loyall: FlaskClient, db_session, monkeypatch):
    """Em dev (FLASK_ENV != production) o agrupamento on-demand NÃO é bloqueado."""
    emp = _empresa(db_session, "Ag Dev")
    ag = Agrupamento(empresa_id=emp, nome="Ramo Y")
    db_session.add(ag)
    db_session.commit()

    monkeypatch.delenv("FLASK_ENV", raising=False)
    r = client_loyall.post(f"/ui/agrupamentos/{ag.id}/disparar")
    assert r.status_code != 403  # sem fontes → 200 com aviso, mas NÃO o gate de prod


def test_em_producao_template_global(app):
    """O global `em_producao` reflete FLASK_ENV (usado pra esconder o botão)."""
    em_producao = app.jinja_env.globals["em_producao"]
    import os

    os.environ.pop("FLASK_ENV", None)
    assert em_producao() is False
    os.environ["FLASK_ENV"] = "production"
    try:
        assert em_producao() is True
    finally:
        os.environ.pop("FLASK_ENV", None)
