"""Segurança de deploy (chore/seguranca-deploy): boot-check do SECRET_KEY +
config do cookie de sessão por ambiente.

O login usa Flask session assinada com SECRET_KEY → em produção o default
'dev-key' permitiria forjar sessão. O app deve FALHAR no boot nesse caso. Dev
(default) mantém o comportamento permissivo. Os 734 rodam como dev → não disparam.
"""

from __future__ import annotations

import pytest

from src import config as cfg
from src.app import create_app


def test_boot_falha_em_producao_com_secret_default(monkeypatch):
    """FLASK_ENV=production + SECRET_KEY default → RuntimeError no create_app."""
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setattr(cfg.Config, "SECRET_KEY", "dev-key")
    with pytest.raises(RuntimeError, match="FLASK_SECRET_KEY"):
        create_app()


def test_boot_ok_em_producao_com_secret_real(monkeypatch):
    """FLASK_ENV=production + SECRET_KEY real → sobe; cookie Secure=True."""
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setattr(cfg.Config, "SECRET_KEY", "uma-chave-forte-de-verdade-xyz")
    app = create_app()
    assert app.config["SECRET_KEY"] == "uma-chave-forte-de-verdade-xyz"
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True


def test_boot_ok_em_dev_com_secret_default(monkeypatch):
    """Dev (FLASK_ENV não-production) NÃO exige secret; cookie não-Secure."""
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setattr(cfg.Config, "SECRET_KEY", "dev-key")
    app = create_app()  # não levanta
    assert app.config["SESSION_COOKIE_SECURE"] is False
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
