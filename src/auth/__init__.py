"""Auth básico (Bloco 4 — CP4): cookies + sessão Flask, 2 papéis.

Papéis (valores do CHECK constraint em ``usuarios.papel`` da migration 002):
    - ``admin_loyall``: edita qualquer empresa, incluindo Agrupamentos
      (item 42 das PENDENCIAS — Agrupamento é só Loyall).
    - ``cliente_total``: lê/edita apenas a empresa em ``usuario.empresa_id``;
      NÃO edita Agrupamento.
    - ``cliente_restrito``: reservado para Visão Salva (item 43); ainda
      não usado no Bloco 4.

Sessão:
    - Cookie HttpOnly assinado pela ``FLASK_SECRET_KEY`` (server-side via
      Flask ``session``).
    - ``session['user_id']`` guarda o id do usuário logado.

Decorators:
    - ``@login_required``: 401 se não há user logado.
    - ``@loyall_required``: 403 se não é ``admin_loyall``.
    - ``@cliente_pode_ver_empresa(param_name='empresa_id')``: 403 se
      é cliente e ``empresa_id`` na URL não bate com ``usuario.empresa_id``;
      ``admin_loyall`` sempre passa.

Hash de senha: ``werkzeug.security`` (pbkdf2:sha256 com salt automático).
"""

from __future__ import annotations

from functools import wraps
from typing import Callable, Optional

from flask import jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from src.models.usuario import Usuario
from src.utils.db import db_session


PAPEL_LOYALL = "admin_loyall"
PAPEL_CLIENTE = "cliente_total"
PAPEIS_CLIENTE = frozenset({"cliente_total", "cliente_restrito"})


# ── Hash de senha ────────────────────────────────────────────────────────


def hash_senha(senha: str) -> str:
    """Gera hash pbkdf2:sha256 da senha."""
    return generate_password_hash(senha)


def verificar_senha(senha: str, senha_hash: str) -> bool:
    """Confere senha em texto plano contra o hash armazenado."""
    return check_password_hash(senha_hash, senha)


# ── Helpers de sessão ────────────────────────────────────────────────────


def get_current_user() -> Optional[Usuario]:
    """Retorna o ``Usuario`` da sessão atual ou ``None``.

    Lê ``session['user_id']``. Se o id da sessão não existe mais no
    banco (usuário deletado), retorna ``None`` e limpa a sessão.
    """
    user_id = session.get("user_id")
    if not user_id:
        return None
    with db_session() as s:
        user = s.get(Usuario, user_id)
        if user is None or not user.ativo:
            session.pop("user_id", None)
            return None
        s.expunge(user)
        return user


def login_user(usuario: Usuario) -> None:
    """Marca o usuário como logado na sessão Flask."""
    session["user_id"] = usuario.id
    session.permanent = True


def logout_user() -> None:
    """Limpa a sessão Flask do usuário atual."""
    session.pop("user_id", None)


# ── Decorators ───────────────────────────────────────────────────────────


def login_required(f: Callable) -> Callable:
    """Decorator: 401 se não há usuário logado."""

    @wraps(f)
    def wrapped(*args, **kwargs):
        if get_current_user() is None:
            return jsonify({"erro": "autenticação requerida"}), 401
        return f(*args, **kwargs)

    return wrapped


def loyall_required(f: Callable) -> Callable:
    """Decorator: 403 se não é ``admin_loyall``."""

    @wraps(f)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify({"erro": "autenticação requerida"}), 401
        if user.papel != PAPEL_LOYALL:
            return (
                jsonify({"erro": "operação restrita a admin_loyall"}),
                403,
            )
        return f(*args, **kwargs)

    return wrapped


def verificar_acesso_empresa(empresa_id: int):
    """Helper inline para handlers que descobrem empresa_id via lookup.

    Retorna ``None`` se o usuário pode acessar, ou ``(response, status)``
    tupla para ser devolvida pelo handler.

    Uso típico::

        local = session.get(Local, local_id)
        if local is None:
            return jsonify({"erro": "Local não encontrado"}), 404
        erro = verificar_acesso_empresa(local.empresa_id)
        if erro:
            return erro
        # ... segue normalmente
    """
    user = get_current_user()
    if user is None:
        return jsonify({"erro": "autenticação requerida"}), 401
    if user.papel == PAPEL_LOYALL:
        return None
    if user.empresa_id != empresa_id:
        return (
            jsonify({"erro": "cliente só pode acessar a própria empresa"}),
            403,
        )
    return None


def cliente_pode_ver_empresa(param_name: str = "empresa_id") -> Callable:
    """Decorator factory: cliente só passa se ``url[param_name] == user.empresa_id``.

    ``admin_loyall`` sempre passa. Use em rotas como
    ``/api/empresas/<empresa_id>/...`` para isolar dados por cliente.
    """

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapped(*args, **kwargs):
            user = get_current_user()
            if user is None:
                return jsonify({"erro": "autenticação requerida"}), 401
            if user.papel == PAPEL_LOYALL:
                return f(*args, **kwargs)
            empresa_id = kwargs.get(param_name) or request.view_args.get(param_name)
            if empresa_id is None or int(empresa_id) != user.empresa_id:
                return (
                    jsonify({"erro": "cliente só pode acessar a própria empresa"}),
                    403,
                )
            return f(*args, **kwargs)

        return wrapped

    return decorator
