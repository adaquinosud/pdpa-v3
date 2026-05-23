"""Fixtures pytest comuns ao pacote de testes.

Importa `src.utils.db` por efeito colateral para registrar o event listener
de PRAGMA foreign_keys (class-level no `Engine`, pega também o `:memory:`).
Importa `src.models` por efeito colateral para registrar as 11 tabelas no
`Base.metadata`.
"""

from __future__ import annotations

from typing import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import src.models  # noqa: F401  registra Base.metadata
import src.utils.db  # noqa: F401  registra PRAGMA foreign_keys listener
from src.models.base import Base


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Sessão em SQLite :memory: para cada teste, com FK enforcement ativo."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
