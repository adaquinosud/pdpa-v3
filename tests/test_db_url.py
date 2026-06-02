"""CP-deploy-1: normalização da DATABASE_URL para o driver psycopg3.

Render/Heroku entregam ``postgresql://``/``postgres://`` — o SQLAlchemy roteia
isso pro psycopg2 (não instalado). O helper força ``postgresql+psycopg://`` sem
duplicar quando já normalizado e sem tocar sqlite/outros.
"""

from __future__ import annotations

import pytest

from src.utils.db_url import normalize_db_url


def test_postgresql_vira_psycopg():
    assert (
        normalize_db_url("postgresql://user:pw@host:5432/db")
        == "postgresql+psycopg://user:pw@host:5432/db"
    )


def test_postgres_legacy_heroku_vira_psycopg():
    assert normalize_db_url("postgres://user:pw@host/db") == "postgresql+psycopg://user:pw@host/db"


def test_ja_normalizada_nao_duplica():
    url = "postgresql+psycopg://user:pw@host/db"
    assert normalize_db_url(url) == url
    # idempotência: aplicar 2x não muda
    assert normalize_db_url(normalize_db_url(url)) == url


def test_sqlite_intacto():
    assert normalize_db_url("sqlite:///pdpa_v3_dev.db") == "sqlite:///pdpa_v3_dev.db"
    assert normalize_db_url("sqlite:///:memory:") == "sqlite:///:memory:"


def test_outro_driver_explicito_intacto():
    # não mexe em quem já escolheu driver (ex. asyncpg)
    assert normalize_db_url("postgresql+asyncpg://h/db") == "postgresql+asyncpg://h/db"


@pytest.mark.parametrize("vazio", ["", None])
def test_vazio_intacto(vazio):
    assert normalize_db_url(vazio) == vazio


def test_config_usa_o_helper(monkeypatch):
    """A Config do app aplica o helper na DATABASE_URL do ambiente."""
    import importlib

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
    import src.config as cfg

    importlib.reload(cfg)
    try:
        assert cfg.Config.SQLALCHEMY_DATABASE_URI == "postgresql+psycopg://u:p@h/d"
    finally:
        # restaura o módulo sem o env de teste pra não vazar pro resto da suíte
        monkeypatch.delenv("DATABASE_URL", raising=False)
        importlib.reload(cfg)
