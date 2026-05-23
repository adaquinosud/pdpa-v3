"""Endpoints de autenticação (Bloco 4 — CP4).

- POST /api/auth/login  (email + senha → cookie de sessão)
- POST /api/auth/logout (limpa cookie de sessão)
- GET  /api/auth/me     (info do usuário logado, ou 401)
"""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from src.auth import get_current_user, login_user, logout_user, verificar_senha
from src.models.usuario import Usuario
from src.utils.db import db_session


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _serialize_user(user: Usuario) -> dict:
    """Converte Usuario em dict serializável (NUNCA inclui senha_hash)."""
    return {
        "id": user.id,
        "email": user.email,
        "nome": user.nome,
        "papel": user.papel,
        "empresa_id": user.empresa_id,
        "ultimo_login": user.ultimo_login.isoformat() if user.ultimo_login else None,
    }


@auth_bp.route("/login", methods=["POST"])
def login():
    """Login por email + senha.

    Body JSON: ``{"email": "...", "senha": "..."}``.

    Returns:
        200 com info do user + cookie de sessão set; 400 se faltar campo;
        401 se credenciais inválidas ou usuário desativado.
    """
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    senha = data.get("senha") or ""
    if not email or not senha:
        return jsonify({"erro": "email e senha são obrigatórios"}), 400

    with db_session() as session_db:
        user = session_db.query(Usuario).filter_by(email=email).first()
        if user is None or not user.ativo:
            return jsonify({"erro": "credenciais inválidas"}), 401
        if not verificar_senha(senha, user.senha_hash):
            return jsonify({"erro": "credenciais inválidas"}), 401

        user.ultimo_login = datetime.utcnow()
        session_db.flush()
        login_user(user)
        return jsonify(_serialize_user(user))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Limpa a sessão Flask do usuário atual."""
    logout_user()
    return jsonify({"ok": True})


@auth_bp.route("/me", methods=["GET"])
def me():
    """Devolve info do usuário logado (ou 401 se não há sessão)."""
    user = get_current_user()
    if user is None:
        return jsonify({"erro": "não autenticado"}), 401
    return jsonify(_serialize_user(user))
