"""Utilitários de banco — engine, session factory e context manager.

O event listener `_set_sqlite_pragma` é o ponto crítico: SQLite desativa
FK por padrão e o `PRAGMA foreign_keys` é por-conexão, então precisa ser
ligado em todo `connect` (não basta o init_db.py rodar uma vez).
"""

from __future__ import annotations

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
    """Liga PRAGMA foreign_keys=ON em toda nova conexão.

    Args:
        dbapi_connection: Conexão DB-API recém-aberta.
        connection_record: Registro interno do SQLAlchemy para a conexão.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine() -> Engine:
    """Retorna o engine SQLAlchemy do projeto (singleton no módulo)."""
    global _engine
    if _engine is None:
        config = get_config()
        _engine = create_engine(config.SQLALCHEMY_DATABASE_URI)
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
