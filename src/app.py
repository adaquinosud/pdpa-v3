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

    @app.cli.command("temas-extrair")
    @click.option("--empresa", "empresa_arg", required=True, help="ID ou nome da empresa.")
    @click.option(
        "--apenas-novos",
        is_flag=True,
        default=False,
        help="Pula verbatins que já têm temas vinculados (idempotência segura).",
    )
    @click.option(
        "--subpilar",
        default=None,
        help="Restringe a um subpilar (P1..A3 ou sem_lastro).",
    )
    @click.option("--tipo", "tipo_arg", default=None, help="Restringe a um tipo.")
    @click.option(
        "--limite",
        type=int,
        default=None,
        help="Cap explícito de verbatins (default: sem cap, processa tudo).",
    )
    @click.option(
        "--max-usd",
        type=float,
        default=None,
        help="Kill switch: aborta quando custo estimado acumulado excede USD.",
    )
    @click.option(
        "--dry-run",
        is_flag=True,
        default=False,
        help="Conta verbatins elegíveis e estima custo, sem chamar LLM.",
    )
    def temas_extrair(empresa_arg, apenas_novos, subpilar, tipo_arg, limite, max_usd, dry_run):
        """Extrai temas de verbatins (Bloco 6 CP-4).

        Reusa o pipeline do endpoint /reprocessar (CP-3) mas sem cap inline.
        Log estruturado JSONL em data/temas_extracao_<ts>.jsonl, resumo
        em .resumo.json. Idempotente — pode rerun.
        """
        import json as _json
        import time
        from datetime import datetime
        from pathlib import Path

        from src.api.temas import CUSTO_USD_POR_VERBATIM
        from src.models.empresa import Empresa
        from src.models.temas import Tema, VerbatimTema
        from src.models.verbatim import Verbatim
        from src.temas.extrator import extrair_temas
        from src.temas.persistencia import persistir_temas_de_verbatim
        from src.utils.db import db_session as _db_session

        # Resolve empresa por ID ou nome
        with _db_session() as session:
            try:
                emp_id = int(empresa_arg)
                emp = session.get(Empresa, emp_id)
            except ValueError:
                emp = session.query(Empresa).filter_by(nome=empresa_arg).first()
            if emp is None:
                click.echo(f"empresa {empresa_arg!r} não encontrada", err=True)
                raise SystemExit(1)
            empresa_id = emp.id
            empresa_nome = emp.nome
            empresa_setor = emp.setor

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = Path(__file__).parent.parent / "data" / f"temas_extracao_{ts}.jsonl"
        click.echo(f"[temas-extrair] empresa={empresa_nome!r} (id={empresa_id})")
        click.echo(f"[temas-extrair] log: {log_path}")

        # Lista verbatins elegíveis
        with _db_session() as session:
            q = session.query(Verbatim).filter(
                Verbatim.empresa_id == empresa_id, Verbatim.tem_texto.is_(True)
            )
            if subpilar:
                q = q.filter(Verbatim.subpilar == subpilar)
            if tipo_arg:
                q = q.filter(Verbatim.tipo == tipo_arg)
            if apenas_novos:
                sub_ids = session.query(VerbatimTema.verbatim_id).distinct()
                q = q.filter(~Verbatim.id.in_(sub_ids))
            total = q.count()
            click.echo(f"[temas-extrair] {total} verbatins elegíveis")
            if limite and limite < total:
                click.echo(f"[temas-extrair] limite={limite} aplicado")
                total = limite

            custo_estimado = round(total * CUSTO_USD_POR_VERBATIM, 4)
            click.echo(f"[temas-extrair] custo estimado: USD {custo_estimado}")
            if max_usd is not None:
                click.echo(f"[temas-extrair] kill switch: max_usd={max_usd}")

            if dry_run:
                click.echo("[temas-extrair] dry-run: nada será chamado.")
                return

            ids_iter = q.order_by(Verbatim.id.asc())
            if limite:
                ids_iter = ids_iter.limit(limite)

            verbatins_dados = [
                {
                    "id": v.id,
                    "texto": v.texto,
                    "subpilar": v.subpilar,
                    "tipo": v.tipo,
                }
                for v in ids_iter.all()
            ]
            catalogo = (
                session.query(Tema.nome, Tema.slug)
                .filter(Tema.empresa_id == empresa_id, Tema.ativo.is_(True))
                .order_by(Tema.criado_em.desc())
                .limit(80)
                .all()
            )
            catalogo_lista = [{"nome": n, "slug": sl} for (n, sl) in catalogo]

        # Loop principal — chamadas LLM fora de qualquer sessão DB aberta
        novos_vinculos = 0
        erros = 0
        usd_acumulado = 0.0
        t0 = time.monotonic()
        with log_path.open("w") as logf:
            for i, vdata in enumerate(verbatins_dados, start=1):
                if max_usd is not None and usd_acumulado >= max_usd:
                    click.echo(
                        f"[temas-extrair] kill switch: USD acumulado "
                        f"{usd_acumulado:.4f} >= {max_usd} — abortando."
                    )
                    break
                try:
                    temas_ext = extrair_temas(
                        vdata["texto"],
                        {
                            "subpilar": vdata.get("subpilar"),
                            "tipo": vdata.get("tipo"),
                            "setor": empresa_setor,
                        },
                        catalogo_recente=catalogo_lista,
                    )
                    if temas_ext:
                        with _db_session() as s2:
                            ids = persistir_temas_de_verbatim(
                                s2, vdata["id"], empresa_id, temas_ext, origem="llm"
                            )
                        novos_vinculos += len(ids)
                    log_line = {
                        "verbatim_id": vdata["id"],
                        "subpilar": vdata.get("subpilar"),
                        "tipo": vdata.get("tipo"),
                        "qtd_temas": len(temas_ext),
                        "nomes": [t["nome"] for t in temas_ext],
                    }
                except Exception as exc:  # noqa: BLE001
                    erros += 1
                    log_line = {
                        "verbatim_id": vdata["id"],
                        "erro": f"{type(exc).__name__}: {exc}",
                    }
                usd_acumulado += CUSTO_USD_POR_VERBATIM
                logf.write(_json.dumps(log_line, ensure_ascii=False) + "\n")
                logf.flush()
                if i % 50 == 0:
                    click.echo(
                        f"[temas-extrair] [{i}/{len(verbatins_dados)}] "
                        f"vinculos={novos_vinculos} erros={erros} "
                        f"usd_acum={usd_acumulado:.4f}"
                    )

        runtime_s = time.monotonic() - t0
        resumo = {
            "empresa_id": empresa_id,
            "empresa_nome": empresa_nome,
            "verbatins_processados": len(verbatins_dados),
            "novos_vinculos": novos_vinculos,
            "erros": erros,
            "custo_estimado_usd": round(usd_acumulado, 4),
            "runtime_segundos": round(runtime_s, 1),
        }
        resumo_path = log_path.with_suffix(".resumo.json")
        resumo_path.write_text(_json.dumps(resumo, indent=2, ensure_ascii=False))
        click.echo("\n[temas-extrair] ============== RESUMO ==============")
        click.echo(_json.dumps(resumo, indent=2, ensure_ascii=False))
        click.echo(f"[temas-extrair] resumo: {resumo_path}")


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5050, debug=True)
