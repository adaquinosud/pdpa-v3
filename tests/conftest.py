"""Fixtures pytest comuns ao pacote de testes.

Importa ``src.utils.db`` por efeito colateral para registrar o event listener
de PRAGMA foreign_keys (class-level no ``Engine``, pega também o ``:memory:``).
Importa ``src.models`` por efeito colateral para registrar as 11 tabelas no
``Base.metadata``.

A fixture ``db_session`` **sobrescreve** o singleton do módulo ``src.utils.db``
para que código sob teste que use ``db_session()`` (blueprints, importador
Excel, etc.) opere contra o mesmo engine ``:memory:`` do teste. ``StaticPool``
mantém uma única connection compartilhada — necessário para que o ``:memory:``
seja visível entre múltiplas sessions no mesmo teste.

A fixture ``client`` depende de ``db_session``: garante que o ``test_client``
do Flask e a verificação direta no banco operem sobre o mesmo engine isolado.
"""

from __future__ import annotations

from typing import Iterator

import pytest
from flask.testing import FlaskClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import src.models  # noqa: F401  registra Base.metadata
import src.utils.db  # noqa: F401  registra PRAGMA foreign_keys listener
from src.models.base import Base


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Sessão SQLite ``:memory:`` por teste + override do singleton em ``src.utils.db``."""
    from src.utils import db as db_module

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    SessionLocal = sessionmaker(bind=test_engine)

    original_engine = db_module._engine
    original_session_local = db_module._SessionLocal
    db_module._engine = test_engine
    db_module._SessionLocal = SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        db_module._engine = original_engine
        db_module._SessionLocal = original_session_local
        test_engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Iterator[FlaskClient]:
    """Flask test client. Depende de ``db_session`` para compartilhar o engine."""
    from src.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client
