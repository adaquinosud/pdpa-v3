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
from src.api.monitoramento import monitoramento_bp
from src.api.temas import temas_bp
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
    app.register_blueprint(monitoramento_bp)
    app.register_blueprint(temas_bp)
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

    @app.cli.command("retencao-aplicar")
    @click.option(
        "--meses",
        type=int,
        default=None,
        help="Remove verbatins com data_criacao_original anterior a hoje−N "
        "meses. Default: PDPA_RETENCAO_MESES (env, fallback 18).",
    )
    @click.option(
        "--dry-run",
        is_flag=True,
        default=False,
        help="Não apaga nada; só conta e loga o evento como dry_run=True.",
    )
    def retencao_aplicar(meses, dry_run):
        """Aplica retenção em verbatins antigos (Bloco 4 CP-D, MEC 2).

        Política:
        - Default ``--meses`` lê de env ``PDPA_RETENCAO_MESES`` (fallback 18).
        - ``--dry-run`` apenas conta os afetados e registra evento.
        - Sem ``--dry-run`` DELETE acontece dentro de uma transação;
          registro fica em ``eventos_manutencao``.
        - O coletor pode re-coletar verbatins removidos se a janela de
          coleta cobrir as datas relevantes; a retenção não invalida o
          incremental porque usa MAX(data_criacao_original) e os mais
          recentes seguem no banco.
        """
        import os
        from datetime import date, timedelta

        from src.models.evento_manutencao import EventoManutencao
        from src.models.verbatim import Verbatim
        from src.utils.db import db_session as _db_session

        if meses is None:
            try:
                meses = int(os.environ.get("PDPA_RETENCAO_MESES", "18"))
            except (TypeError, ValueError):
                meses = 18
        if meses < 1:
            click.echo(
                "--meses deve ser >= 1 (proteção contra remover tudo).",
                err=True,
            )
            raise SystemExit(2)

        cutoff = date.today() - timedelta(days=meses * 30)
        click.echo(f"Retenção: verbatins com data_criacao_original < {cutoff.isoformat()}")

        with _db_session() as session:
            antigos_q = session.query(Verbatim).filter(Verbatim.data_criacao_original < cutoff)
            qtd = antigos_q.count()
            click.echo(f"  → {qtd} verbatins afetados")

            if dry_run:
                click.echo("  (dry-run: nada apagado)")
            else:
                if qtd > 0:
                    antigos_q.delete(synchronize_session=False)
                    click.echo(f"  → {qtd} removidos.")

            evento = EventoManutencao(
                tipo="retencao_verbatins",
                qtd_afetada=qtd,
                dry_run=dry_run,
                mensagem=(f"meses={meses}; cutoff={cutoff.isoformat()}; " f"dry_run={dry_run}"),
            )
            session.add(evento)
        click.echo("OK")


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5050, debug=True)
