"""Testes de monitoramento de coletas (Bloco 4 CP-E)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

from src.models.coleta_execucao import ColetaExecucao
from src.models.fonte import Fonte


# ── Fixtures helper ─────────────────────────────────────────────────────


def _stats_sucesso() -> Dict[str, Any]:
    return {
        "coletados": 10,
        "novos": 8,
        "duplicados": 2,
        "erros": 0,
        "falhou_apify": False,
    }


def _stats_falha() -> Dict[str, Any]:
    return {
        "coletados": 0,
        "novos": 0,
        "duplicados": 0,
        "erros": 0,
        "falhou_apify": True,
    }


def _setup_empresa_fonte(client_loyall, db_session):
    """Cria empresa + fonte google direto via DB; devolve (empresa_id, fonte_id)."""
    import uuid

    sfx = uuid.uuid4().hex[:6]
    e = client_loyall.post("/api/empresas/", json={"nome": f"Emon-{sfx}"}).get_json()
    fonte = Fonte(
        empresa_id=e["id"],
        entidade_tipo="empresa",
        entidade_id=e["id"],
        conector_tipo="google",
        url=f"ChIJ_mon_{sfx}",
        ativo=True,
    )
    db_session.add(fonte)
    db_session.commit()
    return e["id"], fonte.id


# ── Instrumentação do disparar ──────────────────────────────────────────


def test_disparar_cria_coleta_execucao_em_concluido(client_loyall, db_session, monkeypatch):
    e_id, f_id = _setup_empresa_fonte(client_loyall, db_session)
    monkeypatch.setattr("src.coletor.google.coletar", lambda f: _stats_sucesso())

    r = client_loyall.post(f"/api/coleta/disparar/{f_id}")
    assert r.status_code == 200

    db_session.expire_all()
    execs = db_session.query(ColetaExecucao).filter_by(fonte_id=f_id).all()
    assert len(execs) == 1
    ex = execs[0]
    assert ex.status == "concluido"
    assert ex.coletados == 10
    assert ex.novos == 8
    assert ex.duplicados == 2
    assert ex.concluido_em is not None
    assert ex.iniciado_em < ex.concluido_em or ex.iniciado_em == ex.concluido_em


def test_disparar_falha_apify_grava_status_erro(client_loyall, db_session, monkeypatch):
    e_id, f_id = _setup_empresa_fonte(client_loyall, db_session)
    monkeypatch.setattr("src.coletor.google.coletar", lambda f: _stats_falha())

    r = client_loyall.post(f"/api/coleta/disparar/{f_id}")
    assert r.status_code == 200

    db_session.expire_all()
    ex = db_session.query(ColetaExecucao).filter_by(fonte_id=f_id).first()
    assert ex.status == "erro"
    assert "falhou_apify" in (ex.mensagem_erro or "").lower()


def test_disparar_exception_grava_status_erro(client_loyall, db_session, monkeypatch):
    e_id, f_id = _setup_empresa_fonte(client_loyall, db_session)

    def boom(fonte):
        raise RuntimeError("boom no coletor")

    monkeypatch.setattr("src.coletor.google.coletar", boom)

    try:
        client_loyall.post(f"/api/coleta/disparar/{f_id}")
    except Exception:
        pass

    db_session.expire_all()
    ex = db_session.query(ColetaExecucao).filter_by(fonte_id=f_id).first()
    assert ex is not None
    assert ex.status == "erro"
    assert "boom" in (ex.mensagem_erro or "")


# ── API /api/monitoramento/coletas ──────────────────────────────────────


def _criar_execucao_db(db_session, empresa_id, fonte_id, **kw):
    defaults = dict(
        empresa_id=empresa_id,
        fonte_id=fonte_id,
        status="concluido",
        iniciado_em=datetime.utcnow() - timedelta(minutes=10),
        concluido_em=datetime.utcnow(),
        coletados=5,
        novos=4,
        duplicados=1,
        erros=0,
    )
    defaults.update(kw)
    ex = ColetaExecucao(**defaults)
    db_session.add(ex)
    db_session.commit()
    return ex


def test_api_listar_coletas_loyall_ve_tudo(client_loyall, db_session):
    e1, f1 = _setup_empresa_fonte(client_loyall, db_session)
    e2, f2 = _setup_empresa_fonte(client_loyall, db_session)
    _criar_execucao_db(db_session, e1, f1)
    _criar_execucao_db(db_session, e2, f2)
    r = client_loyall.get("/api/monitoramento/coletas")
    assert r.status_code == 200
    body = r.get_json()
    assert body["total"] == 2


def test_api_listar_filtro_status(client_loyall, db_session):
    e_id, f_id = _setup_empresa_fonte(client_loyall, db_session)
    _criar_execucao_db(db_session, e_id, f_id, status="rodando", concluido_em=None)
    _criar_execucao_db(db_session, e_id, f_id, status="concluido")
    _criar_execucao_db(db_session, e_id, f_id, status="erro", mensagem_erro="x")
    rodando = client_loyall.get("/api/monitoramento/coletas?status=rodando").get_json()
    assert rodando["total"] == 1
    assert rodando["execucoes"][0]["status"] == "rodando"


def test_api_listar_cliente_so_da_propria_empresa(
    client_loyall, client_cliente_factory, db_session
):
    e_a, f_a = _setup_empresa_fonte(client_loyall, db_session)
    e_b, f_b = _setup_empresa_fonte(client_loyall, db_session)
    _criar_execucao_db(db_session, e_a, f_a)
    _criar_execucao_db(db_session, e_b, f_b)
    cli = client_cliente_factory(e_a)
    body = cli.get("/api/monitoramento/coletas").get_json()
    assert body["total"] == 1
    assert body["execucoes"][0]["empresa_id"] == e_a


def test_api_obter_coleta_detalhe(client_loyall, db_session):
    e_id, f_id = _setup_empresa_fonte(client_loyall, db_session)
    ex = _criar_execucao_db(db_session, e_id, f_id, novos=99)
    r = client_loyall.get(f"/api/monitoramento/coletas/{ex.id}")
    assert r.status_code == 200
    assert r.get_json()["novos"] == 99


def test_api_obter_coleta_404(client_loyall):
    r = client_loyall.get("/api/monitoramento/coletas/99999")
    assert r.status_code == 404


def test_api_coletas_em_andamento_da_empresa(client_loyall, db_session):
    e_id, f_id = _setup_empresa_fonte(client_loyall, db_session)
    _criar_execucao_db(db_session, e_id, f_id, status="rodando", concluido_em=None)
    _criar_execucao_db(db_session, e_id, f_id, status="concluido")
    r = client_loyall.get(f"/api/empresas/{e_id}/coletas-em-andamento")
    body = r.get_json()
    assert body["total"] == 1


# ── UI ──────────────────────────────────────────────────────────────────


def test_ui_monitoramento_renderiza(client_loyall, db_session):
    e_id, f_id = _setup_empresa_fonte(client_loyall, db_session)
    _criar_execucao_db(db_session, e_id, f_id, novos=42)
    r = client_loyall.get("/monitoramento")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Monitoramento de coletas" in html
    # Pelo menos um marcador de execução presente (badge ou contador)
    assert "concluido" in html.lower() or "42" in html


def test_ui_monitoramento_polling_quando_rodando(client_loyall, db_session):
    e_id, f_id = _setup_empresa_fonte(client_loyall, db_session)
    _criar_execucao_db(db_session, e_id, f_id, status="rodando", concluido_em=None)
    r = client_loyall.get("/monitoramento")
    html = r.get_data(as_text=True)
    # Polling ligado: hx-trigger="every 5s"
    assert "hx-trigger" in html and "every 5s" in html


def test_ui_monitoramento_sem_polling_sem_rodando(client_loyall, db_session):
    e_id, f_id = _setup_empresa_fonte(client_loyall, db_session)
    _criar_execucao_db(db_session, e_id, f_id, status="concluido")
    r = client_loyall.get("/monitoramento")
    html = r.get_data(as_text=True)
    # Sem coletas rodando, lista existe mas polling não é ativado
    assert "every 5s" not in html


def test_ui_htmx_lista_partial(client_loyall, db_session):
    e_id, f_id = _setup_empresa_fonte(client_loyall, db_session)
    _criar_execucao_db(db_session, e_id, f_id, novos=7)
    r = client_loyall.get("/ui/monitoramento/lista")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "<table" in html or "Nenhuma execução" in html


def test_ui_monitoramento_sem_login_redireciona(client):
    r = client.get("/monitoramento")
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]
