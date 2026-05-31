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

    # Selo de confiança por volume (CP-E2): fonte única dos limiares 30/10.
    from src.api.engajamento import selo_confianca

    @app.template_global("selo_emoji")
    def _selo_emoji(volume) -> str:
        return selo_confianca(int(volume or 0))[1]

    # Markdown leve nas respostas do IA Chat (CP-B4): bold + listas + quebras.
    from src.utils.markdown_leve import render_md_leve

    app.add_template_filter(render_md_leve, "md_leve")

    # ⓘ do glossário (CP-glossario-plugar-ui): {{ glossario_i('ratio') }} nas telas.
    # Lê do cadastro (glossario_termo) por slug; 1 query/request via flask.g.
    from src.ui import glossario_i as _glossario_i

    @app.template_global("glossario_i")
    def glossario_i(slug):  # noqa: ANN001, ANN201
        return _glossario_i(slug, debug=app.debug)

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
    def pipeline_pos_coleta(empresa_arg, limiar, force):
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
            f"[pos-coleta] empresa={empresa_nome!r} (id={empresa_id}) limiar={lim} force={force}"
        )
        r = executar_pos_coleta(empresa_id, limiar=lim, force=force, callback_progresso=_prog)
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
