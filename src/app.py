"""Flask app principal — PDPA v3."""

import click
from flask import Flask
from flask_cors import CORS

from src.api.agrupamentos import agrupamentos_bp
from src.api.auth import auth_bp
from src.api.coleta import coleta_bp
from src.api.empresas import empresas_bp
from src.api.fontes import fontes_bp
from src.api.locais import locais_bp
from src.api.verbatins import verbatins_bp
from src.config import get_config
from src.ui import ui_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config())
    # Garante SECRET_KEY para assinar a sessão (cookie HttpOnly).
    if not app.secret_key:
        app.secret_key = app.config.get("SECRET_KEY") or "dev-key"
    CORS(app, supports_credentials=True)

    app.register_blueprint(auth_bp)
    app.register_blueprint(empresas_bp)
    app.register_blueprint(agrupamentos_bp)
    app.register_blueprint(locais_bp)
    app.register_blueprint(fontes_bp)
    app.register_blueprint(verbatins_bp)
    app.register_blueprint(coleta_bp)
    app.register_blueprint(ui_bp)

    _register_cli_commands(app)

    @app.route("/health")
    def health():
        return {"status": "ok", "version": "3.0.0-dev"}

    return app


def _register_cli_commands(app: Flask) -> None:
    """Comandos CLI ``flask <cmd>`` (bootstrap admin do Bloco 4 — CP4)."""

    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.option("--nome", prompt=True)
    @click.option(
        "--senha",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
    )
    def create_admin(email: str, nome: str, senha: str) -> None:
        """Cria um usuário admin_loyall (bootstrap do auth)."""
        from src.auth import PAPEL_LOYALL, hash_senha
        from src.models.usuario import Usuario
        from src.utils.db import db_session as _db_session

        email = email.strip().lower()
        if len(senha) < 8:
            click.echo("Senha deve ter pelo menos 8 caracteres.", err=True)
            raise SystemExit(1)
        with _db_session() as session:
            ja = session.query(Usuario).filter_by(email=email).first()
            if ja is not None:
                click.echo(f"Usuário '{email}' já existe.", err=True)
                raise SystemExit(1)
            user = Usuario(
                email=email,
                nome=nome,
                senha_hash=hash_senha(senha),
                papel=PAPEL_LOYALL,
                empresa_id=None,
                ativo=True,
            )
            session.add(user)
        click.echo(f"OK — admin '{email}' criado.")


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5050, debug=True)
