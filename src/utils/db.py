"""Utilitários de banco — engine, session factory e context manager.

O event listener `_set_sqlite_pragma` liga FK no SQLite (desativado por padrão,
por-conexão). **É SQLite-only**: `PRAGMA foreign_keys` é SQL inválido no Postgres
(erro em todo connect), então o listener só roda quando a conexão é de fato
SQLite (no Postgres a FK já vem ligada). O engine usa `pool_pre_ping` (Postgres/
Render derruba conexão ociosa) e dimensiona o pool fora do SQLite (as daemon
threads de coleta pegam conexão do pool).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_config


_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker[Session]] = None


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    """Liga `PRAGMA foreign_keys=ON` — SOMENTE em conexões SQLite.

    No Postgres a FK já vem ligada e o PRAGMA é inválido; o guard por tipo de
    conexão (`sqlite3.Connection`) torna isto no-op fora do SQLite.
    """
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine() -> Engine:
    """Retorna o engine SQLAlchemy do projeto (singleton no módulo).

    `pool_pre_ping=True` em qualquer dialeto (inócuo no SQLite; evita conexão
    morta no Postgres). `pool_size`/`max_overflow` só fora do SQLite."""
    global _engine
    if _engine is None:
        config = get_config()
        url = config.SQLALCHEMY_DATABASE_URI
        kwargs: dict = {"pool_pre_ping": True}
        if not url.startswith("sqlite"):
            kwargs["pool_size"] = 5
            kwargs["max_overflow"] = 10
        _engine = create_engine(url, **kwargs)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Retorna o sessionmaker do projeto (singleton no módulo)."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal


@contextmanager
def db_session() -> Iterator[Session]:
    """Context manager de sessão SQLAlchemy.

    Faz commit ao sair normalmente do bloco, rollback se houver exceção,
    e sempre fecha a sessão.

    Yields:
        Sessão SQLAlchemy ligada ao engine do projeto.
    """
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
