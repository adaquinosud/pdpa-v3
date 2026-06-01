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

import os
from typing import Iterator, Optional

import pytest
from flask.testing import FlaskClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import src.models  # noqa: F401  registra Base.metadata
import src.utils.db  # noqa: F401  registra PRAGMA foreign_keys listener
from src.models.base import Base


@pytest.fixture(scope="session")
def _pg_engine() -> Iterator[Optional[Engine]]:
    """Engine Postgres compartilhado da SESSÃO, se ``TEST_DATABASE_URL`` setado
    (ex. via ``scripts/run_tests_postgres.py``). Cria o schema UMA vez; cada
    teste só faz ``TRUNCATE ... RESTART IDENTITY`` (rápido + reseta sequences),
    em vez de drop+create por teste. Sem a env, rende ``None`` (usa SQLite)."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        yield None
        return
    eng = create_engine(url)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def _truncar_tudo(engine: Engine) -> None:
    nomes = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {nomes} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db_session(_pg_engine: Optional[Engine]) -> Iterator[Session]:
    """Sessão por teste + override do singleton em ``src.utils.db``.

    SQLite ``:memory:`` (default): engine novo por teste (StaticPool, conexão
    única). Postgres (``_pg_engine`` setado): engine da sessão + TRUNCATE limpa
    os dados antes do teste — mesma isolação, muito mais rápido."""
    from src.utils import db as db_module

    if _pg_engine is not None:
        _truncar_tudo(_pg_engine)
        test_engine = _pg_engine
        dispose_no_fim = False
    else:
        test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(test_engine)
        dispose_no_fim = True

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
        if dispose_no_fim:
            test_engine.dispose()


@pytest.fixture
def app(db_session: Session):
    """Cria a Flask app de teste (sem sessão pré-logada)."""
    from src.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app) -> Iterator[FlaskClient]:
    """Flask test client SEM autenticação — endpoints protegidos retornam 401."""
    with app.test_client() as test_client:
        yield test_client


def _criar_usuario(db_session, papel: str, empresa_id=None, email_prefix="u"):
    """Cria um Usuario no banco de teste com hash de senha real."""
    from src.auth import hash_senha
    from src.models.usuario import Usuario

    user = Usuario(
        email=f"{email_prefix}_{papel}@example.test",
        nome=f"Test {papel}",
        senha_hash=hash_senha("senha-teste-12345"),
        papel=papel,
        empresa_id=empresa_id,
        ativo=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def usuario_loyall(db_session):
    """Usuario admin_loyall (sem empresa_id)."""
    return _criar_usuario(db_session, papel="admin_loyall")


@pytest.fixture
def usuario_cliente_factory(db_session):
    """Fábrica de usuario cliente_total ligado a uma empresa."""

    def factory(empresa_id: int, email_prefix: str = "cli"):
        return _criar_usuario(
            db_session,
            papel="cliente_total",
            empresa_id=empresa_id,
            email_prefix=email_prefix,
        )

    return factory


def _logar(test_client: FlaskClient, user_id: int) -> None:
    """Marca o ``user_id`` na sessão Flask do test client."""
    with test_client.session_transaction() as sess:
        sess["user_id"] = user_id


@pytest.fixture
def client_loyall(app, usuario_loyall) -> Iterator[FlaskClient]:
    """Test client com sessão de admin_loyall pré-logada.

    Usado nos testes existentes que não tinham auth (Bloco 4 CP4
    adicionou ``@login_required`` em quase tudo).
    """
    with app.test_client() as test_client:
        _logar(test_client, usuario_loyall.id)
        yield test_client


@pytest.fixture
def client_cliente_factory(app, usuario_cliente_factory) -> Iterator:
    """Fábrica que devolve test client logado como cliente_total de uma empresa."""

    def factory(empresa_id: int):
        user = usuario_cliente_factory(empresa_id)
        tc = app.test_client()
        _logar(tc, user.id)
        return tc

    yield factory
