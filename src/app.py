"""Flask app principal — PDPA v3."""

import os

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

    # Em produção, NÃO subir com o SECRET_KEY default (assina a sessão de login —
    # default = forja trivial). Falha no boot em vez de rodar inseguro silencioso.
    # Dev mantém o default (FLASK_ENV != production).
    if os.getenv("FLASK_ENV") == "production" and app.config.get("SECRET_KEY") in (
        None,
        "",
        "dev-key",
    ):
        raise RuntimeError(
            "FLASK_SECRET_KEY obrigatório em produção (não usar o default 'dev-key')."
        )

    # CORS: a UI é HTMX server-rendered (same-origin, não passa por CORS). Só
    # habilita CORS se houver origens cross-origin explícitas em CORS_ORIGINS
    # (CSV); default vazio = sem CORS (seguro). supports_credentials só com origens.
    cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
    if cors_origins:
        CORS(app, origins=cors_origins, supports_credentials=True)

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

    # Selo de confiança por volume (CP-E2): fonte única dos limiares 30/10.
    from src.api.engajamento import selo_confianca

    @app.template_global("selo_emoji")
    def _selo_emoji(volume) -> str:
        return selo_confianca(int(volume or 0))[1]

    # Tradução do ratio P/D em linguagem simples (CP-ratio-palavras): texto
    # discreto sob o número do ratio nos cards de pilar do Painel.
    from src.api.painel import ratio_em_palavras as _ratio_em_palavras

    @app.template_global("ratio_em_palavras")
    def ratio_em_palavras(ratio) -> str:  # noqa: ANN001
        return _ratio_em_palavras(float(ratio or 0))

    # Markdown leve nas respostas do IA Chat (CP-B4): bold + listas + quebras.
    from src.utils.markdown_leve import render_md_leve

    app.add_template_filter(render_md_leve, "md_leve")

    # ⓘ do glossário (CP-glossario-plugar-ui): {{ glossario_i('ratio') }} nas telas.
    # Lê do cadastro (glossario_termo) por slug; 1 query/request via flask.g.
    from src.ui import glossario_i as _glossario_i

    @app.template_global("glossario_i")
    def glossario_i(slug):  # noqa: ANN001, ANN201
        return _glossario_i(slug, debug=app.debug)

    # CP-5b: gate de produção pra esconder o botão de coleta de AGRUPAMENTO
    # on-demand (estoura o timeout HTTP — dezenas de fontes em série; a coleta
    # completa é a noturna). Fonte/local seguem visíveis (fire-and-forget).
    @app.template_global("em_producao")
    def em_producao() -> bool:
        return os.getenv("FLASK_ENV") == "production"

    _register_cli_commands(app)

    # Health check (liveness) — 200 trivial, SEM auth e SEM tocar o banco. O Render
    # reinicia o serviço quando a probe falha; acoplar ao DB faria um soluço de
    # banco virar restart do app. Conectividade de DB é readiness/monitoramento,
    # não esta probe. /healthz é o path canônico do Render; /health é mantido
    # (compat com briefings/curl de dev).
    @app.route("/health")
    @app.route("/healthz")
    def health():
        # ``commit`` = SHA do build vivo. O Render injeta RENDER_GIT_COMMIT (SHA
        # completo) no serviço; expor os 7 primeiros aqui permite confirmar QUAL
        # deploy está no ar via ``curl /healthz`` (sem painel/API do Render). Fora
        # do Render (dev/local), cai pra "dev".
        commit = os.environ.get("RENDER_GIT_COMMIT") or "dev"
        return {"status": "ok", "version": "3.0.0-dev", "commit": commit[:7]}

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
        "--prompt-version",
        type=click.Choice(["v1", "v2"]),
        default="v2",
        help="Versão do prompt do extrator (v1=descritivo legado, v2=acionabilidade).",
    )
    @click.option(
        "--refresh-catalogo",
        type=int,
        default=50,
        help="Refresca o catálogo recente do DB a cada N verbatins (fix B6: anti-fragmentação).",
    )
    @click.option(
        "--dry-run",
        is_flag=True,
        default=False,
        help="Conta verbatins elegíveis e estima custo, sem chamar LLM.",
    )
    def temas_extrair(
        empresa_arg,
        apenas_novos,
        subpilar,
        tipo_arg,
        limite,
        max_usd,
        prompt_version,
        refresh_catalogo,
        dry_run,
    ):
        """Extrai temas de verbatins (Bloco 6 CP-4).

        Reusa o pipeline do endpoint /reprocessar (CP-3) mas sem cap inline.
        Log estruturado JSONL em data/temas_extracao_<ts>.jsonl, resumo
        em .resumo.json. Idempotente — pode rerun.
        """
        import json as _json
        import time
        from datetime import datetime
        from pathlib import Path

        from sqlalchemy import func as _func

        from src.api.temas import CUSTO_USD_POR_VERBATIM
        from src.models.agrupamento import Agrupamento
        from src.models.empresa import Empresa
        from src.models.local import Local
        from src.models.temas import Tema, VerbatimTema
        from src.models.verbatim import Verbatim
        from src.temas.extrator import MAX_CATALOGO_NO_PROMPT, extrair_temas
        from src.temas.persistencia import persistir_temas_de_verbatim
        from src.utils.db import db_session as _db_session

        # Fix A: agrupamento. Fix B: refresh. Fix C: cap 150. Fix D: ordem por volume desc.
        PROMPTS_DIR = Path(__file__).parent / "temas" / "prompts"
        prompt_path = PROMPTS_DIR / f"extracao_temas_{prompt_version}.md"

        def _carregar_catalogo(session) -> list[dict]:
            """Catálogo ordenado por VOLUME desc (fix D), até MAX_CATALOGO_NO_PROMPT (fix C)."""
            rows = (
                session.query(Tema.nome, Tema.slug, _func.count(VerbatimTema.id).label("vol"))
                .outerjoin(VerbatimTema, VerbatimTema.tema_id == Tema.id)
                .filter(Tema.empresa_id == empresa_id, Tema.ativo.is_(True))
                .group_by(Tema.id)
                .order_by(_func.count(VerbatimTema.id).desc(), Tema.criado_em.asc())
                .limit(MAX_CATALOGO_NO_PROMPT)
                .all()
            )
            return [{"nome": n, "slug": sl} for (n, sl, _v) in rows]

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

            # Fix A: lookup agrupamento de cada verbatim via local.
            ag_map = dict(
                session.query(Local.id, Agrupamento.nome)
                .outerjoin(Agrupamento, Agrupamento.id == Local.agrupamento_id)
                .filter(Local.empresa_id == empresa_id)
                .all()
            )

            verbatins_dados = [
                {
                    "id": v.id,
                    "texto": v.texto,
                    "subpilar": v.subpilar,
                    "tipo": v.tipo,
                    "agrupamento": ag_map.get(v.local_id) if v.local_id else None,
                }
                for v in ids_iter.all()
            ]
            catalogo_lista = _carregar_catalogo(session)

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
                # Fix B: refresca catálogo a cada N verbatins (anti-fragmentação).
                if i > 1 and refresh_catalogo > 0 and (i - 1) % refresh_catalogo == 0:
                    with _db_session() as s_ref:
                        catalogo_lista = _carregar_catalogo(s_ref)
                try:
                    temas_ext = extrair_temas(
                        vdata["texto"],
                        {
                            "subpilar": vdata.get("subpilar"),
                            "tipo": vdata.get("tipo"),
                            "setor": empresa_setor,
                            "agrupamento": vdata.get("agrupamento"),
                        },
                        catalogo_recente=catalogo_lista,
                        prompt_path=prompt_path,
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

    # ── B6 Caminho A CP-7: flask temas-embed ──────────────────────────
    @app.cli.command("temas-embed")
    @click.option("--empresa", "empresa_arg", required=True, help="ID ou nome da empresa.")
    @click.option(
        "--modelo",
        default="text-embedding-3-small",
        help="Modelo OpenAI (default text-embedding-3-small, 1536d).",
    )
    @click.option("--limite", type=int, default=None, help="Cap defensivo de verbatins.")
    @click.option("--dry-run", is_flag=True, default=False)
    def temas_embed(empresa_arg, modelo, limite, dry_run):
        """Gera embeddings dos verbatins com texto (Bloco 6 Caminho A CP-7).

        Idempotente: pula verbatins que já têm embedding com este modelo.
        Persiste em ``verbatim_embeddings``. Custo ~$0.02/1M tokens (~$0.006
        para 5915 verbatins do BH Airport).
        """
        import json as _json

        from src.models.empresa import Empresa
        from src.models.temas import VerbatimEmbedding
        from src.models.verbatim import Verbatim
        from src.temas.embeddings import embed_verbatins_pendentes
        from src.utils.db import db_session as _db_session

        with _db_session() as s:
            try:
                emp = s.get(Empresa, int(empresa_arg))
            except ValueError:
                emp = s.query(Empresa).filter_by(nome=empresa_arg).first()
            if emp is None:
                click.echo(f"empresa {empresa_arg!r} não encontrada", err=True)
                raise SystemExit(1)
            empresa_id = emp.id
            empresa_nome = emp.nome

            total_texto = (
                s.query(Verbatim)
                .filter(Verbatim.empresa_id == empresa_id, Verbatim.tem_texto.is_(True))
                .count()
            )
            ja_tem = (
                s.query(VerbatimEmbedding)
                .join(Verbatim, Verbatim.id == VerbatimEmbedding.verbatim_id)
                .filter(Verbatim.empresa_id == empresa_id, VerbatimEmbedding.modelo == modelo)
                .count()
            )
            pendentes = total_texto - ja_tem

        click.echo(f"[temas-embed] empresa={empresa_nome!r} (id={empresa_id})")
        click.echo(f"[temas-embed] modelo={modelo}")
        click.echo(f"[temas-embed] verbatins com texto: {total_texto}")
        click.echo(f"[temas-embed]   já com embedding: {ja_tem}")
        click.echo(f"[temas-embed]   pendentes: {pendentes}")
        if limite and limite < pendentes:
            click.echo(f"[temas-embed]   limite aplicado: {limite}")
        # Custo: ~50 tokens médio × $0.02/1M
        amostra = min(limite or pendentes, pendentes)
        custo_est = round(amostra * 50 / 1_000_000 * 0.02, 6)
        click.echo(f"[temas-embed] custo estimado: USD {custo_est}")

        if dry_run:
            click.echo("[temas-embed] dry-run: nada gerado.")
            return

        def _prog(processados, total, custo):
            click.echo(f"[temas-embed] [{processados}/{total}] usd={custo:.6f}")

        resumo = embed_verbatins_pendentes(
            empresa_id, modelo=modelo, limite=limite, progresso_callback=_prog
        )
        click.echo("\n[temas-embed] ============== RESUMO ==============")
        click.echo(_json.dumps(resumo, indent=2, ensure_ascii=False))

    # ── B6 Caminho A CP-10: flask temas-pipeline ──────────────────────
    @app.cli.command("temas-pipeline")
    @click.option("--empresa", "empresa_arg", required=True, help="ID ou nome da empresa.")
    @click.option(
        "--bucket",
        "buckets_arg",
        multiple=True,
        help='Chave "agrupamento_id:subpilar:tipo" (repetível). Vazio = todos.',
    )
    @click.option("--max-usd", type=float, default=None, help="Kill switch de custo acumulado.")
    @click.option(
        "--dry-run",
        is_flag=True,
        default=False,
        help="Lista buckets elegíveis + custo estimado, sem LLM nem DB.",
    )
    def temas_pipeline(empresa_arg, buckets_arg, max_usd, dry_run):
        """Pipeline embeddings → clustering → rotulagem → cache (Caminho A).

        Idempotente. Sobrescreve temas_cache por bucket, mantém temas/
        verbatim_temas (idempotência via UNIQUE).
        """
        import json as _json
        from dataclasses import asdict
        from datetime import datetime
        from pathlib import Path

        from src.models.empresa import Empresa
        from src.temas.pipeline import processar_empresa
        from src.utils.db import db_session as _db_session

        with _db_session() as s:
            try:
                emp = s.get(Empresa, int(empresa_arg))
            except ValueError:
                emp = s.query(Empresa).filter_by(nome=empresa_arg).first()
            if emp is None:
                click.echo(f"empresa {empresa_arg!r} não encontrada", err=True)
                raise SystemExit(1)
            empresa_id = emp.id
            empresa_nome = emp.nome

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = Path(__file__).parent.parent / "data" / f"temas_pipeline_{ts}.json"

        click.echo(f"[temas-pipeline] empresa={empresa_nome!r} (id={empresa_id})")
        if buckets_arg:
            click.echo(f"[temas-pipeline] restrição: {len(buckets_arg)} bucket(s)")
        if dry_run:
            click.echo("[temas-pipeline] DRY-RUN")
        if max_usd is not None:
            click.echo(f"[temas-pipeline] kill switch max_usd={max_usd}")

        def _prog(chave, label, vol):
            click.echo(f"[temas-pipeline] {chave:30s} → {label!r} (vol={vol})")

        resumo = processar_empresa(
            empresa_id,
            so_buckets=list(buckets_arg) if buckets_arg else None,
            max_usd=max_usd,
            callback_progresso=_prog,
            dry_run=dry_run,
        )
        click.echo("\n[temas-pipeline] ============== RESUMO ==============")
        resumo_dict = asdict(resumo)
        click.echo(_json.dumps(resumo_dict, indent=2, ensure_ascii=False, default=str))
        log_path.write_text(_json.dumps(resumo_dict, indent=2, ensure_ascii=False, default=str))
        click.echo(f"[temas-pipeline] log: {log_path}")

    # ── B7 CP-3/CP-3a: flask temas-cruzar (Nível 4) ───────────────────
    @app.cli.command("temas-cruzar")
    @click.option("--empresa", "empresa_arg", required=True, help="ID ou nome da empresa.")
    @click.option(
        "--semantico",
        is_flag=True,
        default=False,
        help="Também roda a Fase 2 semântica (centróides + curadoria Haiku). Custa LLM.",
    )
    def temas_cruzar(empresa_arg, semantico):
        """Detecta cruzamentos N4 e grava em temas_cruzamentos.

        Fase 1 (literal, sem custo) sempre roda. ``--semantico`` adiciona a
        Fase 2 (famílias por embedding + curadoria Haiku). Idempotente por fase.
        """
        from src.models.empresa import Empresa
        from src.temas.cruzamento import (
            detectar_e_persistir_literais,
            detectar_e_persistir_semanticos,
        )
        from src.utils.db import db_session as _db_session

        with _db_session() as s:
            try:
                emp = s.get(Empresa, int(empresa_arg))
            except ValueError:
                emp = s.query(Empresa).filter_by(nome=empresa_arg).first()
            if emp is None:
                click.echo(f"empresa {empresa_arg!r} não encontrada", err=True)
                raise SystemExit(1)
            empresa_id = emp.id
            empresa_nome = emp.nome

        click.echo(f"[temas-cruzar] empresa={empresa_nome!r} (id={empresa_id})")
        resumo = detectar_e_persistir_literais(empresa_id)
        click.echo(f"[temas-cruzar] temas analisados: {resumo.temas_analisados}")
        click.echo(f"[temas-cruzar] cruzamentos literais: {resumo.cruzamentos_criados}")
        for c in sorted(resumo.detalhes, key=lambda x: -x["peso"]):
            click.echo(
                f"  peso={c['peso']:7.2f}  {c['tema_label']:28s} "
                f"nSub={c['n_subpilares_distintos']}  {c['buckets_envolvidos']}"
            )

        if semantico:
            click.echo("[temas-cruzar] Fase 2 semântica (curadoria Haiku)...")
            rs = detectar_e_persistir_semanticos(empresa_id)
            click.echo(
                f"[temas-cruzar] pares candidatos: {rs.pares_candidatos} | "
                f"confirmados: {rs.confirmados} | filtrados: {rs.filtrados} | "
                f"chamadas: {rs.chamadas_llm} (in={rs.input_tokens} out={rs.output_tokens})"
            )
            for c in sorted(rs.detalhes, key=lambda x: -x["peso"]):
                click.echo(
                    f"  peso={c['peso']:7.2f}  {c['tema_label']:28s} "
                    f"nSub={c['n_subpilares_distintos']}  membros={c['membros']}"
                )

    # ── B7 CP-4: flask temas-acoes (Nível 5, Sonnet) ──────────────────
    @app.cli.command("temas-acoes")
    @click.option("--empresa", "empresa_arg", required=True, help="ID ou nome da empresa.")
    @click.option(
        "--top-pontuais",
        type=int,
        default=23,
        help="Quantos temas pontuais (além dos cruzamentos) recebem ação.",
    )
    def temas_acoes(empresa_arg, top_pontuais):
        """Gera ações de venda N5 (Sonnet) p/ cruzamentos + top temas. Custa LLM.

        Idempotente: regrava acoes_venda da empresa. Impacto qualitativo
        (alto/medio/baixo); R$ fica para quando houver LTV setorial.
        """
        from src.models.empresa import Empresa
        from src.temas.acao import gerar_e_persistir_acoes
        from src.utils.db import db_session as _db_session

        with _db_session() as s:
            try:
                emp = s.get(Empresa, int(empresa_arg))
            except ValueError:
                emp = s.query(Empresa).filter_by(nome=empresa_arg).first()
            if emp is None:
                click.echo(f"empresa {empresa_arg!r} não encontrada", err=True)
                raise SystemExit(1)
            empresa_id = emp.id
            empresa_nome = emp.nome

        click.echo(f"[temas-acoes] empresa={empresa_nome!r} (id={empresa_id})")
        r = gerar_e_persistir_acoes(empresa_id, top_pontuais=top_pontuais)
        click.echo(
            f"[temas-acoes] alvos={r.alvos} geradas={r.acoes_geradas} "
            f"descartadas={r.descartadas} | dist={r.distribuicao}"
        )
        click.echo(
            f"[temas-acoes] chamadas Sonnet={r.chamadas_llm} "
            f"tokens in={r.input_tokens} out={r.output_tokens}"
        )
        for d in r.detalhes:
            click.echo(
                f"  [{d['impacto_qualitativo']:5s}] {d['tema_label']:26s} "
                f"({d['tipo_alvo']}) → {d['acao'][:80]}"
            )

    # ── B6.6 CP-3: flask pipeline-pos-coleta ──────────────────────────
    @app.cli.command("pipeline-pos-coleta")
    @click.option("--empresa", "empresa_arg", required=True, help="ID ou nome da empresa.")
    @click.option(
        "--limiar",
        type=int,
        default=None,
        help="Mínimo de verbatins novos (não classificados) p/ rodar. Default 50.",
    )
    @click.option(
        "--force",
        is_flag=True,
        default=False,
        help="Roda mesmo abaixo do limiar.",
    )
    @click.option(
        "--limite",
        type=int,
        default=None,
        help="Máx. de verbatins pendentes a classificar nesta execução (default: todos).",
    )
    def pipeline_pos_coleta(empresa_arg, limiar, force, limite):
        """Pós-coleta: classifica novos → embeddings → temas → cruzamentos → ações.

        Roda só se houver novos verbatins ≥ limiar (--force ignora). Substitui o
        temas-extrair legado. Custa LLM (classificação + rotulagem + Sonnet).
        """
        from src.models.empresa import Empresa
        from src.temas.pos_coleta import LIMIAR_NOVOS_DEFAULT, executar_pos_coleta
        from src.utils.db import db_session as _db_session

        with _db_session() as s:
            try:
                emp = s.get(Empresa, int(empresa_arg))
            except ValueError:
                emp = s.query(Empresa).filter_by(nome=empresa_arg).first()
            if emp is None:
                click.echo(f"empresa {empresa_arg!r} não encontrada", err=True)
                raise SystemExit(1)
            empresa_id = emp.id
            empresa_nome = emp.nome

        lim = limiar if limiar is not None else LIMIAR_NOVOS_DEFAULT

        def _prog(chave, label, vol):
            click.echo(f"[pos-coleta]   {chave:28s} → {label!r} (vol={vol})")

        click.echo(
            f"[pos-coleta] empresa={empresa_nome!r} (id={empresa_id}) limiar={lim} "
            f"force={force} limite={limite if limite is not None else 'todos'}"
        )
        r = executar_pos_coleta(
            empresa_id, limiar=lim, force=force, limite=limite, callback_progresso=_prog
        )
        if not r.executou:
            click.echo(f"[pos-coleta] {r.motivo_skip}")
            return
        click.echo(
            f"[pos-coleta] novos={r.novos} classificados={r.classificados} "
            f"(falhas={r.classif_falhas}) embeddings={r.embeddings_gerados}"
        )
        click.echo(
            f"[pos-coleta] clusters={r.clusters_rotulados} cruz_literais={r.cruz_literais} "
            f"cruz_semanticos={r.cruz_semanticos} acoes={r.acoes}"
        )
        click.echo(
            f"[pos-coleta] anomalias={r.anomalias} "
            f"diagnostico(gerados={r.diagnostico_gerados} pulados={r.diagnostico_pulados}) "
            f"perspectivas={r.perspectivas_classificadas} "
            f"sugestoes(subpilares={r.sugestoes_subpilares} geradas={r.sugestoes_geradas} "
            f"pulados={r.sugestoes_pulados})"
        )
        click.echo(
            f"[pos-coleta] lojas(qualificadas={r.lojas_qualificadas} "
            f"diag_gerados={r.loja_diag_gerados} diag_pulados={r.loja_diag_pulados} "
            f"sug_geradas={r.loja_sug_geradas} sug_pulados={r.loja_sug_pulados})"
        )
        click.echo(f"[pos-coleta] custo estimado ~${r.custo_estimado_usd}")

    # ── CP-poscoleta-watchdog: flask pos-coleta-watchdog (retoma pós-coleta) ──
    @app.cli.command("pos-coleta-watchdog")
    @click.option(
        "--cooldown-horas", type=int, default=None, help="Janela anti-thrash (default: 6)."
    )
    def pos_coleta_watchdog_cmd(cooldown_horas):
        """Varre as empresas e RETOMA o pós-coleta das que ficaram com estado
        parcial (subpilar/desfecho/embeddings/temas pendentes) — a rede de segurança
        contra a daemon-thread morta por redeploy. Lock por-empresa + cooldown.
        Roda no cron (sobrevive a redeploy). Idempotente: empresa limpa = no-op.
        """
        from src.temas.watchdog import COOLDOWN_HORAS, pos_coleta_watchdog

        cd = cooldown_horas if cooldown_horas is not None else COOLDOWN_HORAS
        click.echo(f"[watchdog] varrendo empresas · cooldown={cd}h")
        s = pos_coleta_watchdog(cooldown_horas=cd)
        click.echo(
            f"[watchdog] varridas={s['varridas']} retomadas={s['retomadas']} "
            f"cache_alinhado={s['cache_alinhado']} interrompidas={s['interrompidas']} "
            f"limpas={s['limpas']} puladas(cooldown={s['puladas_cooldown']} "
            f"lock={s['puladas_lock']})"
        )

    # ── CP distribuicao-simbolos: flask simbolos-redistribuir ($0, sem LLM) ──
    @app.cli.command("simbolos-redistribuir")
    @click.option("--empresa", "empresa_arg", required=True, help="ID ou nome da empresa.")
    @click.option(
        "--dry-run",
        is_flag=True,
        default=False,
        help="Mede a migração SEM gravar (mostra quantos saem de Pa1 e pra onde).",
    )
    def simbolos_redistribuir(empresa_arg, dry_run):
        """Redistribui os verbatins só-símbolo pelos pilares (cascata por
        valência). Roda também dentro do pipeline-pos-coleta; este comando é p/
        rodar/auditar avulso. ``--dry-run`` não grava."""
        from src.coletor.distribuicao_simbolos import redistribuir_simbolos
        from src.models.empresa import Empresa
        from src.utils.db import db_session as _db_session

        with _db_session() as s:
            try:
                emp = s.get(Empresa, int(empresa_arg))
            except ValueError:
                emp = s.query(Empresa).filter_by(nome=empresa_arg).first()
            if emp is None:
                click.echo(f"empresa {empresa_arg!r} não encontrada", err=True)
                raise SystemExit(1)
            empresa_id, empresa_nome = emp.id, emp.nome

        r = redistribuir_simbolos(empresa_id, dry_run=dry_run)
        modo = "DRY-RUN (não gravou)" if dry_run else "APLICADO"
        click.echo(f"[simbolos] empresa={empresa_nome!r} (id={empresa_id}) — {modo}")
        click.echo(f"[simbolos] total={r['total_simbolos']} saem_de_Pa1={r['saem_de_pa1']}")
        click.echo(f"[simbolos] por nível: {r['por_nivel']}")
        click.echo(f"[simbolos] destino por pilar: {r['destino_pilar']}")
        for v in ("promotor", "conversivel", "detrator"):
            click.echo(f"[simbolos]   {v:11s} → {r['destino_por_valencia'][v]}")

    # ── CP guard-simbolos: flask simbolos-guard (auto-cura resíduo, $0) ──
    @app.cli.command("simbolos-guard")
    @click.option(
        "--dry-run",
        is_flag=True,
        default=False,
        help="Lista as empresas com resíduo SEM gravar.",
    )
    def simbolos_guard(dry_run):
        """Guard auto-curável: varre TODAS as empresas e redistribui o símbolo
        residual (tem_texto=False ainda no marcador provisório — pós-coleta que
        pulou por limiar ou morreu). Idempotente, $0. Roda também 1×/noite no
        cron (coleta_noturna_todas); este comando é p/ rodar avulso."""
        from src.coletor.distribuicao_simbolos import curar_simbolos_residuais

        g = curar_simbolos_residuais(dry_run=dry_run)
        modo = "DRY-RUN (não gravou)" if dry_run else "APLICADO"
        click.echo(f"[guard-simbolos] {modo} — empresas com resíduo: {len(g['curadas'])}")
        for c in g["curadas"]:
            click.echo(
                f"[guard-simbolos]   empresa {c['empresa_id']}: "
                f"{c['total_simbolos']} símbolos ({c['saem_de_pa1']} saem de Pa1)"
            )

    # ── CP coletas-reaper: flask coletas-reaper (libera locks de coleta órfã) ──
    from src.coletor.orquestrador import REAPER_LIMITE_SEGUNDOS

    @app.cli.command("coletas-reaper")
    @click.option(
        "--limite-segundos",
        type=int,
        default=REAPER_LIMITE_SEGUNDOS,
        show_default=True,
        help="Idade mínima (s) p/ considerar órfã. 0 = reapa TODAS as 'rodando' já.",
    )
    def coletas_reaper(limite_segundos):
        """Marca como 'erro' as ColetaExecucao presas em 'rodando' há mais que
        --limite-segundos (libera o lock pra a fonte voltar a ser coletável).
        Útil quando um deploy/restart mata a daemon-thread no meio da coleta e
        deixa órfãs presas. Idempotente. ``--limite-segundos 0`` reapa todas na
        hora (use só quando souber que não há coleta legítima em andamento)."""
        from src.coletor.orquestrador import re_marca_orfas

        n = re_marca_orfas(limite_segundos=limite_segundos)
        click.echo(f"[coletas-reaper] limite={limite_segundos}s — {n} órfã(s) marcada(s) 'erro'")

    # ── CP local-no-prompt: flask reclassificar-tenant-rejection ──────
    @app.cli.command("reclassificar-tenant-rejection")
    @click.option("--empresa", "empresa_arg", required=True, help="ID ou nome da empresa.")
    @click.option(
        "--dry-run",
        is_flag=True,
        default=False,
        help="Mostra antes→depois SEM gravar (mede a migração antes de aplicar).",
    )
    def reclassificar_tenant_rejection(empresa_arg, dry_run):
        """Reclassifica os verbatins que o classificador (sem o local no prompt)
        descartou como sem_lastro com justificativa de tenant-rejection ('refere-se
        a [loja], não ao aeroporto'), MAS que são reviews de loja física (rating).
        Reusa classificar() já com o local (prompt v3.2). Social (sem rating) fica
        FORA — listado à parte. ``--dry-run`` não grava."""
        from sqlalchemy import or_  # noqa: F401  (mantém paridade de imports do módulo)

        from src.classifier.classifier_v3 import classificar
        from src.models.empresa import Empresa
        from src.models.fonte import Fonte
        from src.models.local import Local
        from src.models.verbatim import Verbatim
        from src.utils.db import db_session as _db_session

        with _db_session() as s:
            try:
                emp = s.get(Empresa, int(empresa_arg))
            except ValueError:
                emp = s.query(Empresa).filter_by(nome=empresa_arg).first()
            if emp is None:
                click.echo(f"empresa {empresa_arg!r} não encontrada", err=True)
                raise SystemExit(1)
            empresa_id, nome, setor = emp.id, emp.nome, emp.setor
            fontes = {
                f.id: f.conector_tipo for f in s.query(Fonte).filter_by(empresa_id=empresa_id)
            }
            locais = {x.id: x.nome for x in s.query(Local).filter_by(empresa_id=empresa_id)}

            # Conjunto-alvo: sem_lastro v3.0, tenant-rejection, COM rating (loja física), COM local.
            base = s.query(Verbatim).filter(
                Verbatim.empresa_id == empresa_id,
                Verbatim.subpilar == "sem_lastro",
                Verbatim.prompt_versao == "v3.0",
                Verbatim.local_id.isnot(None),
                Verbatim.justificativa.like("%refere-se a%"),
                Verbatim.justificativa.like("%aeroporto%"),
            )
            alvos = base.filter(Verbatim.rating.isnot(None)).order_by(Verbatim.id).all()
            social = base.filter(Verbatim.rating.is_(None)).order_by(Verbatim.id).all()

            modo = "DRY-RUN (não gravou)" if dry_run else "APLICADO"
            click.echo(f"[tenant] empresa={nome!r} (id={empresa_id}) — {modo}")
            click.echo(f"[tenant] alvos (c/rating)={len(alvos)} · social (s/rating)={len(social)}")

            reanc = 0
            por_pilar: dict = {}
            for v in alvos:
                try:
                    r = classificar(
                        texto=v.texto,
                        empresa_nome=nome,
                        empresa_setor=setor,
                        fonte_tipo=fontes.get(v.fonte_id),
                        local_nome=locais.get(v.local_id),
                    )
                except Exception as exc:  # noqa: BLE001
                    click.echo(f"[tenant]   v{v.id} ERRO: {type(exc).__name__}: {exc}", err=True)
                    continue
                antes = v.subpilar
                if r.subpilar != "sem_lastro":
                    reanc += 1
                    por_pilar[r.subpilar] = por_pilar.get(r.subpilar, 0) + 1
                click.echo(
                    f"[tenant]   v{v.id} [{locais.get(v.local_id, '?')[:24]}] "
                    f"{antes} → {r.subpilar}/{r.tipo} (conf {r.confianca}) · {v.texto[:45]!r}"
                )
                if not dry_run:
                    v.subpilar, v.tipo, v.confianca = r.subpilar, r.tipo, r.confianca
                    v.justificativa, v.prompt_versao = r.justificativa, r.prompt_versao

            ficaram = len(alvos) - reanc
            click.echo(
                f"[tenant] RESULTADO: reancorados={reanc} (por pilar {por_pilar}) · "
                f"seguem sem_lastro (fora-de-lugar reais)={ficaram}"
            )
            click.echo(f"[tenant] custo estimado ~${reanc * 0.0005 + ficaram * 0.0005:.4f}")
            if social:
                click.echo(f"[tenant] SOCIAL não reprocessado ({len(social)}) — decidir à parte:")
                for v in social:
                    src = f"{fontes.get(v.fonte_id)}/{locais.get(v.local_id, '?')[:18]}"
                    click.echo(f"[tenant]   v{v.id} [{src}] {v.texto[:44]!r}")

    # ── flask reclassificar-prompt-versao (migração de prompt v3.1→v3.2) ──
    @app.cli.command("reclassificar-prompt-versao")
    @click.option("--empresa", "empresa_arg", required=True, help="ID ou nome da empresa.")
    @click.option(
        "--de",
        "de_versao",
        default="v3.1",
        show_default=True,
        help="prompt_versao de ORIGEM (só verbatins de texto com este valor).",
    )
    @click.option(
        "--so-candidatos",
        is_flag=True,
        default=False,
        help="Restringe aos que a nova versão tende a mudar: tipo='conversivel' OU subpilar='A2'.",
    )
    @click.option(
        "--limite",
        type=int,
        default=None,
        help="Máx. de verbatins-alvo (amostra p/ --dry-run; cap do zeramento no apply).",
    )
    @click.option(
        "--dry-run",
        is_flag=True,
        default=False,
        help="Mede antes→depois SEM gravar (serial, custa LLM). Sem a flag: ZERA o alvo "
        "e reclassifica via Batch API (classificar_pendentes, ~50% mais barato).",
    )
    def reclassificar_prompt_versao(empresa_arg, de_versao, so_candidatos, limite, dry_run):
        """Reclassifica com o prompt ATUAL os verbatins classificados por um prompt
        antigo (``--de``). NÃO recoleta nada — reusa o texto já no banco.

        Fluxo recomendado (custo-consciente): ``--dry-run --limite 200`` numa
        amostra pra medir o flip real; se valer, aplique (sem ``--dry-run``).

        ``--so-candidatos`` mira só ``tipo='conversivel'`` OU ``subpilar='A2'`` —
        os que a v3.2 tende a mudar (o resto é estável). O apply ZERA o subpilar do
        alvo (vira pendente) e chama ``classificar_pendentes`` (Batch API), que
        reclassifica TODOS os pendentes da empresa (alvo + eventuais já-pendentes).
        Agregados (ratios/temas/anomalias/Painel) NÃO são recalculados aqui — rode
        ``pipeline-pos-coleta`` depois p/ refletir.
        """
        from collections import Counter

        from sqlalchemy import or_

        from src.classifier.classifier_v3 import classificar
        from src.models.empresa import Empresa
        from src.models.fonte import Fonte
        from src.models.local import Local
        from src.models.verbatim import Verbatim
        from src.utils.db import db_session as _db_session

        with _db_session() as s:
            try:
                emp = s.get(Empresa, int(empresa_arg))
            except ValueError:
                emp = s.query(Empresa).filter_by(nome=empresa_arg).first()
            if emp is None:
                click.echo(f"empresa {empresa_arg!r} não encontrada", err=True)
                raise SystemExit(1)
            empresa_id, nome, setor = emp.id, emp.nome, emp.setor
            fontes = {
                f.id: f.conector_tipo for f in s.query(Fonte).filter_by(empresa_id=empresa_id)
            }
            locais = {x.id: x.nome for x in s.query(Local).filter_by(empresa_id=empresa_id)}

            q = s.query(Verbatim).filter(
                Verbatim.empresa_id == empresa_id,
                Verbatim.tem_texto.is_(True),
                Verbatim.prompt_versao == de_versao,
            )
            if so_candidatos:
                q = q.filter(or_(Verbatim.tipo == "conversivel", Verbatim.subpilar == "A2"))
            q = q.order_by(Verbatim.id)
            if limite:
                q = q.limit(limite)
            # Valores planos: não segura a sessão durante as chamadas LLM do dry-run.
            alvos = [(v.id, v.subpilar, v.tipo, v.texto, v.fonte_id, v.local_id) for v in q.all()]

        escopo = "candidatos (conversivel|A2)" if so_candidatos else "todos"
        modo = "DRY-RUN (serial, não grava)" if dry_run else "APLICAR (Batch API)"
        click.echo(
            f"[reclassif] empresa={nome!r} (id={empresa_id}) de={de_versao} escopo={escopo} "
            f"limite={limite if limite is not None else 'todos'} alvos={len(alvos)} · {modo}"
        )
        if not alvos:
            click.echo("[reclassif] nada a reclassificar.")
            return

        if dry_run:
            mudaram = 0
            transicoes: Counter = Counter()
            exemplos = []
            for vid, sub, tipo, texto, fonte_id, local_id in alvos:
                antes = f"{sub}/{tipo}"
                try:
                    r = classificar(
                        texto=texto,
                        empresa_nome=nome,
                        empresa_setor=setor,
                        fonte_tipo=fontes.get(fonte_id),
                        local_nome=locais.get(local_id),
                    )
                except Exception as exc:  # noqa: BLE001
                    click.echo(f"[reclassif]   v{vid} ERRO: {type(exc).__name__}: {exc}", err=True)
                    continue
                depois = f"{r.subpilar}/{r.tipo}"
                if depois != antes:
                    mudaram += 1
                    transicoes[f"{antes} → {depois}"] += 1
                    if len(exemplos) < 10:
                        exemplos.append((vid, antes, depois, (texto or "")[:60]))
            pct = (100 * mudaram / len(alvos)) if alvos else 0
            click.echo(f"[reclassif] MUDARIAM: {mudaram}/{len(alvos)} ({pct:.0f}%)")
            for trans, n in transicoes.most_common():
                click.echo(f"[reclassif]   {n:>5}  {trans}")
            for vid, a, d, txt in exemplos:
                click.echo(f"[reclassif]   ex v{vid}: {a} → {d} · {txt!r}")
            click.echo("[reclassif] DRY-RUN — nada gravado.")
            return

        # APLICAR: zera o alvo (vira pendente) e reclassifica via Batch API.
        alvo_ids = [a[0] for a in alvos]
        with _db_session() as s2:
            s2.query(Verbatim).filter(Verbatim.id.in_(alvo_ids)).update(
                {
                    Verbatim.subpilar: None,
                    Verbatim.tipo: None,
                    Verbatim.confianca: None,
                    Verbatim.justificativa: None,
                    Verbatim.prompt_versao: None,
                },
                synchronize_session=False,
            )
        click.echo(
            f"[reclassif] zerados {len(alvo_ids)} verbatins → classificar_pendentes (Batch)..."
        )
        from src.temas.pos_coleta import classificar_pendentes

        stats = classificar_pendentes(empresa_id)
        click.echo(
            f"[reclassif] resultado: classificados={stats['classificados']} "
            f"falhas={stats['falhas']}"
        )

        # Poda de vínculos órfãos: verbatim_temas é aditivo, então um alvo que
        # mudou de bucket mantinha o vínculo ao tema antigo. Sweep AGORA — depois
        # do classificar_pendentes — quando o subpilar/tipo novo já foi gravado
        # (verbatins ainda NULL por timeout do batch são pulados pelo primitivo).
        from src.temas.persistencia import reconciliar_vinculos

        rec = reconciliar_vinculos(empresa_id, verbatim_ids=alvo_ids)
        click.echo(
            f"[reclassif] poda de vínculos órfãos: removidos={rec['vinculos_removidos']} "
            f"(avaliados={rec['verbatins_avaliados']})"
        )
        click.echo(
            "[reclassif] OBS: agregados (ratios/temas/anomalias/Painel) NÃO "
            "recalculados.\n"
            "[reclassif] Fluxo de equalização completo:\n"
            "[reclassif]   1. (feito) reclassificar-prompt-versao --apply "
            "(reclassifica + poda alvos)\n"
            "[reclassif]   2. flask reconciliar-vinculos --empresa N "
            "(retroativo, se reclassificou antes desta poda)\n"
            "[reclassif]   3. flask pipeline-pos-coleta --empresa N --force "
            "(recalcula cache/Painel + re-tematiza)"
        )

    # ── flask reconciliar-vinculos (poda retroativa de vínculos órfãos) ──
    @app.cli.command("reconciliar-vinculos")
    @click.option("--empresa", "empresa_arg", required=True, help="ID ou nome da empresa.")
    def reconciliar_vinculos_cmd(empresa_arg):
        """Poda vínculos verbatim_temas órfãos de uma empresa JÁ reclassificada.

        Remove os links LLM cujo bucket (subpilar:tipo gravado no bucket_chave do
        vínculo) não bate mais com o subpilar/tipo ATUAL do verbatim. Preserva
        origem manual/merge, bucket_chave NULL e verbatins com subpilar atual NULL.
        Idempotente. NÃO recalcula agregados.

        Use no caso retroativo: empresas reclassificadas ANTES desta poda existir
        (ex.: empresa 16/Club Med). O apply de reclassificar-prompt-versao já poda
        os alvos automaticamente; este comando cobre o que ficou para trás.

        Fluxo de equalização completo:
          1. reclassificar-prompt-versao --apply  (reclassifica + poda os alvos)
          2. flask reconciliar-vinculos --empresa N   (retroativo, este comando)
          3. flask pipeline-pos-coleta --empresa N --force  (recalcula cache/Painel)
        """
        from src.models.empresa import Empresa
        from src.temas.persistencia import reconciliar_vinculos
        from src.utils.db import db_session as _db_session

        with _db_session() as s:
            try:
                emp = s.get(Empresa, int(empresa_arg))
            except ValueError:
                emp = s.query(Empresa).filter_by(nome=empresa_arg).first()
            if emp is None:
                click.echo(f"empresa {empresa_arg!r} não encontrada", err=True)
                raise SystemExit(1)
            empresa_id, nome = emp.id, emp.nome

        rec = reconciliar_vinculos(empresa_id)
        click.echo(
            f"[reconciliar] empresa={nome!r} (id={empresa_id}): "
            f"avaliados={rec['verbatins_avaliados']} vínculos_removidos={rec['vinculos_removidos']}"
        )
        click.echo(
            "[reconciliar] OBS: rode 'flask pipeline-pos-coleta --empresa N --force' "
            "depois p/ recalcular cache/Painel + re-tematizar."
        )

    # ── flask reconciliar-reclassificados (ciclo retroativo em lote) ──
    @app.cli.command("reconciliar-reclassificados")
    @click.option(
        "--empresa",
        "empresa_arg",
        default=None,
        help="ID ou nome de UMA empresa. Omita e use --todas p/ auto-detectar.",
    )
    @click.option(
        "--todas",
        is_flag=True,
        default=False,
        help="Todas as empresas com vínculos órfãos (auto-detecta pelo mesmo predicado da poda).",
    )
    @click.option(
        "--dry-run",
        is_flag=True,
        default=False,
        help="Só LISTA as empresas afetadas + nº de órfãos. NÃO roda o ciclo.",
    )
    def reconciliar_reclassificados(empresa_arg, todas, dry_run):
        """Aplica o ciclo de reconciliação retroativa nas empresas reclassificadas.

        Por empresa, na ordem: ``reconciliar_vinculos`` (poda vínculos órfãos) →
        ``executar_pos_coleta(force=True, aplicar_janela=False)`` (regenera o cache
        de TODOS os buckets + re-tematiza). Idempotente — rodar 2x converge (a 2ª
        poda remove ~0; o pós-coleta nunca recria órfão, pois clusteriza pelo
        subpilar/tipo ATUAL).

        Seleção: ``--empresa N`` (uma, explícita) OU ``--todas`` (auto-detecta as
        que têm vínculo órfão). ``--dry-run`` só lista. Gate de concorrência: pula
        empresa com classificação em andamento. Carve-outs (manual/merge, bucket
        NULL) preservados pelo ``reconciliar_vinculos``.
        """
        from sqlalchemy import func

        from src.models.empresa import Empresa
        from src.models.temas import TemaCache
        from src.temas.persistencia import (
            empresas_com_vinculos_orfaos,
            reconciliar_vinculos,
        )
        from src.temas.pos_coleta import _lock_empresa, executar_pos_coleta
        from src.utils.db import db_session as _db_session

        if not empresa_arg and not todas:
            click.echo("informe --empresa N ou --todas", err=True)
            raise SystemExit(1)

        # 1) Monta a lista de alvos (id → nº de órfãos quando conhecido).
        if empresa_arg:
            with _db_session() as s:
                try:
                    emp = s.get(Empresa, int(empresa_arg))
                except ValueError:
                    emp = s.query(Empresa).filter_by(nome=empresa_arg).first()
                if emp is None:
                    click.echo(f"empresa {empresa_arg!r} não encontrada", err=True)
                    raise SystemExit(1)
                alvos = [{"empresa_id": emp.id, "orfaos": None}]
        else:
            alvos = empresas_com_vinculos_orfaos()

        if not alvos:
            click.echo("[recl-em-lote] nenhuma empresa com vínculos órfãos — nada a fazer.")
            return

        # Resolve nomes p/ log.
        with _db_session() as s:
            nomes = {
                e.id: e.nome
                for e in s.query(Empresa).filter(Empresa.id.in_([a["empresa_id"] for a in alvos]))
            }

        click.echo(f"[recl-em-lote] {len(alvos)} empresa(s) afetada(s):")
        for a in alvos:
            eid = a["empresa_id"]
            orf = a["orfaos"]
            sufixo = f" órfãos≈{orf}" if orf is not None else ""
            click.echo(f"[recl-em-lote]   - id={eid} {nomes.get(eid, '?')!r}{sufixo}")

        if dry_run:
            click.echo("[recl-em-lote] DRY-RUN — nada executado.")
            return

        def _volume_cache(empresa_id: int) -> int:
            with _db_session() as s:
                v = s.query(func.coalesce(func.sum(TemaCache.volume), 0)).filter(
                    TemaCache.empresa_id == empresa_id
                )
                return int(v.scalar() or 0)

        # 2) Executa o ciclo por empresa.
        total_removidos = 0
        processadas = 0
        puladas = 0
        for a in alvos:
            eid = a["empresa_id"]
            nome = nomes.get(eid, "?")

            # Gate de concorrência: se há classificação em andamento, pula.
            with _lock_empresa(eid) as got_lock:
                livre = got_lock
            if not livre:
                puladas += 1
                click.echo(f"[recl-em-lote] id={eid} {nome!r}: job em andamento — PULADA.")
                continue

            vol_antes = _volume_cache(eid)
            rec = reconciliar_vinculos(eid)
            r = executar_pos_coleta(eid, force=True, aplicar_janela=False)
            vol_depois = _volume_cache(eid)

            total_removidos += rec["vinculos_removidos"]
            processadas += 1
            click.echo(
                f"[recl-em-lote] id={eid} {nome!r}: "
                f"órfãos_removidos={rec['vinculos_removidos']} "
                f"volume_cache {vol_antes}→{vol_depois} "
                f"clusters={r.clusters_rotulados}"
            )

        click.echo(
            f"[recl-em-lote] RESUMO: processadas={processadas} puladas={puladas} "
            f"vínculos_removidos={total_removidos}"
        )

    # ── flask limpar-acumulo-temas (poda one-off do acúmulo entre rodadas) ──
    @app.cli.command("limpar-acumulo-temas")
    @click.option("--empresa", "empresa_arg", required=True, help="ID ou nome da empresa.")
    @click.option(
        "--dry-run",
        is_flag=True,
        default=False,
        help="Mede e reporta SEM gravar (poda + temas a desativar; não regenera cache).",
    )
    def limpar_acumulo_temas_cmd(empresa_arg, dry_run):
        """Poda o acúmulo de vínculos de tema entre rodadas (operação única).

        Por verbatim mantém só o vínculo LLM da rodada MAIS RECENTE e remove os
        anteriores (preserva origem manual/merge); desativa Tema que ficou sem
        vínculo vivo; regenera temas_cache a partir do resultado (link-based, sem
        re-clusterizar). Com --dry-run, só reporta os números.

        Contraparte one-off da correção de raiz no pipeline (tornar
        _upsert_tema_e_link não-aditivo). NÃO recoleta nem reclassifica.
        """
        from src.models.empresa import Empresa
        from src.temas.limpeza import limpar_acumulo_temas
        from src.utils.db import db_session as _db_session

        with _db_session() as s:
            try:
                emp = s.get(Empresa, int(empresa_arg))
            except ValueError:
                emp = s.query(Empresa).filter_by(nome=empresa_arg).first()
            if emp is None:
                click.echo(f"empresa {empresa_arg!r} não encontrada", err=True)
                raise SystemExit(1)
            empresa_id, nome = emp.id, emp.nome

        modo = "DRY-RUN (não grava)" if dry_run else "APLICAR"
        click.echo(f"[limpar-acumulo] empresa={nome!r} (id={empresa_id}) · {modo}")
        r = limpar_acumulo_temas(empresa_id, dry_run=dry_run)
        click.echo(
            f"[limpar-acumulo] verbatins_com_acumulo={r['verbatins_com_acumulo']} "
            f"vinculos_removidos={r['vinculos_removidos']} "
            f"temas_desativados={r['temas_desativados']}"
        )
        if dry_run:
            click.echo("[limpar-acumulo] DRY-RUN — nada gravado (cache não regenerado).")
        else:
            click.echo(f"[limpar-acumulo] cache regenerado: {r['cache_rows']} rows. Concluído.")

    # ── CP purge-linkedin-dup: flask purgar-verbatins-fonte ───────────
    @app.cli.command("purgar-verbatins-fonte")
    @click.option(
        "--fonte-id", "fonte_id", type=int, required=True, help="ID da fonte (deve estar INATIVA)."
    )
    @click.option(
        "--dry-run", is_flag=True, default=False, help="Mostra o que removeria SEM deletar."
    )
    @click.option(
        "--remover-cadastro",
        is_flag=True,
        default=False,
        help="Além dos verbatins, remove a fonte (e o local, se ficar órfão).",
    )
    def purgar_verbatins_fonte(fonte_id, dry_run, remover_cadastro):
        """Remove os verbatins de uma fonte INATIVA (ex.: fonte duplicada já
        desativada — LinkedIn /Empregador). GUARDA: só roda se a fonte estiver
        ``ativo=False``. CASCADE limpa embeddings/temas/reclassificações. Com
        ``--remover-cadastro`` apaga também a fonte (e o local, se órfão). Depois:
        ``pipeline-pos-coleta --empresa <id> --force`` recalcula os derivados."""
        from sqlalchemy import func

        from src.models.fonte import Fonte
        from src.models.local import Local
        from src.models.verbatim import Verbatim
        from src.utils.db import db_session as _db_session

        with _db_session() as s:
            fonte = s.get(Fonte, fonte_id)
            if fonte is None:
                click.echo(f"fonte {fonte_id} não encontrada", err=True)
                raise SystemExit(1)
            if fonte.ativo:
                click.echo(
                    f"fonte {fonte_id} está ATIVA — desative antes de purgar (guarda).", err=True
                )
                raise SystemExit(1)
            empresa_id = fonte.empresa_id
            verbs = s.query(Verbatim).filter_by(fonte_id=fonte_id)
            n = verbs.count()
            modo = "DRY-RUN (não removeu)" if dry_run else "APLICADO"
            click.echo(f"[purge] fonte={fonte_id} (empresa {empresa_id}, inativa) — {modo}")
            click.echo(f"[purge] verbatins a remover: {n}")
            for v in verbs.order_by(Verbatim.id).limit(5):
                click.echo(
                    f"[purge]   v{v.id} rid={v.review_id_externo} · {(v.texto or '')[:42]!r}"
                )

            local_id = fonte.entidade_id if fonte.entidade_tipo == "local" else None
            remove_local = False
            if remover_cadastro and local_id is not None:
                outras = (
                    s.query(func.count(Fonte.id))
                    .filter(
                        Fonte.entidade_tipo == "local",
                        Fonte.entidade_id == local_id,
                        Fonte.id != fonte_id,
                    )
                    .scalar()
                )
                remove_local = outras == 0
                loc = s.get(Local, local_id)
                nome_loc = loc.nome if loc else "?"
                click.echo(
                    f"[purge] cadastro: remover fonte {fonte_id}"
                    + (
                        f" + local {local_id} ({nome_loc}) [órfão]"
                        if remove_local
                        else f" (local {local_id} mantido — {outras} outra(s) fonte(s))"
                    )
                )

            if not dry_run:
                verbs.delete(synchronize_session=False)  # CASCADE: embeddings/temas/reclassif
                if remover_cadastro:
                    s.delete(s.get(Fonte, fonte_id))
                    if remove_local:
                        loc = s.get(Local, local_id)
                        if loc is not None:
                            s.delete(loc)
            click.echo(f"[purge] OK ({modo}).")
            click.echo(
                f"[purge] recompute: flask pipeline-pos-coleta --empresa {empresa_id} --force"
            )

    # ── Monitoramento ML CP-5: flask anomalias-detectar ($0, sem LLM) ──
    @app.cli.command("anomalias-detectar")
    @click.option("--empresa", "empresa_arg", required=True, help="ID ou nome da empresa.")
    @click.option(
        "--sem-snapshot",
        is_flag=True,
        default=False,
        help="Não grava temas_snapshot/cruzamentos_snapshot desta rodada.",
    )
    def anomalias_detectar(empresa_arg, sem_snapshot):
        """Detecta anomalias (Camada 1 indicador + Camada 2 temas) e persiste.

        Recomputa a série mensal de ratios, roda as duas camadas com corroboração
        cruzada e grava em anomalias_detectadas (preservando validação humana).
        Sem custo de LLM — a leitura editorial é gerada à parte.
        """
        from src.anomalias.combinador import detectar_e_persistir
        from src.anomalias.ratios import recomputar_ratios_mensais
        from src.models.empresa import Empresa
        from src.utils.db import db_session as _db_session

        with _db_session() as s:
            try:
                emp = s.get(Empresa, int(empresa_arg))
            except ValueError:
                emp = s.query(Empresa).filter_by(nome=empresa_arg).first()
            if emp is None:
                click.echo(f"empresa {empresa_arg!r} não encontrada", err=True)
                raise SystemExit(1)
            empresa_id = emp.id
            empresa_nome = emp.nome

        click.echo(f"[anomalias] empresa={empresa_nome!r} (id={empresa_id})")
        n_ratios = recomputar_ratios_mensais(empresa_id)
        click.echo(f"[anomalias] ratios mensais recomputados: {n_ratios}")
        resumo = detectar_e_persistir(empresa_id, gravar_snapshot=not sem_snapshot)
        click.echo(
            f"[anomalias] total={resumo['total']} "
            f"por_tipo={resumo['por_tipo']} por_severidade={resumo['por_severidade']}"
        )
        click.echo(
            f"[anomalias] corroborados por tema={resumo['corroborados']} "
            f"validacoes preservadas={resumo['validacoes_preservadas']}"
        )

    # ── Monitoramento ML CP-3: flask anomalias-gerar-leituras (gasta Sonnet) ──
    @app.cli.command("anomalias-gerar-leituras")
    @click.option("--empresa", "empresa_arg", required=True, help="ID ou nome da empresa.")
    @click.option(
        "--limite",
        type=int,
        default=50,
        help="Máx. de leituras a gerar nesta rodada (controle de custo). Default 50.",
    )
    def anomalias_gerar_leituras(empresa_arg, limite):
        """Gera a leitura editorial (Sonnet) das anomalias SEM leitura e grava em
        leitura_editorial. NÃO sobrescreve as que já têm — só preenche as pendentes,
        da maior pra menor severidade/score (limitado por --limite). Custa LLM
        (~$0.02 por leitura). A detecção (anomalias-detectar) não gera leitura."""
        from sqlalchemy import or_

        from src.anomalias.editorial import gerar_e_persistir_leituras
        from src.models.anomalia import AnomaliaDetectada
        from src.models.empresa import Empresa
        from src.utils.db import db_session as _db_session

        with _db_session() as s:
            try:
                emp = s.get(Empresa, int(empresa_arg))
            except ValueError:
                emp = s.query(Empresa).filter_by(nome=empresa_arg).first()
            if emp is None:
                click.echo(f"empresa {empresa_arg!r} não encontrada", err=True)
                raise SystemExit(1)
            empresa_id, empresa_nome = emp.id, emp.nome
            # Pendentes = sem leitura_editorial (NULL/vazio); pior score primeiro.
            pendentes = [
                r[0]
                for r in s.query(AnomaliaDetectada.id)
                .filter(AnomaliaDetectada.empresa_id == empresa_id)
                .filter(
                    or_(
                        AnomaliaDetectada.leitura_editorial.is_(None),
                        AnomaliaDetectada.leitura_editorial == "",
                    )
                )
                .order_by(AnomaliaDetectada.score_final.desc())
                .all()
            ]

        alvos = pendentes[:limite]
        # ~$0.02/leitura: Sonnet in~1.4k tok ($3/1M) + out~0.8k tok ($15/1M).
        custo_est = round(len(alvos) * 0.02, 2)
        click.echo(
            f"[leituras] empresa={empresa_nome!r} (id={empresa_id}) "
            f"pendentes={len(pendentes)} a_gerar={len(alvos)} (limite={limite}) "
            f"custo_estimado~${custo_est}"
        )
        if not alvos:
            click.echo("[leituras] nada a gerar — todas as anomalias já têm leitura.")
            return

        m = gerar_e_persistir_leituras(empresa_id, ids=alvos)
        click.echo(
            f"[leituras] gerados={m['gerados']} falhas={m['falhas']} "
            f"por_tipo={m['por_tipo']} tokens(in={m['in']} out={m['out']}) "
            f"custo_real~${m['custo_usd']}"
        )
        for e in m["erros"]:
            click.echo(f"  ERRO {e['chave']}: {e['erro']}", err=True)

    # ── Bloco 8 / Diagnóstico CP-B1: flask diagnostico-gerar (gasta Sonnet) ──
    @app.cli.command("diagnostico-gerar")
    @click.option("--empresa", "empresa_arg", required=True, help="ID ou nome da empresa.")
    @click.option(
        "--agrupamento",
        "agrupamento_id",
        type=int,
        default=None,
        help="ID do agrupamento (escopo). Omitido = empresa inteira.",
    )
    def diagnostico_gerar(empresa_arg, agrupamento_id):
        """Gera as leituras diagnósticas por subpilar (Sonnet) e grava em
        leituras_diagnostico. Custa LLM (~12 leituras curtas por escopo)."""
        from src.diagnostico.leituras import gerar_e_persistir_diagnostico
        from src.models.empresa import Empresa
        from src.utils.db import db_session as _db_session

        with _db_session() as s:
            try:
                emp = s.get(Empresa, int(empresa_arg))
            except ValueError:
                emp = s.query(Empresa).filter_by(nome=empresa_arg).first()
            if emp is None:
                click.echo(f"empresa {empresa_arg!r} não encontrada", err=True)
                raise SystemExit(1)
            empresa_id, empresa_nome = emp.id, emp.nome

        click.echo(
            f"[diagnostico] empresa={empresa_nome!r} (id={empresa_id}) "
            f"agrupamento={agrupamento_id or '(empresa toda)'}"
        )
        m = gerar_e_persistir_diagnostico(empresa_id, agrupamento_id)
        click.echo(
            f"[diagnostico] gerados={m['gerados']} falhas={m['falhas']} "
            f"tokens(in={m['in']} out={m['out']}) custo~${m['custo_usd']}"
        )
        for e in m["erros"]:
            click.echo(f"  ERRO {e['subpilar']}: {e['erro']}", err=True)

    # ── Bloco 8 / Planos de Ação CP-B2.2: flask perspectivas-classificar ──
    @app.cli.command("perspectivas-classificar")
    @click.option("--empresa", "empresa_arg", required=True, help="ID ou nome da empresa.")
    @click.option("--limite", type=int, default=None, help="Limita o nº de ações (amostra).")
    def perspectivas_classificar(empresa_arg, limite):
        """Classifica a perspectiva (1 das 6) das ações sem perspectiva, via Sonnet
        em lote. Persiste no overlay acoes_status. Incremental. Custa LLM."""
        from src.models.empresa import Empresa
        from src.planos.perspectiva import classificar_perspectivas
        from src.utils.db import db_session as _db_session

        with _db_session() as s:
            try:
                emp = s.get(Empresa, int(empresa_arg))
            except ValueError:
                emp = s.query(Empresa).filter_by(nome=empresa_arg).first()
            if emp is None:
                click.echo(f"empresa {empresa_arg!r} não encontrada", err=True)
                raise SystemExit(1)
            empresa_id, empresa_nome = emp.id, emp.nome

        click.echo(f"[perspectivas] empresa={empresa_nome!r} (id={empresa_id}) limite={limite}")
        m = classificar_perspectivas(empresa_id, limite=limite)
        click.echo(
            f"[perspectivas] classificados={m['classificados']} falhas={m['falhas']} "
            f"lotes={m['lotes']} tokens(in={m['in']} out={m['out']}) custo~${m['custo_usd']}"
        )

    # ── Bloco 8 / CP-PA: flask sugestoes-perspectiva (gasta Sonnet) ──
    @app.cli.command("sugestoes-perspectiva")
    @click.option("--empresa", "empresa_arg", required=True, help="ID ou nome da empresa.")
    @click.option(
        "--agrupamento",
        "agrupamento_id",
        type=int,
        default=None,
        help="ID do agrupamento (escopo). Omitido = empresa inteira.",
    )
    def sugestoes_perspectiva(empresa_arg, agrupamento_id):
        """Gera sugestões estruturais por subpilar × perspectiva (Sonnet) e grava em
        sugestoes_estruturais. ~12 subpilares × 1-6 frentes com alavanca. Custa LLM."""
        from src.models.empresa import Empresa
        from src.planos.sugestoes import gerar_e_persistir_sugestoes
        from src.utils.db import db_session as _db_session

        with _db_session() as s:
            try:
                emp = s.get(Empresa, int(empresa_arg))
            except ValueError:
                emp = s.query(Empresa).filter_by(nome=empresa_arg).first()
            if emp is None:
                click.echo(f"empresa {empresa_arg!r} não encontrada", err=True)
                raise SystemExit(1)
            empresa_id, empresa_nome = emp.id, emp.nome

        click.echo(
            f"[sugestoes] empresa={empresa_nome!r} (id={empresa_id}) "
            f"agrupamento={agrupamento_id or '(empresa toda)'}"
        )
        m = gerar_e_persistir_sugestoes(empresa_id, agrupamento_id)
        click.echo(
            f"[sugestoes] subpilares={m['subpilares']} sugestoes={m['sugestoes']} "
            f"por_perspectiva={m['por_perspectiva']} tokens(in={m['in']} out={m['out']}) "
            f"custo~${m['custo_usd']}"
        )
        for e in m["erros"]:
            click.echo(f"  ERRO {e['subpilar']}: {e['erro']}", err=True)


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5050, debug=True)
