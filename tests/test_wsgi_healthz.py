"""CP-deploy-2: entrypoint de produção — WSGI callable + /healthz.

Prova que ``gunicorn wsgi:app`` teria um callable válido e que o health check do
Render (``/healthz``) responde 200 sem auth e sem tocar o banco.

O boot em produção (FLASK_ENV=production + SECRET_KEY real) já é coberto por
``test_seguranca_deploy.test_boot_ok_em_producao_com_secret_real`` — não duplico.
"""

from __future__ import annotations

from flask import Flask


def test_wsgi_expoe_callable_app():
    """`import wsgi; wsgi.app` é o callable que o gunicorn serve (wsgi:app)."""
    import wsgi

    assert isinstance(wsgi.app, Flask)


def test_healthz_200_sem_auth(client):
    """/healthz: 200, sem autenticação, payload de status."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_health_alias_mantido(client):
    """/health continua respondendo (compat com briefings/curl de dev)."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_healthz_commit_default_dev(client, monkeypatch):
    """Sem RENDER_GIT_COMMIT (dev/local), o campo commit cai pra 'dev'."""
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    resp = client.get("/healthz")
    assert resp.get_json()["commit"] == "dev"


def test_healthz_commit_expoe_sha_do_render(client, monkeypatch):
    """No Render, /healthz devolve os 7 primeiros do RENDER_GIT_COMMIT — permite
    confirmar QUAL deploy está vivo via `curl /healthz` (sem painel/API)."""
    monkeypatch.setenv("RENDER_GIT_COMMIT", "8bce4cbdeadbeef0123456789abcdef")
    resp = client.get("/healthz")
    assert resp.get_json()["commit"] == "8bce4cb"
