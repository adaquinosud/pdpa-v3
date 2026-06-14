"""UI blueprint — páginas Jinja+HTMX do Bloco 4 CP5.

Rotas (todas server-side rendered):
    GET  /                   → redireciona para /empresas
    GET  /login              → form de login
    POST /login              → autentica e redireciona (HTML form)
    POST /logout             → limpa sessão e redireciona
    GET  /empresas           → lista de empresas (cliente vê só a sua)
    GET  /empresas/nova      → form criação manual (loyall_admin)
    POST /empresas/nova      → cria empresa
    GET  /empresas/importar  → form upload Excel
    POST /empresas/importar  → processa upload
    GET  /empresas/<id>      → visão geral (agrupamentos + locais + fontes)

HTMX partials (retornam fragmento HTML, não página inteira):
    GET  /ui/empresas/<id>/agrupamentos    → tabela parcial
    POST /ui/empresas/<id>/agrupamentos    → cria + devolve linha
    POST /ui/empresas/<id>/locais          → cria + devolve linha
    POST /ui/locais/<id>/fontes            → cria + devolve linha
    DELETE /ui/agrupamentos/<id>           → 200 vazio
    DELETE /ui/locais/<id>                 → 200 vazio
    DELETE /ui/fontes/<id>                 → 200 vazio
"""

from __future__ import annotations

import json
import re
from functools import wraps
from types import SimpleNamespace

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.exceptions import BadRequest

from src.auth import (
    PAPEL_CLIENTE,
    PAPEL_LOYALL,
    get_current_user,
    hash_senha,
    login_user,
    logout_user,
    verificar_senha,
)
from src.classifier.classifier_v3 import SUBPILARES_VALIDOS, TIPOS_VALIDOS
from src.models.agrupamento import Agrupamento
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.local import Local
from src.models.usuario import Usuario
from src.models.verbatim import Verbatim
from src.models.verbatim_reclassificacao import VerbatimReclassificacao
from src.utils.db import db_session


# ── View-model wrappers (sem ORM relationships) ──────────────────────────
# Construídos dentro de db_session(); usados pelos templates Jinja sem
# disparar lazy-load em objetos detached.


def _wrap_fonte(f, nome_local=None) -> SimpleNamespace:
    return SimpleNamespace(
        id=f.id,
        empresa_id=f.empresa_id,
        entidade_tipo=f.entidade_tipo,
        entidade_id=f.entidade_id,
        conector_tipo=f.conector_tipo,
        url=f.url,
        # Nome amigável do Local quando a fonte é de um local (entidade_tipo='local').
        # A tela exibe isto em vez do place_id cru (ChIJ…, guardado em url). None para
        # fontes de empresa (url costuma ser URL real de site/social → faz sentido exibir).
        nome_local=nome_local if f.entidade_tipo == "local" else None,
        ativo=bool(f.ativo),
        ultima_coleta=f.ultima_coleta,
        criada_em=f.criada_em,
        observacao=f.observacao,
    )


def _fontes_para_filtro(s, empresa_id):
    """Fontes da empresa p/ o dropdown de FILTRO, com ``nome_local`` resolvido
    (fonte de local → ``Local.nome``) — exibe o nome amigável em vez do place_id
    cru (guardado em ``url``). O filtro continua usando ``f.id``; ``nome_local`` é
    só o label. 1 query batch p/ os nomes dos locais (sem N+1)."""
    fonts = s.query(Fonte).filter_by(empresa_id=empresa_id).order_by(Fonte.conector_tipo).all()
    lids = {f.entidade_id for f in fonts if f.entidade_tipo == "local"}
    nomes = (
        {lid: nome for lid, nome in s.query(Local.id, Local.nome).filter(Local.id.in_(lids))}
        if lids
        else {}
    )
    return [
        SimpleNamespace(
            id=f.id,
            conector_tipo=f.conector_tipo,
            url=f.url,
            nome_local=(nomes.get(f.entidade_id) if f.entidade_tipo == "local" else None),
        )
        for f in fonts
    ]


def _wrap_local(loc, fontes=None) -> SimpleNamespace:
    # nome_local=loc.nome resolve o ChIJ → nome amigável em TODA fonte do local
    # (cobre local_card e o detalhe da empresa, que passam por aqui).
    fontes_w = [_wrap_fonte(f, nome_local=loc.nome) for f in (fontes or [])]
    return SimpleNamespace(
        id=loc.id,
        empresa_id=loc.empresa_id,
        agrupamento_id=loc.agrupamento_id,
        nome=loc.nome,
        endereco=loc.endereco,
        cidade=loc.cidade,
        uf=loc.uf,
        status=loc.status,
        observacao=loc.observacao,
        # CP-impacto-rs: os templates (view local_card + edit) leem estes 3 campos
        # para exibir o LTV. Sem eles aqui, viram Undefined no Jinja → "—"/input vazio
        # mesmo com o valor gravado no banco (o salvar sempre funcionou).
        ticket_medio=loc.ticket_medio,
        frequencia=loc.frequencia,
        ltv_origem=loc.ltv_origem,
        fontes=fontes_w,
        fontes_ativas=sum(1 for f in fontes_w if f.ativo),
        tem_fontes=bool(fontes_w),
    )


def _wrap_agrupamento(a, locais_w=None) -> SimpleNamespace:
    locais_w = locais_w or []
    total_fontes = sum(len(loc.fontes) for loc in locais_w)
    return SimpleNamespace(
        id=a.id,
        empresa_id=a.empresa_id,
        nome=a.nome,
        descricao=a.descricao,
        ativo=bool(a.ativo),
        locais=locais_w,
        fontes_ativas=sum(loc.fontes_ativas for loc in locais_w),
        total_fontes=total_fontes,
        tem_fontes=total_fontes > 0,
    )


def _ultima_coleta(s, empresa_id):
    """Última coleta da empresa: MAX(fonte.ultima_coleta), fallback
    MAX(verbatim.data_coleta). ``None`` se nunca coletou."""
    from sqlalchemy import func

    mf = s.query(func.max(Fonte.ultima_coleta)).filter(Fonte.empresa_id == empresa_id).scalar()
    if mf is not None:
        return mf
    return (
        s.query(func.max(Verbatim.data_coleta)).filter(Verbatim.empresa_id == empresa_id).scalar()
    )


def _wrap_empresa(e, ultima_coleta=None) -> SimpleNamespace:
    return SimpleNamespace(
        id=e.id,
        nome=e.nome,
        setor=e.setor,
        site=e.site,
        cnpj=e.cnpj,
        observacao=e.observacao,
        criada_em=e.criada_em,
        atualizada_em=e.atualizada_em,
        ultima_coleta=ultima_coleta,
        # CP-noturna-toggle: o toggle 🌙 na tela de cadastro lê este campo. Sem ele
        # no wrapper, o template lia undefined → sempre "desligada" (bug fbb2ee1).
        coleta_noturna_ativa=bool(e.coleta_noturna_ativa),
    )


ui_bp = Blueprint(
    "ui",
    __name__,
    url_prefix="",
    template_folder="../../templates",
    static_folder="../../static",
)


def _require_login_html():
    """Se não autenticado, redireciona para /login (não 401 JSON)."""
    if get_current_user() is None:
        return redirect(url_for("ui.login_form"))
    return None


def _require_loyall_html():
    """Se não é admin_loyall, devolve 403 HTML."""
    user = get_current_user()
    if user is None:
        return redirect(url_for("ui.login_form"))
    if user.papel != PAPEL_LOYALL:
        return render_template("403.html"), 403
    return None


def loyall_required_ui(f):
    """Decorator de NATUREZA (CP-O2 personas): rota INTERNA, só admin_loyall.

    Padroniza o gating das rotas internas (cadastro/coleta/monitoramento/etc.) —
    antes era inline e inconsistente (o que vazou o monitoramento). Cliente nunca
    chega aqui pelo menu (escondido por papel); o 403 é a rede de segurança p/
    URL direta. HTMX recebe fragmento (não a página 403 inteira no target)."""

    @wraps(f)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return redirect(url_for("ui.login_form"))
        if user.papel != PAPEL_LOYALL:
            if request.headers.get("HX-Request"):
                return (
                    "<div class='text-red-600 text-sm'>Acesso restrito a admin Loyall.</div>",
                    403,
                )
            return render_template("403.html"), 403
        return f(*args, **kwargs)

    return wrapped


def _redirect_cliente_para_explorar():
    """Páginas de navegação fora do Explorar (home/lista/detalhe): cliente é
    levado ao próprio Explorar em vez de ver cadastro. Retorna a resposta de
    redirect se for cliente, ou None se for loyall/anônimo (segue o fluxo normal)."""
    user = get_current_user()
    if user is not None and user.papel != PAPEL_LOYALL and user.empresa_id is not None:
        return redirect(url_for("ui.explorar_empresa", empresa_id=user.empresa_id))
    return None


# ── Home ─────────────────────────────────────────────────────────────────


@ui_bp.route("/")
def home():
    if get_current_user() is None:
        return redirect(url_for("ui.login_form"))
    r = _redirect_cliente_para_explorar()  # cliente entra direto no próprio Explorar
    if r:
        return r
    return redirect(url_for("ui.lista_empresas"))


# ── Login / Logout ───────────────────────────────────────────────────────


@ui_bp.route("/login", methods=["GET"])
def login_form():
    if get_current_user() is not None:
        return _redirect_cliente_para_explorar() or redirect(url_for("ui.lista_empresas"))
    return render_template("auth/login.html")


@ui_bp.route("/login", methods=["POST"])
def login_submit():
    email = (request.form.get("email") or "").strip().lower()
    senha = request.form.get("senha") or ""
    if not email or not senha:
        flash("Email e senha são obrigatórios.", "erro")
        return render_template("auth/login.html", email=email), 400

    from datetime import datetime

    with db_session() as session_db:
        user = session_db.query(Usuario).filter_by(email=email).first()
        if user is None or not user.ativo or not verificar_senha(senha, user.senha_hash):
            flash("Credenciais inválidas.", "erro")
            return render_template("auth/login.html", email=email), 401
        user.ultimo_login = datetime.utcnow()
        session_db.flush()
        login_user(user)
    return _redirect_cliente_para_explorar() or redirect(url_for("ui.lista_empresas"))


@ui_bp.route("/logout", methods=["POST"])
def logout_submit():
    logout_user()
    flash("Sessão encerrada.", "ok")
    return redirect(url_for("ui.login_form"))


# ── Empresas ─────────────────────────────────────────────────────────────


@ui_bp.route("/empresas")
def lista_empresas():
    r = _require_login_html()
    if r:
        return r
    # CP-O2: cliente não vê a lista de empresas (cadastro) — vai pro próprio Explorar.
    r = _redirect_cliente_para_explorar()
    if r:
        return r
    user = get_current_user()
    with db_session() as s:
        empresas = s.query(Empresa).order_by(Empresa.nome).all()
        # Detach para uso no template
        for e in empresas:
            s.expunge(e)
    return render_template("empresas/lista.html", empresas=empresas, user=user)


@ui_bp.route("/empresas/nova", methods=["GET", "POST"])
@loyall_required_ui
def empresa_nova():
    r = _require_loyall_html()
    if r:
        return r
    if request.method == "GET":
        return render_template("empresas/nova.html")

    nome = (request.form.get("nome") or "").strip()
    setor = (request.form.get("setor") or "").strip() or None
    site = (request.form.get("site") or "").strip() or None
    if not nome:
        flash("Nome é obrigatório.", "erro")
        return render_template("empresas/nova.html"), 400
    with db_session() as s:
        if s.query(Empresa).filter_by(nome=nome).first():
            flash(f"Empresa '{nome}' já existe.", "erro")
            return render_template("empresas/nova.html"), 409
        e = Empresa(nome=nome, setor=setor, site=site)
        s.add(e)
        s.flush()
        emp_id = e.id
    flash(f"Empresa '{nome}' criada.", "ok")
    return redirect(url_for("ui.detalhe_empresa", empresa_id=emp_id))


@ui_bp.route("/empresas/importar", methods=["GET", "POST"])
@loyall_required_ui
def empresa_importar():
    r = _require_loyall_html()
    if r:
        return r
    if request.method == "GET":
        return render_template("empresas/importar.html")

    import tempfile
    from pathlib import Path

    if "arquivo" not in request.files:
        flash("Arquivo é obrigatório.", "erro")
        return render_template("empresas/importar.html"), 400
    arquivo = request.files["arquivo"]
    if not arquivo.filename:
        flash("Arquivo vazio.", "erro")
        return render_template("empresas/importar.html"), 400

    sobrescrever = request.form.get("sobrescrever") == "on"
    suffix = Path(arquivo.filename).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        arquivo.save(str(tmp_path))
        from src.coletor.excel_cadastro import importar_cadastro

        stats = importar_cadastro(tmp_path, sobrescrever=sobrescrever)
    finally:
        tmp_path.unlink(missing_ok=True)

    if stats.get("erros"):
        return render_template("empresas/importar.html", erros=stats["erros"]), 400
    flash(
        f"Importado: {stats['agrupamentos_criados']} agrupamentos, "
        f"{stats['locais_criados']} locais, {stats['fontes_criadas']} fontes.",
        "ok",
    )
    return redirect(url_for("ui.detalhe_empresa", empresa_id=stats["empresa_id"]))


@ui_bp.route("/importar-verbatins", methods=["GET", "POST"])
@loyall_required_ui
def importar_verbatins():
    """Tela de upload de verbatins (CSAT/pesquisa). GET: form. POST acao=preview:
    detecta colunas sem importar. POST acao=confirmar: importa + dispara pós-coleta."""
    r = _require_loyall_html()
    if r:
        return r

    import tempfile
    from pathlib import Path

    with db_session() as s:
        empresas = [
            SimpleNamespace(id=e.id, nome=e.nome)
            for e in s.query(Empresa).order_by(Empresa.nome).all()
        ]
    if request.method == "GET":
        return render_template("empresas/importar_verbatins.html", empresas=empresas)

    # POST — acao decide preview vs confirmar.
    part = "partials/importar_verbatins_resultado.html"
    acao = request.form.get("acao", "preview")
    empresa_id_raw = request.form.get("empresa_id", "")
    if not empresa_id_raw.isdigit():
        return render_template(part, erro="Selecione a empresa.")
    empresa_id = int(empresa_id_raw)
    arquivo = request.files.get("arquivo")
    if arquivo is None or not arquivo.filename:
        return render_template(part, erro="Selecione um arquivo (.xlsx/.xls/.csv).")

    suffix = Path(arquivo.filename).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        arquivo.save(str(tmp_path))
        if acao == "confirmar":
            from src.coletor.excel import importar_arquivo

            stats = importar_arquivo(tmp_path, empresa_id=empresa_id, disparar_pos=True)
            return render_template(part, stats=stats, empresa_id=empresa_id)
        from src.coletor.excel import prever_arquivo

        preview = prever_arquivo(tmp_path)
        return render_template(
            part, preview=preview, empresa_id=empresa_id, arquivo_nome=arquivo.filename
        )
    except (FileNotFoundError, ValueError) as exc:
        return render_template(part, erro=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)


def _carregar_detalhe_empresa(empresa_id: int):
    """Carrega empresa + estrutura hierárquica + stats para o detalhe.

    CP-B: devolve uma estrutura aninhada agrupamentos→locais→fontes em
    vez de listas paralelas, mais stats agregados para os cards do topo.
    """
    with db_session() as s:
        empresa_db = s.get(Empresa, empresa_id)
        if empresa_db is None:
            return None
        ags_db = (
            s.query(Agrupamento).filter_by(empresa_id=empresa_id).order_by(Agrupamento.nome).all()
        )
        locais_db = s.query(Local).filter_by(empresa_id=empresa_id).order_by(Local.nome).all()
        fontes_db = s.query(Fonte).filter_by(empresa_id=empresa_id).order_by(Fonte.id).all()

        empresa_w = _wrap_empresa(empresa_db, _ultima_coleta(s, empresa_db.id))

        # Indexa fontes por local_id; separa diretas da empresa
        fontes_por_local: dict[int, list] = {}
        fontes_empresa_db = []
        for f in fontes_db:
            if f.entidade_tipo == "local":
                fontes_por_local.setdefault(f.entidade_id, []).append(f)
            else:
                fontes_empresa_db.append(f)

        # Wrap locais com fontes
        locais_w_all = [_wrap_local(loc, fontes_por_local.get(loc.id, [])) for loc in locais_db]
        locais_por_ag: dict[int, list] = {}
        locais_sem_ag: list = []
        for loc_w in locais_w_all:
            if loc_w.agrupamento_id is None:
                locais_sem_ag.append(loc_w)
            else:
                locais_por_ag.setdefault(loc_w.agrupamento_id, []).append(loc_w)

        ags_w = [_wrap_agrupamento(a, locais_por_ag.get(a.id, [])) for a in ags_db]
        fontes_empresa_w = [_wrap_fonte(f) for f in fontes_empresa_db]
        fontes_all_w = [_wrap_fonte(f) for f in fontes_db]

        locais_ativos = sum(1 for loc in locais_w_all if loc.status == "ativo")
        fontes_ativas_n = sum(1 for f in fontes_db if f.ativo)
        fontes_inativas_n = sum(1 for f in fontes_db if not f.ativo)
        stats = {
            "total_agrupamentos": len(ags_w),
            "total_locais": len(locais_w_all),
            "locais_ativos": locais_ativos,
            "total_fontes": len(fontes_db),
            "fontes_ativas": fontes_ativas_n,
            "fontes_inativas": fontes_inativas_n,
        }

    return {
        "empresa": empresa_w,
        "agrupamentos": ags_w,
        "locais": locais_w_all,
        "fontes": fontes_all_w,
        "locais_sem_ag": locais_sem_ag,
        "fontes_empresa": fontes_empresa_w,
        "stats": stats,
    }


@ui_bp.route("/empresas/<int:empresa_id>")
def detalhe_empresa(empresa_id: int):
    r = _require_login_html()
    if r:
        return r
    # CP-O2: detalhe = cadastro (interno). Cliente vai pro próprio Explorar.
    r = _redirect_cliente_para_explorar()
    if r:
        return r
    user = get_current_user()  # aqui só admin_loyall (cliente já redirecionou)
    dados = _carregar_detalhe_empresa(empresa_id)
    if dados is None:
        return render_template("404.html"), 404
    # Mapas auxiliares para o template
    ag_map = {a.id: a.nome for a in dados["agrupamentos"]}
    local_map = {loc.id: loc.nome for loc in dados["locais"]}
    return render_template(
        "empresas/detalhe.html",
        user=user,
        agrupamento_nome=ag_map,
        local_nome=local_map,
        eh_loyall=(user.papel == PAPEL_LOYALL),
        **dados,
    )


# ── Página de verbatins ─────────────────────────────────────────────────


@ui_bp.route("/monitoramento")
@loyall_required_ui
def monitoramento():
    """Página global de monitoramento de coletas (CP-E)."""
    r = _require_login_html()
    if r:
        return r
    user = get_current_user()
    from src.api.monitoramento import listar_coletas as api_listar

    # Reusa o endpoint da API para listar
    resp = api_listar()
    if isinstance(resp, tuple):
        return resp
    body = resp.get_json() or {}
    execucoes_em_andamento = sum(
        1 for e in body.get("execucoes", []) if e.get("status") == "rodando"
    )
    filtros = {
        "status": request.args.get("status", ""),
        "desde_data": request.args.get("desde_data", ""),
    }
    return render_template(
        "monitoramento.html",
        user=user,
        eh_loyall=(user.papel == PAPEL_LOYALL),
        execucoes=body.get("execucoes", []),
        execucoes_em_andamento=execucoes_em_andamento,
        filtros=filtros,
    )


@ui_bp.route("/ui/empresas/<int:empresa_id>/coletas-em-andamento")
@loyall_required_ui
def coletas_em_andamento_redirect(empresa_id: int):
    """Atalho UI -> API JSON usado pelo polling JS na página de detalhe."""
    from src.api.monitoramento import coletas_em_andamento_da_empresa as h

    return h(empresa_id)


@ui_bp.route("/ui/monitoramento/lista")
@loyall_required_ui
def htmx_monitoramento_lista():
    """Fragment HTML da lista — usado pelo polling HTMX de /monitoramento."""
    if get_current_user() is None:
        return ("<div class='text-red-600 text-xs'>Sessão expirada.</div>", 401)
    from src.api.monitoramento import listar_coletas as api_listar

    resp = api_listar()
    if isinstance(resp, tuple):
        return resp
    body = resp.get_json() or {}
    return render_template(
        "partials/monitoramento_lista.html",
        execucoes=body.get("execucoes", []),
    )


@ui_bp.route("/empresas/<int:empresa_id>/verbatins")
def verbatins_empresa(empresa_id: int):
    """Aba Verbatins do Hub Explorar (rota legada preservada → renderiza o shell
    in-place com tab=verbatins, status 200)."""
    return _explorar_render(empresa_id, "verbatins")


def _aba_verbatins(empresa_id, empresa_w):
    """Contexto da aba Verbatins (lista paginada + filtros). Auth e 404 já
    resolvidos pelo shell; ``empresa_w`` vem pronto do _explorar_contexto."""
    # Chama o handler da API e usa o JSON resultante
    from src.api.verbatins import listar_verbatins_da_empresa as api_handler

    resp = api_handler(empresa_id)
    # api_handler retorna Response (200) ou tupla (response, status) em erro →
    # na aba, erro de parâmetro degrada para lista vazia (não derruba o shell).
    api_payload = None if isinstance(resp, tuple) else resp.get_json()
    if api_payload is None:
        api_payload = {"verbatins": [], "total": 0, "pagina": 1, "por_pagina": 20}

    # Filtros lidos da URL
    filtros = {
        "q": request.args.get("q", ""),
        "agrupamento_id": request.args.get("agrupamento_id", ""),
        "local_id": request.args.get("local_id", ""),
        "fonte_id": request.args.get("fonte_id", ""),
        # Multi-select (CP-multiselect): listas (p/ checkbox + contagem no template).
        "subpilar": [s for s in request.args.getlist("subpilar") if s],
        "tipo": [t for t in request.args.getlist("tipo") if t],
        "data_de": request.args.get("data_de", ""),
        "data_ate": request.args.get("data_ate", ""),
        "esconder_rating_only": request.args.get("esconder_rating_only", ""),
        "tema_id": request.args.get("tema_id", ""),
        "sem_classificacao": request.args.get("sem_classificacao", ""),
        "origem": request.args.get("origem", ""),
        "periodo": request.args.get("periodo", ""),
        "pagina": api_payload["pagina"],
        "por_pagina": api_payload["por_pagina"],
    }

    # Listas de filtros (agrupamentos/locais/fontes da empresa)
    with db_session() as s:
        ags = s.query(Agrupamento).filter_by(empresa_id=empresa_id).order_by(Agrupamento.nome).all()
        locs = s.query(Local).filter_by(empresa_id=empresa_id).order_by(Local.nome).all()
        agrupamentos = [SimpleNamespace(id=a.id, nome=a.nome) for a in ags]
        locais = [SimpleNamespace(id=loc.id, nome=loc.nome) for loc in locs]
        fontes_ = _fontes_para_filtro(s, empresa_id)
        # B6 CP-5: temas ativos da empresa, com volume, pra select no UI
        from sqlalchemy import func as _func

        from src.models.temas import Tema, VerbatimTema

        temas_rows = (
            s.query(Tema, _func.count(VerbatimTema.id).label("vol"))
            .outerjoin(VerbatimTema, VerbatimTema.tema_id == Tema.id)
            .filter(Tema.empresa_id == empresa_id, Tema.ativo.is_(True))
            .group_by(Tema.id)
            .order_by(_func.count(VerbatimTema.id).desc(), Tema.nome.asc())
            .all()
        )
        temas_filtro = [
            SimpleNamespace(id=t.id, nome=t.nome, volume=int(vol or 0))
            for (t, vol) in temas_rows
            if (vol or 0) > 0  # só temas com pelo menos 1 vínculo
        ]

    # Paginação: query strings para próxima/anterior preservando filtros
    from urllib.parse import urlencode

    def _qs(pagina):
        # doseq=True → listas viram params repetidos (?subpilar=P1&subpilar=D2);
        # exclui [] (subpilar/tipo vazios) além de ""/None.
        params = {k: v for k, v in filtros.items() if v not in ("", None, []) and k != "pagina"}
        params["pagina"] = pagina
        return urlencode(params, doseq=True)

    total = api_payload["total"]
    por_pagina = api_payload["por_pagina"]
    total_paginas = max(1, (total + por_pagina - 1) // por_pagina)

    # Link de "voltar" contextual: se chegou via Painel (origem=painel),
    # volta pro Painel preservando filtros espaciais; senão, volta pra empresa.
    if filtros["origem"] == "painel":
        painel_kwargs = {"empresa_id": empresa_id}
        for k in ("periodo", "agrupamento_id", "local_id", "fonte_id"):
            if filtros.get(k):
                painel_kwargs[k] = filtros[k]
        voltar_url = url_for("ui.painel_empresa", **painel_kwargs)
        voltar_texto = "Painel"
    else:
        voltar_url = url_for("ui.detalhe_empresa", empresa_id=empresa_id)
        voltar_texto = empresa_w.nome

    return {
        "verbatins": api_payload["verbatins"],
        "total": total,
        "total_paginas": total_paginas,
        "agrupamentos": agrupamentos,
        "locais": locais,
        "fontes": fontes_,
        "temas": temas_filtro,
        "filtros": filtros,
        "subpilares": sorted(SUBPILARES_VALIDOS),
        "tipos": sorted(TIPOS_VALIDOS),
        "pag_qs_anterior": _qs(filtros["pagina"] - 1),
        "pag_qs_proxima": _qs(filtros["pagina"] + 1),
        "voltar_url": voltar_url,
        "voltar_texto": voltar_texto,
    }


@ui_bp.route("/empresas/<int:empresa_id>/painel")
def painel_empresa(empresa_id: int):
    """Aba Painel do Hub Explorar (rota legada preservada → shell in-place)."""
    return _explorar_render(empresa_id, "painel")


def _aba_painel(empresa_id, empresa_w):
    """Contexto da aba Painel Executivo. Retorna None em erro dos endpoints
    (→ 404 no shell)."""
    # Chama os 2 endpoints do painel via handler interno (zero HTTP overhead)
    from src.api.painel import painel_nivel1 as h_n1
    from src.api.painel import painel_nivel2 as h_n2

    resp_n1 = h_n1(empresa_id)
    resp_n2 = h_n2(empresa_id)
    if isinstance(resp_n1, tuple) or isinstance(resp_n2, tuple):
        return None
    n1 = resp_n1.get_json()
    n2 = resp_n2.get_json()
    if n1 is None or n2 is None:
        return None

    # Filtros lidos da URL (eco para o front; mesmos do n1/n2)
    filtros = {
        "agrupamento_id": request.args.get("agrupamento_id", ""),
        "local_id": request.args.get("local_id", ""),
        "fonte_id": request.args.get("fonte_id", ""),
        "periodo": request.args.get("periodo", ""),
    }

    # ── Governança (CP-LG-4, leitura): Proximity do escopo + Previsibilidade da
    # loja (LG-2, CV temporal). No escopo loja a Previsibilidade composta de
    # empresa é degenerada (var_locais=0) — por isso trocamos a FONTE do card.
    from src.governanca.leitura import (
        escopo_de_filtros,
        garantir_governanca,
        gini_escopo,
        previsibilidade_loja,
        proximity_escopo,
        selo_de_loja,
    )

    garantir_governanca(empresa_id)
    escopo_tipo, escopo_id = escopo_de_filtros(filtros["agrupamento_id"], filtros["local_id"])

    with db_session() as s:
        proximity = proximity_escopo(s, empresa_id, escopo_tipo, escopo_id)
        if escopo_tipo == "loja":
            pv = previsibilidade_loja(s, empresa_id, escopo_id)
            previsib = {"valor": pv["valor"], "faixa": pv["faixa"], "fonte": "loja"}
        else:
            previsib = {"valor": n1.get("previsibilidade"), "faixa": None, "fonte": "empresa"}
        # Gini (CP-LG-3) só existe p/ empresa/agrupamento — N/A em loja única.
        gini = gini_escopo(s, empresa_id, escopo_tipo, escopo_id) if escopo_tipo != "loja" else None
        # Selo de excelência (CP-LG-6) — só no escopo loja.
        selo = selo_de_loja(s, empresa_id, escopo_id) if escopo_tipo == "loja" else None
        ags = s.query(Agrupamento).filter_by(empresa_id=empresa_id).order_by(Agrupamento.nome).all()
        locs = s.query(Local).filter_by(empresa_id=empresa_id).order_by(Local.nome).all()
        agrupamentos = [SimpleNamespace(id=a.id, nome=a.nome) for a in ags]
        locais = [SimpleNamespace(id=loc.id, nome=loc.nome) for loc in locs]
        fontes_ = _fontes_para_filtro(s, empresa_id)
        anomalias_resumo = _resumo_anomalias(s, empresa_id)

    # B6.6 CP-5: a seção "Temas transversais" saiu do painel — vive na aba Temas.
    return {
        "n1": n1,
        "n2": n2,
        "filtros": filtros,
        "agrupamentos": agrupamentos,
        "locais": locais,
        "fontes": fontes_,
        "anomalias_resumo": anomalias_resumo,
        "escopo_tipo": escopo_tipo,
        "proximity": proximity,
        "previsib": previsib,
        "gini": gini,
        "selo": selo,
    }


def _labels_no_agrupamento(s, empresa_id, agrupamento_id):
    """Conjunto de tema.nome com ≥1 vínculo Caminho A naquele agrupamento.

    bucket_chave = ``"<agrupamento_id>:<subpilar>:<tipo>"`` → prefixo ``"ag:"``.
    """
    from src.models.temas import Tema, VerbatimTema

    rows = (
        s.query(Tema.nome)
        .join(VerbatimTema, VerbatimTema.tema_id == Tema.id)
        .filter(
            Tema.empresa_id == empresa_id,
            VerbatimTema.bucket_chave.like(f"{agrupamento_id}:%"),
        )
        .distinct()
        .all()
    )
    return {r[0] for r in rows}


def _quartis(valores):
    """(P25, P50, P75) por interpolação linear. Listas pequenas → ok."""
    s = sorted(valores)
    if not s:
        return (0.0, 0.0, 0.0)
    if len(s) == 1:
        return (s[0], s[0], s[0])

    def pct(p):
        k = (len(s) - 1) * p
        f = int(k)
        c = min(f + 1, len(s) - 1)
        return s[f] + (s[c] - s[f]) * (k - f)

    return pct(0.25), pct(0.50), pct(0.75)


def _abrangencia(peso, t25, t50, t75):
    """Rótulo qualitativo do peso por quartil (decisão B6.6 CP-5.3)."""
    if peso >= t75:
        return "muito alta"
    if peso >= t50:
        return "alta"
    if peso >= t25:
        return "média"
    return "baixa"


def _carregar_transversais(s, empresa_id, agrupamento_id=None, limite=10):
    """Cruzamentos N4 (top por peso) + a ação N5 de cada um (Bloco 7 CP-5/6).

    Os cruzamentos são company-wide (agrupamento_id NULL, buckets subpilar:tipo).
    Quando ``agrupamento_id`` é fornecido, filtra por **pertinência**: mantém só
    os cruzamentos cujos temas-membros têm vínculo nesse agrupamento.
    """
    from src.models.temas import AcaoVenda, TemaCruzamento

    crz = (
        s.query(TemaCruzamento)
        .filter(TemaCruzamento.empresa_id == empresa_id)
        .order_by(TemaCruzamento.peso.desc())
        .all()
    )
    # Quartis sobre TODOS os pesos da empresa (antes do filtro de agrupamento).
    t25, t50, t75 = _quartis([cr.peso for cr in crz])
    if agrupamento_id is not None:
        labels_ag = _labels_no_agrupamento(s, empresa_id, agrupamento_id)
        crz = [
            cr
            for cr in crz
            if (set([cr.tema_label]) | set(json.loads(cr.membros_json) if cr.membros_json else []))
            & labels_ag
        ]
    crz = crz[:limite]
    acoes = {
        a.cruzamento_id: a
        for a in s.query(AcaoVenda)
        .filter(AcaoVenda.empresa_id == empresa_id, AcaoVenda.cruzamento_id.isnot(None))
        .all()
    }
    out = []
    for cr in crz:
        acao = acoes.get(cr.id)
        out.append(
            SimpleNamespace(
                tema_label=cr.tema_label,
                buckets=json.loads(cr.buckets_envolvidos_json or "[]"),
                tipos=json.loads(cr.tipos_envolvidos_json or "[]"),
                n_subpilares=cr.n_subpilares_distintos or 0,
                peso=cr.peso,
                abrangencia=_abrangencia(cr.peso, t25, t50, t75),
                eh_semantico=bool(cr.membros_json),
                membros=json.loads(cr.membros_json) if cr.membros_json else None,
                acao=(
                    SimpleNamespace(texto=acao.acao_texto, impacto=acao.impacto_qualitativo)
                    if acao
                    else None
                ),
            )
        )
    return out


# ── B6.6 CP-5: tela dedicada de temas ─────────────────────────────────


def _montar_mapa_lastro(n1, n2):
    """Mapa de Lastro: 4 pilares (ratio+faixa) com seus subpilares + gargalo.

    Reusa os dados de painel_nivel1 (pilares) e painel_nivel2 (matriz de
    subpilares). Gargalo = pilar de menor ratio entre os com volume > 0.
    """
    from src.api.painel import PILARES_ORDEM

    pilares = {p["pilar"]: p for p in n1.get("pilares", [])}
    subs_por_pilar = {}
    for cell in n2.get("matriz", []):
        subs_por_pilar.setdefault(cell["pilar"], []).append(cell)
    candidatos = [(p["pilar"], p["ratio"]) for p in n1.get("pilares", []) if p.get("total", 0) > 0]
    gargalo = min(candidatos, key=lambda x: x[1])[0] if candidatos else None

    mapa = []
    for pid in PILARES_ORDEM:
        p = pilares.get(pid)
        if not p:
            continue
        mapa.append(
            {
                "pilar": pid,
                "nome": p["nome"],
                "ratio": p["ratio"],
                "faixa": p["faixa"],
                "total": p["total"],
                "promotor": p.get("promotor", 0),
                "conversivel": p.get("conversivel", 0),
                "detrator": p.get("detrator", 0),
                "gargalo": pid == gargalo,
                "subpilares": subs_por_pilar.get(pid, []),
            }
        )
    return mapa, gargalo


def _top_temas_por_subpilar(s, empresa_id, agrupamento_id=None, top=5):
    """Top N temas de cada subpilar (de temas_cache), com split por tipo e
    2-3 exemplos de verbatim (2 queries batched — sem N+1).

    Returns lista por subpilar (ordem canônica) com
    ``{subpilar, nome, temas:[{label, tema_id, total, promotor, conversivel,
    detrator, exemplos:[texto_curto, ...]}]}``.
    """
    from sqlalchemy import and_, func

    from src.api.painel import NOME_SUBPILAR, SUBPILARES_ORDEM
    from src.models.temas import Tema, TemaCache
    from src.utils.sql import group_concat

    q = (
        s.query(
            TemaCache.subpilar,
            TemaCache.tema_label,
            TemaCache.tipo,
            func.sum(TemaCache.volume).label("vol"),
            group_concat(TemaCache.exemplos_verbatim_ids, "|").label("ex_blobs"),
            Tema.id.label("tema_id"),
        )
        .join(
            Tema,
            and_(
                Tema.empresa_id == TemaCache.empresa_id,
                Tema.nome == TemaCache.tema_label,
                Tema.ativo.is_(True),
            ),
        )
        .filter(TemaCache.empresa_id == empresa_id)
    )
    if agrupamento_id is not None:
        q = q.filter(TemaCache.agrupamento_id == agrupamento_id)
    q = q.group_by(TemaCache.subpilar, TemaCache.tema_label, TemaCache.tipo, Tema.id)

    # Agrega por (subpilar, label): total + split por tipo + ids de exemplo.
    agg = {}
    for sub, label, tipo, vol, ex_blobs, tema_id in q.all():
        key = (sub, label)
        e = agg.setdefault(
            key,
            {
                "label": label,
                "tema_id": tema_id,
                "total": 0,
                "promotor": 0,
                "conversivel": 0,
                "detrator": 0,
                "ex_ids": [],
            },
        )
        e["total"] += int(vol or 0)
        if tipo in ("promotor", "conversivel", "detrator"):
            e[tipo] += int(vol or 0)
        for blob in (ex_blobs or "").split("|"):
            blob = blob.strip()
            if not blob:
                continue
            try:
                for vid in json.loads(blob):
                    if vid not in e["ex_ids"]:
                        e["ex_ids"].append(vid)
            except (ValueError, TypeError):
                continue

    por_sub = {}
    for (sub, _label), e in agg.items():
        por_sub.setdefault(sub, []).append(e)

    out = []
    todos_ids = set()
    for sp in SUBPILARES_ORDEM:
        temas = sorted(por_sub.get(sp, []), key=lambda x: -x["total"])[:top]
        for t in temas:
            t["ex_ids"] = t["ex_ids"][:3]
            todos_ids.update(t["ex_ids"])
        if temas:
            out.append({"subpilar": sp, "nome": NOME_SUBPILAR[sp], "temas": temas})

    # Batched: textos dos exemplos.
    textos = {}
    if todos_ids:
        for vid, texto in (
            s.query(Verbatim.id, Verbatim.texto).filter(Verbatim.id.in_(todos_ids)).all()
        ):
            textos[vid] = texto or ""
    for bloco in out:
        for t in bloco["temas"]:
            t["exemplos"] = [textos.get(vid, "")[:140] for vid in t["ex_ids"] if textos.get(vid)]
    return out


@ui_bp.route("/empresas/<int:empresa_id>/temas")
def temas_empresa(empresa_id: int):
    """Aba Temas do Hub Explorar (rota legada preservada → shell in-place)."""
    return _explorar_render(empresa_id, "temas")


def _aba_temas(empresa_id, empresa_w):
    """Contexto da aba Temas: Mapa de Lastro + cruzamentos transversais (N4) +
    ações (N5) + top temas por subpilar. Retorna None em erro (→ 404)."""
    from sqlalchemy import distinct, func

    from src.api.painel import painel_nivel1 as h_n1
    from src.api.painel import painel_nivel2 as h_n2
    from src.models.temas import AcaoVenda, Tema, TemaCruzamento, VerbatimTema
    from src.temas.janela import data_corte, get_janela_dias

    resp1 = h_n1(empresa_id)
    resp2 = h_n2(empresa_id)
    if isinstance(resp1, tuple) or isinstance(resp2, tuple):
        return None
    n1 = resp1.get_json()
    n2 = resp2.get_json()
    if n1 is None or n2 is None:
        return None

    filtros = {"agrupamento_id": request.args.get("agrupamento_id", "")}
    ag_filtro = int(filtros["agrupamento_id"]) if filtros["agrupamento_id"].isdigit() else None

    with db_session() as s:
        ags = s.query(Agrupamento).filter_by(empresa_id=empresa_id).order_by(Agrupamento.nome).all()
        agrupamentos = [SimpleNamespace(id=a.id, nome=a.nome) for a in ags]
        ag_filtro_nome = next((a.nome for a in agrupamentos if a.id == ag_filtro), None)
        transversais = _carregar_transversais(s, empresa_id, agrupamento_id=ag_filtro)
        top_subpilar = _top_temas_por_subpilar(s, empresa_id, ag_filtro)
        corte = data_corte(empresa_id, s)
        n_temas = (
            s.query(func.count(distinct(Tema.id)))
            .join(VerbatimTema, VerbatimTema.tema_id == Tema.id)
            .filter(Tema.empresa_id == empresa_id, Tema.ativo.is_(True))
            .scalar()
        )
        n_cruz = (
            s.query(func.count(TemaCruzamento.id))
            .filter(TemaCruzamento.empresa_id == empresa_id)
            .scalar()
        )
        n_acoes = (
            s.query(func.count(AcaoVenda.id)).filter(AcaoVenda.empresa_id == empresa_id).scalar()
        )
        # selo de anomalia: temas (por id) e cruzamentos (por label) com anomalia
        from src.models.anomalia import AnomaliaDetectada

        anoms = (
            s.query(AnomaliaDetectada.tipo, AnomaliaDetectada.tema_id, AnomaliaDetectada.chave)
            .filter(AnomaliaDetectada.empresa_id == empresa_id)
            .all()
        )
        temas_em_anomalia = {tid for tp, tid, _ in anoms if tp == "tema" and tid}
        cruzamentos_em_anomalia = {
            ch.split(":", 1)[1].strip()
            for tp, _, ch in anoms
            if tp == "cruzamento" and ch and ":" in ch
        }

    mapa_lastro, gargalo = _montar_mapa_lastro(n1, n2)

    return {
        "n1": n1,
        "mapa_lastro": mapa_lastro,
        "gargalo_pilar": gargalo,
        "transversais": transversais,
        "agrupamento_filtrado": ag_filtro_nome,
        "top_subpilar": top_subpilar,
        "totais": {"temas": n_temas, "cruzamentos": n_cruz, "acoes": n_acoes},
        "temas_em_anomalia": temas_em_anomalia,
        "cruzamentos_em_anomalia": cruzamentos_em_anomalia,
        "janela_dias": get_janela_dias(),
        "data_corte": corte,
        "filtros": filtros,
        "agrupamentos": agrupamentos,
    }


# ── Monitoramento ML CP-6: tela de anomalias ──────────────────────────

_SEV_RANK_UI = {"critico": 2, "atencao": 1, "normal": 0}


def _anomalia_view(a, local_nome=None, tema_nome=None):
    """Converte uma AnomaliaDetectada em objeto de exibição p/ o template.
    ``leitura`` vira dict (7 seções) quando o JSON parseia; senão, texto cru."""
    import json as _json

    corrob = bool(a.tendencia and "corroborado por tema" in a.tendencia)
    leitura = a.leitura_editorial
    if leitura:
        try:
            parsed = _json.loads(leitura)
            if isinstance(parsed, dict):
                leitura = parsed
        except (ValueError, TypeError):
            pass
    # Resumo curto p/ o card colapsado: 1ª frase do o_que (ou a tendência).
    if isinstance(leitura, dict) and leitura.get("o_que"):
        resumo = leitura["o_que"].split(". ")[0].rstrip(".") + "."
    else:
        resumo = a.tendencia or "Leitura editorial ainda não gerada."
    resumo = resumo[:180]
    # CP-UX-b: título legível p/ o header. Anomalia de indicador tem local_id →
    # "Nome da loja · subpilar" (o nome substitui o "loja XX" cru da chave). Tema/
    # cruzamento não têm local → mantém a chave (já descritiva). Lógica aqui (não
    # no template) p/ centralizar a regra. $0 — local_nome já vem do lookup batch.
    if local_nome:
        titulo = f"{local_nome} · {a.subpilar}" if a.subpilar else local_nome
    else:
        titulo = a.chave
    return SimpleNamespace(
        id=a.id,
        tipo=a.tipo,
        chave=a.chave,
        titulo=titulo,
        severidade=a.severidade,
        score=a.score_final,
        score_temporal=a.score_temporal,
        score_cross=a.score_cross_sectional,
        magnitude=a.magnitude,
        direcao=a.direcao,
        tendencia=a.tendencia,
        subpilar=a.subpilar,
        periodo=a.periodo,
        local_nome=local_nome,
        tema_nome=tema_nome,
        leitura=leitura,
        resumo=resumo,
        estado=a.estado_validacao or "pendente",
        nota=a.nota_editorial,
        corroborado=corrob,
    )


def _resumo_anomalias(s, empresa_id):
    """Contagens gerais (sem filtro) p/ badge no header e card sumário."""
    from src.models.anomalia import AnomaliaDetectada

    base = s.query(AnomaliaDetectada).filter(AnomaliaDetectada.empresa_id == empresa_id).all()
    return {
        "total": len(base),
        "critico": sum(1 for a in base if a.severidade == "critico"),
        "atencao": sum(1 for a in base if a.severidade == "atencao"),
        "pendentes": sum(1 for a in base if (a.estado_validacao or "pendente") == "pendente"),
        "confirmados": sum(1 for a in base if a.estado_validacao == "confirmado"),
    }


def _carregar_anomalias(s, empresa_id, filtros=None):
    from src.models.anomalia import AnomaliaDetectada
    from src.models.local import Local
    from src.models.temas import Tema

    filtros = filtros or {}
    q = s.query(AnomaliaDetectada).filter(AnomaliaDetectada.empresa_id == empresa_id)
    if filtros.get("severidade"):
        q = q.filter(AnomaliaDetectada.severidade == filtros["severidade"])
    if filtros.get("tipo"):
        q = q.filter(AnomaliaDetectada.tipo == filtros["tipo"])
    if filtros.get("estado"):
        q = q.filter(AnomaliaDetectada.estado_validacao == filtros["estado"])
    rows = q.all()

    local_ids = {a.local_id for a in rows if a.local_id}
    tema_ids = {a.tema_id for a in rows if a.tema_id}
    locais = (
        {x.id: x.nome for x in s.query(Local).filter(Local.id.in_(local_ids)).all()}
        if local_ids
        else {}
    )
    temas = (
        {t.id: t.nome for t in s.query(Tema).filter(Tema.id.in_(tema_ids)).all()}
        if tema_ids
        else {}
    )
    dicts = [_anomalia_view(a, locais.get(a.local_id), temas.get(a.tema_id)) for a in rows]
    dicts.sort(key=lambda a: (-_SEV_RANK_UI.get(a.severidade, 0), -(a.score or 0)))
    return dicts


@ui_bp.route("/empresas/<int:empresa_id>/anomalias")
def anomalias_empresa(empresa_id: int):
    """Aba Anomalias do Hub Explorar (rota legada preservada → shell in-place)."""
    return _explorar_render(empresa_id, "anomalias")


def _aba_anomalias(empresa_id, empresa_w):
    """Contexto da aba Monitoramento ML: anomalias detectadas com filtros,
    leitura editorial, drill-down e validação editorial."""
    filtros = {
        "severidade": request.args.get("severidade", ""),
        "tipo": request.args.get("tipo", ""),
        "estado": request.args.get("estado", ""),
    }
    with db_session() as s:
        anomalias = _carregar_anomalias(s, empresa_id, filtros)
        resumo = _resumo_anomalias(s, empresa_id)

    return {
        "anomalias": anomalias,
        "resumo": resumo,
        "filtros": filtros,
    }


# ── Relatórios (Bloco 9 Evolução B) ──────────────────────────────────────────
_RELATORIOS = [
    (
        "resumo_executivo",
        "Resumo Executivo Geral",
        "Overview C-level: índice + engajamento + gargalo + 2 frentes + top achados.",
        "B1",
        "disponivel",
    ),
    (
        "diagnostico_pontual",
        "Diagnóstico Pontual",
        "Foto técnica atual: Mapa de Lastro + Confronto + 12 leituras + indicadores.",
        "B2",
        "disponivel",
    ),
    (
        "plano_executivo",
        "Plano de Ação Executivo",
        "161 ações priorizadas por perspectiva (reativas + estruturais).",
        "B3",
        "disponivel",
    ),
    (
        "diagnostico_longitudinal",
        "Diagnóstico Longitudinal",
        "Narrativa quarterly: ratios por período, tendências e inércia estrutural.",
        "B4",
        "disponivel",
    ),
    (
        "painel_governanca",
        "Painel de Governança",
        "Visão Board: saúde consolidada, concentração, previsibilidade, selos e simulação.",
        "B5",
        "disponivel",
    ),
]
_RELATORIOS_DICT = {t[0]: t for t in _RELATORIOS}


def _pdf_disponivel() -> bool:
    """Detecta se as libs nativas do WeasyPrint estão presentes (sem renderizar)."""
    try:
        import weasyprint  # noqa: F401
        from weasyprint import HTML

        HTML(string="<p>x</p>").write_pdf()
        return True
    except Exception:  # noqa: BLE001 — qualquer falha → indisponível
        return False


@ui_bp.route("/empresas/<int:empresa_id>/relatorios")
def relatorios_index(empresa_id: int):
    """Aba Relatórios do Hub Explorar (rota legada preservada → shell in-place)."""
    return _explorar_render(empresa_id, "relatorios")


def _aba_relatorios(empresa_id, empresa_w):
    """Contexto da aba Relatórios — 4 cards (Resumo Executivo, Diagnóstico
    Pontual, Plano Executivo, Diagnóstico Longitudinal)."""
    relatorios = [
        SimpleNamespace(tipo=t, titulo=titulo, descricao=desc, cp=cp, status=st)
        for t, titulo, desc, cp, st in _RELATORIOS
    ]
    return {
        "relatorios": relatorios,
        "pdf_disponivel": _pdf_disponivel(),
    }


# Builders das abas migradas → consumidos por _explorar_contexto. Cada um recebe
# (empresa_id, empresa_w) e devolve o dict de variáveis específico da aba (sem
# empresa/eh_loyall/user, que o shell já injeta), ou None em erro de dados.
_ABA_BUILDERS = {
    "verbatins": _aba_verbatins,
    "painel": _aba_painel,
    "temas": _aba_temas,
    "anomalias": _aba_anomalias,
    "relatorios": _aba_relatorios,
}


def _relatorio_html(empresa_w, tipo: str) -> str:
    """Dispatch do HTML por tipo de relatório. Cada CP B1-B4 preenche o seu."""
    from datetime import datetime

    meta = _RELATORIOS_DICT.get(tipo)
    if meta is None:
        return None
    _, titulo, _, cp, _ = meta
    if tipo == "resumo_executivo":
        from src.relatorios.resumo_executivo import montar_dados

        d = montar_dados(empresa_w.id)
        return render_template(
            "relatorios/resumo_executivo.html",
            empresa=empresa_w,
            gerado_em=d.get("gerado_em") or datetime.utcnow(),
            escopo_label=None,
            d=d,
        )
    if tipo == "diagnostico_pontual":
        from src.relatorios.diagnostico_pontual import montar_dados as _mdp

        d = _mdp(empresa_w.id)
        return render_template(
            "relatorios/diagnostico_pontual.html",
            empresa=empresa_w,
            gerado_em=d.get("gerado_em") or datetime.utcnow(),
            escopo_label=None,
            d=d,
        )
    if tipo == "plano_executivo":
        from src.relatorios.plano_executivo import montar_dados as _mpe

        d = _mpe(empresa_w.id)
        return render_template(
            "relatorios/plano_executivo.html",
            empresa=empresa_w,
            gerado_em=d.get("gerado_em") or datetime.utcnow(),
            escopo_label=None,
            d=d,
        )
    if tipo == "diagnostico_longitudinal":
        from src.relatorios.diagnostico_longitudinal import montar_dados as _mdl

        d = _mdl(empresa_w.id)
        return render_template(
            "relatorios/diagnostico_longitudinal.html",
            empresa=empresa_w,
            gerado_em=d.get("gerado_em") or datetime.utcnow(),
            escopo_label=None,
            d=d,
        )
    if tipo == "painel_governanca":
        from src.relatorios.painel_governanca import montar_dados as _mpg

        d = _mpg(empresa_w.id)
        return render_template(
            "relatorios/painel_governanca.html",
            empresa=empresa_w,
            gerado_em=d.get("gerado_em") or datetime.utcnow(),
            escopo_label=None,
            d=d,
        )
    return render_template(
        "relatorios/em_construcao.html",
        empresa=empresa_w,
        gerado_em=datetime.utcnow(),
        escopo_label=None,
        titulo=titulo,
        cp=cp,
    )


@ui_bp.route("/empresas/<int:empresa_id>/relatorios/<tipo>")
def relatorios_view(empresa_id: int, tipo: str):
    """Tela do relatório (HTML — funciona sempre, sem deps nativas)."""
    r = _require_login_html()
    if r:
        return r
    user = get_current_user()
    if user.papel != PAPEL_LOYALL and user.empresa_id != empresa_id:
        return render_template("403.html"), 403
    if tipo not in _RELATORIOS_DICT:
        return render_template("404.html"), 404
    with db_session() as s:
        empresa_db = s.get(Empresa, empresa_id)
        if empresa_db is None:
            return render_template("404.html"), 404
        empresa_w = _wrap_empresa(empresa_db, _ultima_coleta(s, empresa_id))
    html = _relatorio_html(empresa_w, tipo)
    return html


@ui_bp.route("/empresas/<int:empresa_id>/relatorios/<tipo>.pdf")
def relatorios_pdf(empresa_id: int, tipo: str):
    """Download PDF (WeasyPrint). 503 com instrução se libs nativas ausentes."""
    from flask import Response

    r = _require_login_html()
    if r:
        return r
    user = get_current_user()
    if user.papel != PAPEL_LOYALL and user.empresa_id != empresa_id:
        return render_template("403.html"), 403
    if tipo not in _RELATORIOS_DICT:
        return render_template("404.html"), 404
    with db_session() as s:
        empresa_db = s.get(Empresa, empresa_id)
        if empresa_db is None:
            return render_template("404.html"), 404
        empresa_w = _wrap_empresa(empresa_db, _ultima_coleta(s, empresa_id))
    html = _relatorio_html(empresa_w, tipo)
    from src.relatorios.pdf import PdfIndisponivel, render_pdf

    try:
        pdf_bytes = render_pdf(html)
    except PdfIndisponivel as exc:
        return Response(str(exc), status=503, mimetype="text/plain; charset=utf-8")
    nome = f"PDPA_{tipo}_{empresa_w.nome.replace(' ', '_')}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@ui_bp.route("/ui/empresas/<int:empresa_id>/anomalias/<int:anomalia_id>/validar", methods=["POST"])
def anomalia_validar_ui(empresa_id: int, anomalia_id: int):
    """HTMX: valida a anomalia e devolve o card atualizado (swap outerHTML)."""
    r = _require_login_html()
    if r:
        return r
    user = get_current_user()
    if user.papel != PAPEL_LOYALL and user.empresa_id != empresa_id:
        return render_template("403.html"), 403

    from src.api.anomalias import aplicar_validacao
    from src.models.anomalia import AnomaliaDetectada
    from src.models.local import Local
    from src.models.temas import Tema

    estado = request.form.get("estado")
    nota = request.form.get("nota")
    _, erro = aplicar_validacao(empresa_id, anomalia_id, estado, nota)
    if erro:
        return ("", erro)

    with db_session() as s:
        a = s.get(AnomaliaDetectada, anomalia_id)
        local_nome = s.get(Local, a.local_id).nome if a.local_id else None
        tema_nome = s.get(Tema, a.tema_id).nome if a.tema_id else None
        av = _anomalia_view(a, local_nome, tema_nome)
    return render_template(
        "partials/anomalia_card.html",
        a=av,
        empresa_id=empresa_id,
        eh_loyall=(user.papel == PAPEL_LOYALL),
    )


# ── B6 CP-5: Modal de temas + tela admin do catálogo ──────────────────


@ui_bp.route("/ui/empresas/<int:empresa_id>/painel/temas-modal", methods=["GET"])
def painel_temas_modal(empresa_id: int):
    """HTMX modal lateral com top temas de um bucket subpilar × tipo."""
    r = _require_login_html()
    if r:
        return r
    user = get_current_user()
    if user.papel != PAPEL_LOYALL and user.empresa_id != empresa_id:
        return render_template("403.html"), 403

    from src.api.temas import painel_temas as api_handler

    resp = api_handler(empresa_id)
    if isinstance(resp, tuple):
        return resp
    body = resp.get_json()
    # Resolve o nome do agrupamento filtrado (se houver) p/ exibir no modal.
    agrupamento_nome = None
    if body.get("agrupamento_id"):
        with db_session() as s:
            ag = s.get(Agrupamento, body["agrupamento_id"])
            agrupamento_nome = ag.nome if ag else None
    return render_template(
        "partials/painel_temas_modal.html",
        empresa_id=empresa_id,
        subpilar=body.get("subpilar"),
        tipo=body.get("tipo"),
        agrupamento_nome=agrupamento_nome,
        temas=body.get("temas", []),
    )


@ui_bp.route("/admin/temas/<int:empresa_id>", methods=["GET"])
@loyall_required_ui
def admin_temas(empresa_id: int):
    """Tela admin do catálogo de temas (loyall only)."""
    r = _require_login_html()
    if r:
        return r
    user = get_current_user()
    if user.papel != PAPEL_LOYALL:
        return render_template("403.html"), 403

    from src.api.temas import listar_temas_da_empresa as h

    resp = h(empresa_id)
    if isinstance(resp, tuple):
        return resp
    body = resp.get_json()

    with db_session() as s:
        empresa_db = s.get(Empresa, empresa_id)
        if empresa_db is None:
            return render_template("404.html"), 404
        empresa_w = _wrap_empresa(empresa_db, _ultima_coleta(s, empresa_db.id))

    return render_template(
        "admin/temas.html",
        empresa=empresa_w,
        temas=body.get("temas", []),
        filtros={
            "q": request.args.get("q", ""),
            "incluir_inativos": request.args.get("incluir_inativos", ""),
        },
        eh_loyall=True,
        user=user,
    )


def _carregar_verbatim_para_template(verbatim_id: int):
    """Devolve dict (estilo serializer da API) + historico, ambos seguros."""
    from src.api.verbatins import _serialize_reclassificacao, _serialize_verbatim

    with db_session() as s:
        v_db = s.get(Verbatim, verbatim_id)
        if v_db is None:
            return None, None
        empresa_id = v_db.empresa_id
        fonte = s.get(Fonte, v_db.fonte_id)
        local = s.get(Local, v_db.local_id) if v_db.local_id else None
        ag = s.get(Agrupamento, local.agrupamento_id) if local and local.agrupamento_id else None
        fonte_map = {
            v_db.fonte_id: {
                "conector_tipo": fonte.conector_tipo if fonte else None,
                "url": fonte.url if fonte else None,
                "agrupamento_id_via_local": local.agrupamento_id if local else None,
            }
        }
        local_map = {local.id: local.nome} if local else {}
        ag_map = {ag.id: ag.nome} if ag else {}
        v_dict = _serialize_verbatim(v_db, ag_map, local_map, fonte_map)
        historico_db = (
            s.query(VerbatimReclassificacao)
            .filter_by(verbatim_id=verbatim_id)
            .order_by(VerbatimReclassificacao.reclassificado_em.desc())
            .all()
        )
        historico = [_serialize_reclassificacao(r) for r in historico_db]
    return v_dict, empresa_id, historico


@ui_bp.route("/ui/verbatins/<int:verbatim_id>/detalhes", methods=["GET"])
def htmx_verbatim_detalhes(verbatim_id: int):
    """Modal de detalhes (HTMX)."""
    info = _carregar_verbatim_para_template(verbatim_id)
    if info is None or info[0] is None:
        return ("<div class='text-red-600'>Verbatim não encontrado.</div>", 404)
    v_dict, empresa_id, historico = info
    erro = _check_acesso(empresa_id)
    if erro:
        return erro
    return render_template("partials/verbatim_detalhes_modal.html", v=v_dict, historico=historico)


@ui_bp.route("/ui/verbatins/<int:verbatim_id>/reclassificar", methods=["GET"])
def htmx_reclassificar_modal(verbatim_id: int):
    """Modal de reclassificação (HTMX)."""
    info = _carregar_verbatim_para_template(verbatim_id)
    if info is None or info[0] is None:
        return ("<div class='text-red-600'>Verbatim não encontrado.</div>", 404)
    v_dict, empresa_id, _historico = info
    erro = _check_acesso(empresa_id)
    if erro:
        return erro
    return render_template(
        "partials/verbatim_reclassificar_modal.html",
        v=v_dict,
        SUBPILARES=sorted(SUBPILARES_VALIDOS),
        TIPOS=sorted(TIPOS_VALIDOS),
    )


@ui_bp.route("/ui/verbatins/<int:verbatim_id>/reclassificar", methods=["PATCH"])
def htmx_salvar_reclassificacao(verbatim_id: int):
    """Salva reclassificação via PATCH form. Devolve o item atualizado."""
    sub_novo = (request.form.get("subpilar") or "").strip()
    tipo_novo = (request.form.get("tipo") or "").strip()
    justif = (request.form.get("justificativa") or "").strip() or None

    if sub_novo not in SUBPILARES_VALIDOS:
        return ("<div class='text-red-600 text-xs'>subpilar inválido.</div>", 400)
    if tipo_novo not in TIPOS_VALIDOS:
        return ("<div class='text-red-600 text-xs'>tipo inválido.</div>", 400)
    if (sub_novo == "sem_lastro") != (tipo_novo == "inativo"):
        return (
            "<div class='text-red-600 text-xs'>"
            "Restrição: sem_lastro exige inativo (e vice-versa).</div>",
            400,
        )

    user = get_current_user()
    if user is None:
        return ("<div class='text-red-600 text-xs'>Sessão expirada.</div>", 401)

    from datetime import datetime as _dt

    with db_session() as s:
        v_db = s.get(Verbatim, verbatim_id)
        if v_db is None:
            return ("<div class='text-red-600 text-xs'>Verbatim não encontrado.</div>", 404)
        if user.papel != PAPEL_LOYALL and user.empresa_id != v_db.empresa_id:
            return ("<div class='text-red-600 text-xs'>Acesso negado.</div>", 403)

        recl = VerbatimReclassificacao(
            verbatim_id=v_db.id,
            subpilar_anterior=v_db.subpilar,
            tipo_anterior=v_db.tipo,
            subpilar_novo=sub_novo,
            tipo_novo=tipo_novo,
            justificativa=justif,
            reclassificado_por=user.id,
        )
        s.add(recl)
        v_db.subpilar_anterior = v_db.subpilar
        v_db.tipo_anterior = v_db.tipo
        v_db.subpilar = sub_novo
        v_db.tipo = tipo_novo
        v_db.reclassificado_em = _dt.utcnow()
        v_db.reclassificado_por = user.id
        s.flush()

    # Devolve o item renderizado novamente
    info = _carregar_verbatim_para_template(verbatim_id)
    v_dict, _eid, _hist = info
    return render_template(
        "partials/verbatim_item.html",
        v=v_dict,
        eh_loyall=(user.papel == PAPEL_LOYALL),
    )


@ui_bp.route("/ui/verbatins/<int:verbatim_id>", methods=["DELETE"])
def htmx_excluir_verbatim(verbatim_id: int):
    user = get_current_user()
    if user is None:
        return ("", 401)
    with db_session() as s:
        v_db = s.get(Verbatim, verbatim_id)
        if v_db is None:
            return ("", 404)
        if user.papel != PAPEL_LOYALL and user.empresa_id != v_db.empresa_id:
            return ("", 403)
        s.delete(v_db)
    return ("", 200)


# ── HTMX partials: CRUD inline em /empresas/<id> ────────────────────────


def _check_acesso(empresa_id: int):
    """Para endpoints HTMX: devolve None ou tupla (fragment, status)."""
    user = get_current_user()
    if user is None:
        return ("<div class='text-red-600'>Sessão expirada.</div>", 401)
    if user.papel != PAPEL_LOYALL and user.empresa_id != empresa_id:
        return ("<div class='text-red-600'>Acesso negado.</div>", 403)
    return None


@ui_bp.route("/ui/empresas/<int:empresa_id>/agrupamentos", methods=["POST"])
@loyall_required_ui
def htmx_criar_agrupamento(empresa_id: int):
    user = get_current_user()
    if user is None or user.papel != PAPEL_LOYALL:
        return ("<div class='text-red-600'>Restrito a admin Loyall.</div>", 403)
    nome = (request.form.get("nome") or "").strip()
    descricao = (request.form.get("descricao") or "").strip() or None
    if not nome:
        return ("<div class='text-red-600'>Nome é obrigatório.</div>", 400)
    with db_session() as s:
        ja = s.query(Agrupamento).filter_by(empresa_id=empresa_id, nome=nome).first()
        if ja:
            return (
                f"<div class='text-red-600'>Já existe agrupamento '{nome}'.</div>",
                409,
            )
        a_db = Agrupamento(empresa_id=empresa_id, nome=nome, descricao=descricao)
        s.add(a_db)
        s.flush()
        a_w = _wrap_agrupamento(a_db, [])
    return render_template("partials/agrupamento_card.html", a=a_w, eh_loyall=True, open=True)


def _carregar_ag(agrupamento_id: int):
    """Carrega Agrupamento como view-model wrapper com locais+fontes."""
    with db_session() as s:
        a_db = s.get(Agrupamento, agrupamento_id)
        if a_db is None:
            return None
        locais_db = (
            s.query(Local)
            .filter_by(empresa_id=a_db.empresa_id, agrupamento_id=a_db.id)
            .order_by(Local.nome)
            .all()
        )
        locais_w = []
        for loc_db in locais_db:
            fontes_db = (
                s.query(Fonte)
                .filter_by(entidade_tipo="local", entidade_id=loc_db.id)
                .order_by(Fonte.id)
                .all()
            )
            locais_w.append(_wrap_local(loc_db, fontes_db))
        return _wrap_agrupamento(a_db, locais_w)


@ui_bp.route("/ui/agrupamentos/<int:agrupamento_id>/row", methods=["GET"])
@loyall_required_ui
def htmx_agrupamento_row(agrupamento_id: int):
    """Devolve a row em modo view (para cancelar edição ou após save)."""
    a = _carregar_ag(agrupamento_id)
    if a is None:
        return ("", 404)
    user = get_current_user()
    eh_loyall = bool(user and user.papel == PAPEL_LOYALL)
    return render_template("partials/agrupamento_card.html", a=a, eh_loyall=eh_loyall)


@ui_bp.route("/ui/agrupamentos/<int:agrupamento_id>/editar", methods=["GET"])
@loyall_required_ui
def htmx_editar_agrupamento_form(agrupamento_id: int):
    """Devolve a row em modo edit (inputs em vez de spans)."""
    user = get_current_user()
    if user is None or user.papel != PAPEL_LOYALL:
        return (
            "<tr><td colspan='4' class='text-red-600 text-xs'>"
            "Edição restrita a admin Loyall.</td></tr>"
        ), 403
    a = _carregar_ag(agrupamento_id)
    if a is None:
        return ("", 404)
    return render_template("partials/agrupamento_card_edit.html", a=a)


@ui_bp.route("/ui/agrupamentos/<int:agrupamento_id>", methods=["PUT"])
@loyall_required_ui
def htmx_salvar_agrupamento(agrupamento_id: int):
    user = get_current_user()
    if user is None or user.papel != PAPEL_LOYALL:
        return (
            "<tr><td colspan='4' class='text-red-600 text-xs'>"
            "Edição restrita a admin Loyall.</td></tr>"
        ), 403
    nome = (request.form.get("nome") or "").strip()
    descricao = (request.form.get("descricao") or "").strip() or None
    if not nome:
        return (
            "<tr><td colspan='4' class='text-red-600 text-xs'>" "Nome é obrigatório.</td></tr>"
        ), 400
    with db_session() as s:
        a = s.get(Agrupamento, agrupamento_id)
        if a is None:
            return ("", 404)
        # Verifica conflito de nome (exceto ele mesmo)
        dup = (
            s.query(Agrupamento)
            .filter(
                Agrupamento.empresa_id == a.empresa_id,
                Agrupamento.nome == nome,
                Agrupamento.id != a.id,
            )
            .first()
        )
        if dup:
            return (
                "<tr><td colspan='4' class='text-red-600 text-xs'>"
                f"Já existe agrupamento '{nome}'.</td></tr>"
            ), 409
        a.nome = nome
        a.descricao = descricao
        s.flush()
    # Recarrega com locais+fontes
    a = _carregar_ag(agrupamento_id)
    return render_template("partials/agrupamento_card.html", a=a, eh_loyall=True, open=True)


@ui_bp.route("/ui/agrupamentos/<int:agrupamento_id>/inativar", methods=["PATCH"])
@loyall_required_ui
def htmx_inativar_agrupamento(agrupamento_id: int):
    user = get_current_user()
    if user is None or user.papel != PAPEL_LOYALL:
        return (
            "<tr><td colspan='4' class='text-red-600 text-xs'>" "Restrito a admin Loyall.</td></tr>"
        ), 403
    with db_session() as s:
        a = s.get(Agrupamento, agrupamento_id)
        if a is None:
            return ("", 404)
        a.ativo = not bool(a.ativo)
        s.flush()
    a = _carregar_ag(agrupamento_id)
    return render_template("partials/agrupamento_card.html", a=a, eh_loyall=True)


@ui_bp.route("/ui/agrupamentos/<int:agrupamento_id>", methods=["DELETE"])
@loyall_required_ui
def htmx_deletar_agrupamento(agrupamento_id: int):
    user = get_current_user()
    if user is None or user.papel != PAPEL_LOYALL:
        return ("<div class='text-red-600'>Restrito a admin Loyall.</div>", 403)
    with db_session() as s:
        a = s.get(Agrupamento, agrupamento_id)
        if a is None:
            return ("", 404)
        s.delete(a)
    return ("", 200)


@ui_bp.route("/ui/empresas/<int:empresa_id>/locais", methods=["POST"])
@loyall_required_ui
def htmx_criar_local(empresa_id: int):
    erro = _check_acesso(empresa_id)
    if erro:
        return erro
    nome = (request.form.get("nome") or "").strip()
    if not nome:
        return ("<div class='text-red-600'>Nome é obrigatório.</div>", 400)
    ag_id_raw = request.form.get("agrupamento_id") or ""
    agrupamento_id = int(ag_id_raw) if ag_id_raw.isdigit() else None
    endereco = (request.form.get("endereco") or "").strip() or None
    with db_session() as s:
        if agrupamento_id is not None:
            ag = s.get(Agrupamento, agrupamento_id)
            if ag is None or ag.empresa_id != empresa_id:
                return ("<div class='text-red-600'>Agrupamento inválido.</div>", 400)
        loc = Local(
            empresa_id=empresa_id,
            agrupamento_id=agrupamento_id,
            nome=nome,
            endereco=endereco,
        )
        s.add(loc)
        s.flush()
        ag_nome = ag.nome if agrupamento_id else None
        loc_w = _wrap_local(loc, [])
    return render_template(
        "partials/local_card.html",
        loc=loc_w,
        agrupamento_nome={agrupamento_id: ag_nome} if agrupamento_id else {},
    )


def _carregar_local_e_ags(local_id: int):
    """Devolve (loc_wrapper, ags_wrappers, ag_map) para o template de local."""
    with db_session() as s:
        loc_db = s.get(Local, local_id)
        if loc_db is None:
            return None, [], None
        ags_db = (
            s.query(Agrupamento)
            .filter_by(empresa_id=loc_db.empresa_id)
            .order_by(Agrupamento.nome)
            .all()
        )
        fontes_db = (
            s.query(Fonte)
            .filter_by(entidade_tipo="local", entidade_id=loc_db.id)
            .order_by(Fonte.id)
            .all()
        )
        loc_w = _wrap_local(loc_db, fontes_db)
        ags_w = [SimpleNamespace(id=a.id, nome=a.nome, empresa_id=a.empresa_id) for a in ags_db]
        ag_map = {a.id: a.nome for a in ags_db}
    return loc_w, ags_w, ag_map


@ui_bp.route("/ui/locais/<int:local_id>/row", methods=["GET"])
@loyall_required_ui
def htmx_local_row(local_id: int):
    loc, ags, ag_map = _carregar_local_e_ags(local_id)
    if loc is None:
        return ("", 404)
    erro = _check_acesso(loc.empresa_id)
    if erro:
        return erro
    return render_template("partials/local_card.html", loc=loc, agrupamento_nome=ag_map)


@ui_bp.route("/ui/locais/<int:local_id>/editar", methods=["GET"])
@loyall_required_ui
def htmx_editar_local_form(local_id: int):
    loc, ags, _ag_map = _carregar_local_e_ags(local_id)
    if loc is None:
        return ("", 404)
    erro = _check_acesso(loc.empresa_id)
    if erro:
        return erro
    return render_template("partials/local_card_edit.html", loc=loc, agrupamentos=ags)


# Grupos de milhar PT-BR só-com-ponto: "1.000", "12.500", "1.234.567" (cada ponto
# seguido de EXATAMENTE 3 dígitos). Distingue milhar de decimal quando não há vírgula.
_RE_MILHAR_BR = re.compile(r"^\d{1,3}(\.\d{3})+$")


def _parse_num_brl(raw):
    """Converte texto de valor (ticket/frequência) em float > 0, ou None.

    Corrige o bug do parser anterior, que fazia ``.replace(".", "")`` cego e
    inflava decimais com ponto (a sugestão IA manda float JSON: "45.9" → virava
    459). Regras:

    - Vírgula presente → formato BR ("1.234,56"): ponto é milhar, vírgula é
      decimal → remove pontos, vírgula vira ponto.
    - Só pontos em grupos de 3 ("1.000", "12.500") → milhar → remove pontos.
    - Senão → ponto é decimal ("45.9", "120.0", "89.90") → float direto.

    Vazio / não-numérico / ``<= 0`` → ``None`` (→ R$ "—" honesto).
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif _RE_MILHAR_BR.match(raw):
        raw = raw.replace(".", "")
    try:
        v = float(raw)
    except ValueError:
        return None
    return v if v > 0 else None


@ui_bp.route("/ui/locais/<int:local_id>", methods=["PUT"])
@loyall_required_ui
def htmx_salvar_local(local_id: int):
    nome = (request.form.get("nome") or "").strip()
    if not nome:
        return (
            "<tr><td colspan='5' class='text-red-600 text-xs'>" "Nome é obrigatório.</td></tr>"
        ), 400
    ag_id_raw = request.form.get("agrupamento_id") or ""
    new_ag = int(ag_id_raw) if ag_id_raw.isdigit() else None
    endereco = (request.form.get("endereco") or "").strip() or None

    ticket = _parse_num_brl(request.form.get("ticket_medio"))
    frequencia = _parse_num_brl(request.form.get("frequencia"))
    # origem vinda do pré-preenchimento (hidden); edição manual c/ valor → 'proprio'.
    origem = (request.form.get("ltv_origem") or "").strip() or None
    if (ticket is not None or frequencia is not None) and origem is None:
        origem = "proprio"
    with db_session() as s:
        loc = s.get(Local, local_id)
        if loc is None:
            return ("", 404)
        erro = _check_acesso(loc.empresa_id)
        if erro:
            return erro
        if new_ag is not None:
            ag = s.get(Agrupamento, new_ag)
            if ag is None or ag.empresa_id != loc.empresa_id:
                return (
                    "<tr><td colspan='5' class='text-red-600 text-xs'>"
                    "Agrupamento inválido.</td></tr>"
                ), 400
        loc.nome = nome
        loc.agrupamento_id = new_ag
        loc.endereco = endereco
        loc.ticket_medio = ticket
        loc.frequencia = frequencia
        loc.ltv_origem = origem
        s.flush()
    # Recarrega com fontes + ag_map
    loc, _ags, ag_map = _carregar_local_e_ags(local_id)
    return render_template("partials/local_card.html", loc=loc, agrupamento_nome=ag_map, open=True)


@ui_bp.route("/ui/locais/<int:local_id>/inativar", methods=["PATCH"])
@loyall_required_ui
def htmx_inativar_local(local_id: int):
    with db_session() as s:
        loc = s.get(Local, local_id)
        if loc is None:
            return ("", 404)
        erro = _check_acesso(loc.empresa_id)
        if erro:
            return erro
        loc.status = "desativado" if loc.status == "ativo" else "ativo"
        s.flush()
    loc, _ags, ag_map = _carregar_local_e_ags(local_id)
    return render_template("partials/local_card.html", loc=loc, agrupamento_nome=ag_map)


@ui_bp.route("/ui/locais/<int:local_id>", methods=["DELETE"])
@loyall_required_ui
def htmx_deletar_local(local_id: int):
    with db_session() as s:
        loc = s.get(Local, local_id)
        if loc is None:
            return ("", 404)
        erro = _check_acesso(loc.empresa_id)
        if erro:
            return erro
        # Remove fontes do local (polimórfico)
        for f in s.query(Fonte).filter_by(entidade_tipo="local", entidade_id=local_id).all():
            s.delete(f)
        s.delete(loc)
    return ("", 200)


@ui_bp.route("/ui/locais/<int:local_id>/fontes", methods=["POST"])
@loyall_required_ui
def htmx_criar_fonte(local_id: int):
    from src.api.fontes import CONECTORES_COM_SCRAPER, CONECTORES_CONHECIDOS

    with db_session() as s:
        loc = s.get(Local, local_id)
        if loc is None:
            return ("<div class='text-red-600'>Local não encontrado.</div>", 404)
        empresa_id = loc.empresa_id
        loc_nome = loc.nome  # captura para uso fora da sessão
    erro = _check_acesso(empresa_id)
    if erro:
        return erro

    conector = (request.form.get("conector_tipo") or "").strip()
    url = (request.form.get("url") or "").strip()
    ativo = request.form.get("ativo") == "on"
    if not conector or conector not in CONECTORES_CONHECIDOS:
        return (
            f"<div class='text-red-600'>conector_tipo inválido. Aceitos: "
            f"{', '.join(sorted(CONECTORES_CONHECIDOS))}</div>",
            400,
        )
    if conector not in CONECTORES_COM_SCRAPER and ativo:
        return (
            f"<div class='text-red-600'>'{conector}' não tem scraper Apify. "
            f"Cadastre como inativo (catalogação).</div>",
            400,
        )
    if not url:
        return ("<div class='text-red-600'>url é obrigatória.</div>", 400)

    with db_session() as s:
        f = Fonte(
            empresa_id=empresa_id,
            entidade_tipo="local",
            entidade_id=local_id,
            conector_tipo=conector,
            url=url,
            ativo=ativo,
        )
        s.add(f)
        s.flush()
        # Força carga de atributos antes do expunge (commit-on-exit expira).
        _ = (
            f.id,
            f.empresa_id,
            f.entidade_tipo,
            f.entidade_id,
            f.conector_tipo,
            f.url,
            f.ativo,
            f.ultima_coleta,
            f.criada_em,
            f.observacao,
        )
        s.expunge(f)
    # Embrulha p/ a fonte recém-criada já exibir o nome do local (não o place_id cru).
    f_w = _wrap_fonte(f, nome_local=loc_nome)
    return render_template("partials/fonte_item.html", f=f_w, local_nome={local_id: loc_nome})


def _carregar_fonte_e_local(fonte_id: int):
    """Devolve (fonte_wrapper, local_map_id_to_nome)."""
    with db_session() as s:
        f_db = s.get(Fonte, fonte_id)
        if f_db is None:
            return None, {}
        local_map = {}
        if f_db.entidade_tipo == "local":
            loc_db = s.get(Local, f_db.entidade_id)
            if loc_db is not None:
                local_map[loc_db.id] = loc_db.nome
        f_w = _wrap_fonte(f_db, nome_local=local_map.get(f_db.entidade_id))
    return f_w, local_map


@ui_bp.route("/ui/fontes/<int:fonte_id>/row", methods=["GET"])
@loyall_required_ui
def htmx_fonte_row(fonte_id: int):
    f, local_map = _carregar_fonte_e_local(fonte_id)
    if f is None:
        return ("", 404)
    erro = _check_acesso(f.empresa_id)
    if erro:
        return erro
    return render_template("partials/fonte_item.html", f=f, local_nome=local_map)


@ui_bp.route("/ui/fontes/<int:fonte_id>/editar", methods=["GET"])
@loyall_required_ui
def htmx_editar_fonte_form(fonte_id: int):
    f, _local_map = _carregar_fonte_e_local(fonte_id)
    if f is None:
        return ("", 404)
    erro = _check_acesso(f.empresa_id)
    if erro:
        return erro
    return render_template("partials/fonte_item_edit.html", f=f)


@ui_bp.route("/ui/fontes/<int:fonte_id>", methods=["PUT"])
@loyall_required_ui
def htmx_salvar_fonte(fonte_id: int):
    url = (request.form.get("url") or "").strip()
    observacao = (request.form.get("observacao") or "").strip() or None
    if not url:
        return (
            "<tr><td colspan='6' class='text-red-600 text-xs'>" "URL é obrigatória.</td></tr>"
        ), 400
    with db_session() as s:
        f = s.get(Fonte, fonte_id)
        if f is None:
            return ("", 404)
        erro = _check_acesso(f.empresa_id)
        if erro:
            return erro
        f.url = url
        f.observacao = observacao
        s.flush()
        local_map = {}
        if f.entidade_tipo == "local":
            loc = s.get(Local, f.entidade_id)
            if loc is not None:
                local_map[loc.id] = loc.nome
        _ = (
            f.id,
            f.empresa_id,
            f.entidade_tipo,
            f.entidade_id,
            f.conector_tipo,
            f.url,
            f.ativo,
            f.ultima_coleta,
            f.criada_em,
            f.observacao,
        )
        s.expunge(f)
    return render_template("partials/fonte_item.html", f=f, local_nome=local_map)


@ui_bp.route("/ui/fontes/<int:fonte_id>/inativar", methods=["PATCH"])
@loyall_required_ui
def htmx_inativar_fonte(fonte_id: int):
    with db_session() as s:
        f = s.get(Fonte, fonte_id)
        if f is None:
            return ("", 404)
        erro = _check_acesso(f.empresa_id)
        if erro:
            return erro
        f.ativo = not bool(f.ativo)
        s.flush()
        local_map = {}
        if f.entidade_tipo == "local":
            loc = s.get(Local, f.entidade_id)
            if loc is not None:
                local_map[loc.id] = loc.nome
        _ = (
            f.id,
            f.empresa_id,
            f.entidade_tipo,
            f.entidade_id,
            f.conector_tipo,
            f.url,
            f.ativo,
            f.ultima_coleta,
            f.criada_em,
            f.observacao,
        )
        s.expunge(f)
    return render_template("partials/fonte_item.html", f=f, local_nome=local_map)


@ui_bp.route("/ui/fontes/<int:fonte_id>", methods=["DELETE"])
@loyall_required_ui
def htmx_deletar_fonte(fonte_id: int):
    with db_session() as s:
        f = s.get(Fonte, fonte_id)
        if f is None:
            return ("", 404)
        erro = _check_acesso(f.empresa_id)
        if erro:
            return erro
        s.delete(f)
    return ("", 200)


@ui_bp.route("/ui/empresas/<int:empresa_id>/editar-modal", methods=["GET"])
@loyall_required_ui
def htmx_editar_empresa_modal(empresa_id: int):
    """Devolve o HTML do modal de edição da empresa (HTMX abre como overlay)."""
    user = get_current_user()
    if user is None or user.papel != PAPEL_LOYALL:
        return ("<div class='text-red-600 text-xs'>" "Edição restrita a admin Loyall.</div>"), 403
    with db_session() as s:
        empresa = s.get(Empresa, empresa_id)
        if empresa is None:
            return ("", 404)
        _ = (
            empresa.id,
            empresa.nome,
            empresa.setor,
            empresa.site,
            empresa.observacao,
            empresa.cnpj,
        )
        s.expunge(empresa)
    return render_template("partials/empresa_edit_modal.html", empresa=empresa)


@ui_bp.route("/ui/empresas/<int:empresa_id>", methods=["PUT"])
@loyall_required_ui
def htmx_salvar_empresa(empresa_id: int):
    user = get_current_user()
    if user is None or user.papel != PAPEL_LOYALL:
        return ("<div class='text-red-600 text-xs'>" "Edição restrita a admin Loyall.</div>"), 403
    nome = (request.form.get("nome") or "").strip()
    if not nome:
        return ("<div class='text-red-600 text-xs'>Nome é obrigatório.</div>"), 400
    setor = (request.form.get("setor") or "").strip() or None
    site = (request.form.get("site") or "").strip() or None
    observacao = (request.form.get("observacao") or "").strip() or None

    def _taxa(campo, default):  # 0–1; fora da faixa/ inválida → mantém default
        raw = (request.form.get(campo) or "").strip().replace(",", ".")
        try:
            v = float(raw)
            return v if 0 <= v <= 1 else default
        except (ValueError, TypeError):
            return default

    from datetime import datetime as _dt

    with db_session() as s:
        empresa = s.get(Empresa, empresa_id)
        if empresa is None:
            return ("", 404)
        # Conflito de nome com outra empresa?
        dup = s.query(Empresa).filter(Empresa.nome == nome, Empresa.id != empresa_id).first()
        if dup:
            return (
                f"<div class='text-red-600 text-xs'>"
                f"Já existe outra empresa com nome '{nome}'.</div>"
            ), 409
        empresa.nome = nome
        empresa.setor = setor
        empresa.site = site
        empresa.observacao = observacao
        empresa.taxa_alto = _taxa("taxa_alto", empresa.taxa_alto)
        empresa.taxa_medio = _taxa("taxa_medio", empresa.taxa_medio)
        empresa.taxa_baixo = _taxa("taxa_baixo", empresa.taxa_baixo)
        empresa.atualizada_em = _dt.utcnow()
    # Resposta vazia: o modal usa hx-on::after-request="window.location.reload()"
    return ("", 200)


@ui_bp.route("/ui/fontes/<int:fonte_id>/disparar", methods=["POST"])
@loyall_required_ui
def htmx_disparar_fonte(fonte_id: int):
    """Botão 'disparar coleta' — CP-5b (Opção A): FIRE-AND-FORGET. Dispara a coleta
    da fonte numa daemon-thread e retorna 'coletando…' na hora; não trava a request
    na cauda do google (p90 ~7min). O status real vai pra ``coletas_execucoes`` (o
    pollColetas acompanha). Guards síncronos (em_andamento/cooldown) ANTES de
    spawnar — duplo-clique não cria 2 threads."""
    from src.coletor.orquestrador import (
        COOLDOWN_MINUTOS,
        disparar_coleta_fonte_async,
        em_cooldown,
        execucao_em_andamento,
    )

    with db_session() as s:
        f = s.get(Fonte, fonte_id)
        if f is None:
            return ("<div class='text-red-600 text-xs'>Fonte não encontrada.</div>", 404)
        erro = _check_acesso(f.empresa_id)
        if erro:
            return erro
        empresa_id = f.empresa_id

    if execucao_em_andamento("fonte", fonte_id):
        return "<div class='text-amber-700 text-xs'>⏳ Coleta em andamento</div>"
    ult = em_cooldown("fonte", fonte_id)
    if ult is not None:
        return (
            f"<div class='text-amber-700 text-xs'>⏳ Cooldown {COOLDOWN_MINUTOS} min. "
            f"Última: {ult.isoformat()[:16]}</div>"
        )

    disparar_coleta_fonte_async(fonte_id, empresa_id)
    return (
        "<div class='text-loyall-700 text-xs'>🔄 Coletando… acompanhe o status na lista.</div>",
        202,
    )


def _fmt_stats_coleta(stats: dict) -> str:
    """HTML inline curto para devolver após coleta (Local/Agrupamento)."""
    if "erro" in stats:
        if stats.get("em_cooldown"):
            return (
                f"<div class='text-amber-700 text-xs'>"
                f"⏳ Cooldown 15 min. Última: {stats.get('ultima_coleta', '?')[:16]}</div>"
            )
        if stats.get("em_andamento"):
            return "<div class='text-amber-700 text-xs'>⏳ Coleta em andamento</div>"
        return f"<div class='text-red-600 text-xs'>Falha: {stats['erro']}</div>"
    fp = stats.get("fontes_processadas", 0)
    ok = stats.get("fontes_ok", 0)
    falha = stats.get("fontes_falha", 0)
    novos = stats.get("novos", 0)
    coletados = stats.get("coletados", 0)
    return (
        f"<div class='text-emerald-700 text-xs'>"
        f"✓ {ok}/{fp} fontes ok · {coletados} coletados · {novos} novos"
        f"{(' · ' + str(falha) + ' falhas') if falha else ''}</div>"
    )


@ui_bp.route("/ui/locais/<int:local_id>/disparar", methods=["POST"])
@loyall_required_ui
def htmx_disparar_local(local_id: int):
    """Coleta as fontes ativas do local — CP-5b: FIRE-AND-FORGET (daemon-thread,
    retorna 'coletando…' na hora). Guards síncronos antes de spawnar."""
    from src.coletor.orquestrador import (
        COOLDOWN_MINUTOS,
        disparar_coleta_local_async,
        em_cooldown,
        execucao_em_andamento,
    )
    from src.models.local import Local

    with db_session() as s:
        loc = s.get(Local, local_id)
        if loc is None:
            return ("<div class='text-red-600 text-xs'>Local não encontrado.</div>", 404)
        erro = _check_acesso(loc.empresa_id)
        if erro:
            return erro

    if execucao_em_andamento("local", local_id):
        return "<div class='text-amber-700 text-xs'>⏳ Coleta em andamento</div>"
    ult = em_cooldown("local", local_id)
    if ult is not None:
        return (
            f"<div class='text-amber-700 text-xs'>⏳ Cooldown {COOLDOWN_MINUTOS} min. "
            f"Última: {ult.isoformat()[:16]}</div>"
        )

    disparar_coleta_local_async(local_id)
    return (
        "<div class='text-loyall-700 text-xs'>🔄 Coletando… acompanhe o status na lista.</div>",
        202,
    )


@ui_bp.route("/ui/agrupamentos/<int:agrupamento_id>/disparar", methods=["POST"])
@loyall_required_ui
def htmx_disparar_agrupamento(agrupamento_id: int):
    """Coleta todos os locais do agrupamento. CP-5b: DESABILITADO em produção
    (dezenas de fontes em série → não sobrevive ao timeout HTTP; a coleta completa
    é a noturna). Em dev segue síncrono (útil pra teste). O botão também some em
    prod (gate ``em_producao`` no template)."""
    import os

    if os.getenv("FLASK_ENV") == "production":
        return (
            "<div class='text-amber-700 text-xs'>Coleta de agrupamento on-demand "
            "desabilitada em produção — a coleta completa é a noturna.</div>",
            403,
        )

    from src.coletor.orquestrador import coletar_agrupamento
    from src.models.agrupamento import Agrupamento

    with db_session() as s:
        ag = s.get(Agrupamento, agrupamento_id)
        if ag is None:
            return ("<div class='text-red-600 text-xs'>Agrupamento não encontrado.</div>", 404)
        erro = _check_acesso(ag.empresa_id)
        if erro:
            return erro
    try:
        stats = coletar_agrupamento(agrupamento_id)
    except Exception as exc:  # pragma: no cover — robustez
        return (f"<div class='text-red-600 text-xs'>Falha: {exc!r}</div>", 500)
    return _fmt_stats_coleta(stats)


@ui_bp.route("/ui/empresas/<int:empresa_id>/toggle-coleta-noturna", methods=["POST"])
@loyall_required_ui
def htmx_toggle_coleta_noturna(empresa_id: int):
    """Liga/desliga a coleta noturna (cron) da empresa (CP-noturna-toggle).
    Loyall-only. Devolve o próprio botão re-renderizado (outerHTML)."""
    with db_session() as s:
        empresa = s.get(Empresa, empresa_id)
        if empresa is None:
            return ("", 404)
        empresa.coleta_noturna_ativa = not bool(empresa.coleta_noturna_ativa)
        novo = empresa.coleta_noturna_ativa
    return render_template(
        "partials/coleta_noturna_toggle.html",
        empresa=SimpleNamespace(id=empresa_id, coleta_noturna_ativa=novo),
    )


@ui_bp.route("/ui/empresas/<int:empresa_id>/reprocessar", methods=["POST"])
@loyall_required_ui
def htmx_reprocessar_empresa(empresa_id: int):
    """Dispara o pipeline pós-coleta (passo 7.5 inclui Proximity/Gini/Mapa) da
    empresa em segundo plano, SEM coletar — destrava o reprocessamento após
    reagrupar lojas sem depender do terminal (CP-UX-reprocessar).

    Fire-and-forget: reusa ``disparar_pos_coleta_async`` (thread daemon) tal como
    está; a requisição retorna na hora. NÃO há tracking de conclusão — o operador
    recarrega a página depois. PODE consumir LLM (diagnóstico/sugestões com
    skip-by-hash) — avisado no botão. Gated a admin Loyall."""
    user = get_current_user()
    if user is None or user.papel != PAPEL_LOYALL:
        return ("<div class='text-red-600 text-xs'>Restrito a admin Loyall.</div>", 403)

    from src.coletor.orquestrador import disparar_pos_coleta_async

    disparar_pos_coleta_async(empresa_id)
    return (
        "<div class='px-3 py-2 rounded bg-emerald-50 border-l-4 border-emerald-400 "
        "text-xs text-emerald-800'>✓ Reprocessamento iniciado em segundo plano. "
        "Aguarde ~2-3 min e recarregue a página para ver os números atualizados.</div>"
    )


# ── Hub Explorar (Grupo A) ────────────────────────────────────────────

# Estrutura de abas do Hub Explorar. O campo "grupo" define a SEÇÃO de cada aba
# na tab bar (CP-B): a bar é agrupada e rotulada por seção (visao/explorar/
# diagnostico/acao/saida + ia), na ordem do funil. Ver _EXPLORAR_GRUPOS e
# templates/partials/explorar_tabbar.html.
# Dimensões de escopo do header global, na ordem de exibição. `escopo_aceito`
# em cada aba lista quais aparecem como <select> visível; as ausentes viram
# <input type="hidden"> (carregam o valor atual → persistência de escopo entre
# abas preservada — NUNCA são removidas do form). Editar o filtro de uma aba =
# mexer em 1 linha aqui (CP-A, header condicional declarativo).
_ESCOPO_DIMENSOES = ("agrupamento", "local", "periodo")
_ESCOPO_FULL = list(_ESCOPO_DIMENSOES)  # atalho p/ "como hoje" (as três visíveis)

# Ordem do FUNIL (CP-B): panorama → explorar → causa → ação → saída. O `grupo` de
# cada aba aponta p/ uma seção em _EXPLORAR_GRUPOS; a tab bar renderiza as seções
# rotuladas, na ordem desta lista. IA fica fora do funil (transversal, à direita).
# Reorg SÓ visual — escopo_aceito de cada aba é o do CP-A, intacto.
_EXPLORAR_TABS = [
    # VISÃO (panorama)
    {"id": "painel", "label": "Painel", "grupo": "visao", "escopo_aceito": _ESCOPO_FULL},
    {"id": "locais", "label": "Locais", "grupo": "visao", "escopo_aceito": []},
    {"id": "leaderboard", "label": "Leaderboard", "grupo": "visao", "escopo_aceito": _ESCOPO_FULL},
    # EXPLORAR (dados)
    {"id": "heatmap", "label": "Heatmap", "grupo": "explorar", "escopo_aceito": _ESCOPO_FULL},
    {"id": "comparar", "label": "Comparar", "grupo": "explorar", "escopo_aceito": _ESCOPO_FULL},
    {"id": "evolucao", "label": "Evolução", "grupo": "explorar", "escopo_aceito": _ESCOPO_FULL},
    {"id": "temas", "label": "Temas", "grupo": "explorar", "escopo_aceito": _ESCOPO_FULL},
    # Verbatins NÃO mostra período no header: a API de listagem ignora período
    # relativo (usa date-pickers absolutos data_de/data_ate, filtro próprio da
    # aba). Mostrar período aqui faria o chip prometer um recorte não aplicado.
    {
        "id": "verbatins",
        "label": "Verbatins",
        "grupo": "explorar",
        "escopo_aceito": ["agrupamento", "local"],
    },
    # DIAGNÓSTICO (causa)
    {
        "id": "diagnostico",
        "label": "Diagnóstico",
        "grupo": "diagnostico",
        "escopo_aceito": ["agrupamento", "local"],
    },
    {
        "id": "concentracao",
        "label": "Concentração",
        "grupo": "diagnostico",
        "escopo_aceito": ["agrupamento"],
    },
    {
        "id": "anomalias",
        "label": "Anomalias",
        "grupo": "diagnostico",
        "escopo_aceito": _ESCOPO_FULL,
    },
    # AÇÃO
    {
        "id": "planos",
        "label": "Planos de Ação",
        "grupo": "acao",
        "escopo_aceito": ["agrupamento", "local"],
    },
    # GOVERNANÇA & SAÍDA
    {"id": "governanca", "label": "Governança", "grupo": "saida", "escopo_aceito": _ESCOPO_FULL},
    {"id": "relatorios", "label": "Relatórios", "grupo": "saida", "escopo_aceito": _ESCOPO_FULL},
    # IA (transversal — renderizada à direita, fora do funil)
    {"id": "ia", "label": "✨ IA", "grupo": "ia", "escopo_aceito": _ESCOPO_FULL},
]
# Seções da tab bar (CP-B), na ordem do funil. IA não entra aqui — é transversal e
# a tab bar a renderiza à direita, separada.
_EXPLORAR_GRUPOS = [
    {"id": "visao", "label": "Visão"},
    {"id": "explorar", "label": "Explorar"},
    {"id": "diagnostico", "label": "Diagnóstico"},
    {"id": "acao", "label": "Ação"},
    {"id": "saida", "label": "Governança & Saída"},
]
# Set de ids para validação rápida (substitui o antigo `tab in _EXPLORAR_TABS`).
_EXPLORAR_TAB_IDS = {t["id"] for t in _EXPLORAR_TABS}
# Mapa id→escopo_aceito p/ o contexto do template (chip + header condicional).
_EXPLORAR_ESCOPO_ACEITO = {t["id"]: t["escopo_aceito"] for t in _EXPLORAR_TABS}
# Abas que ainda usam full-load (não HTMX swap). VAZIO desde o CP-UX2b: todas as
# abas fazem HTMX swap. O <script> inline que morria no swap innerHTML (export-href,
# leitura, toggles das anomalias) virou um re-init global data-driven em base.html
# (lê data-export-*/data-leitura-url/data-anom-empresa no htmx:afterSettle). Os forms
# de filtro de Painel/Verbatins seguem full-load por decisão (o piscar = feedback).
_EXPLORAR_TABS_MIGRADAS = set()


def _explorar_filtros():
    """Filtros globais do hub: agrupamento + período. Devolve (filtros_eco,
    ag_id, corte) — filtros_eco p/ o template, ag_id/corte p/ as queries."""
    from src.api.painel import _resolver_periodo

    ag_raw = request.args.get("agrupamento_id", "")
    periodo = request.args.get("periodo", "")
    local_raw = request.args.get("local_id", "")
    ag_id = int(ag_raw) if ag_raw.isdigit() else None
    corte = _resolver_periodo(periodo)
    return (
        {"agrupamento_id": ag_raw, "periodo": periodo, "local_id": local_raw},
        ag_id,
        corte,
    )


# Rótulos de período p/ o chip de escopo (espelham o <select> do header).
_PERIODO_LABELS = {
    "7d": "7 dias",
    "30d": "30 dias",
    "90d": "90 dias",
    "6m": "6 meses",
    "12m": "12 meses",
    "15m": "15 meses",
}


def _montar_escopo_chip(filtros, agrupamentos, lojas_header, escopo_aceito):
    """Partes do chip 'Analisando: …' — só as dimensões que a aba ACEITA e que
    têm valor selecionado. Representa o escopo GLOBAL do header (sempre os
    valores de _explorar_filtros, independentes da aba). Cada parte =
    SimpleNamespace(dim, label, valor)."""
    partes = []
    if "agrupamento" in escopo_aceito and filtros.get("agrupamento_id"):
        nome = next((a.nome for a in agrupamentos if str(a.id) == filtros["agrupamento_id"]), None)
        if nome:
            partes.append(SimpleNamespace(dim="agrupamento", label="Agrupamento", valor=nome))
    if "local" in escopo_aceito and filtros.get("local_id"):
        nome = next((x.nome for x in lojas_header if str(x.id) == filtros["local_id"]), None)
        if nome:
            partes.append(SimpleNamespace(dim="local", label="Loja", valor=nome))
    if "periodo" in escopo_aceito and filtros.get("periodo"):
        partes.append(
            SimpleNamespace(
                dim="periodo",
                label="Período",
                valor=_PERIODO_LABELS.get(filtros["periodo"], filtros["periodo"]),
            )
        )
    return partes


_VIS_SORT = {
    "detratores": lambda x: -x.detrator,
    "conversiveis": lambda x: -x.conversivel,
    "promotores": lambda x: -x.promotor,
}


def _explorar_locais_ranking(s, empresa_id, ag_id=None, corte=None, vis="todos"):
    """Ranking de locais (tabela densa). Mix prom/conv/det + ratio + faixa +
    % impacto (peso no total da empresa). Ordenação conforme ``vis``:
    todos→ratio asc (pior primeiro); det/conv/prom→volume desc do tipo."""
    from sqlalchemy import func

    from src.api.painel import calcular_ratio, faixa_ratio
    from src.models.local import Local
    from src.models.verbatim import Verbatim

    q = (
        s.query(Verbatim.local_id, Verbatim.tipo, func.count(Verbatim.id))
        .filter(Verbatim.empresa_id == empresa_id, Verbatim.local_id.isnot(None))
        .group_by(Verbatim.local_id, Verbatim.tipo)
    )
    if ag_id is not None:
        locais_ag = [
            lid
            for (lid,) in s.query(Local.id)
            .filter_by(empresa_id=empresa_id, agrupamento_id=ag_id)
            .all()
        ]
        q = q.filter(Verbatim.local_id.in_(locais_ag or [-1]))
    if corte is not None:
        q = q.filter(Verbatim.data_criacao_original >= corte)

    por_local = {}
    for lid, tipo, n in q.all():
        d = por_local.setdefault(lid, {"promotor": 0, "conversivel": 0, "detrator": 0})
        if tipo in d:
            d[tipo] += int(n)
    if not por_local:
        return SimpleNamespace(linhas=[], total_geral=0, vis=vis)
    locs = {x.id: x for x in s.query(Local).filter(Local.id.in_(por_local)).all()}
    linhas = []
    for lid, d in por_local.items():
        prom, conv, detr = d["promotor"], d["conversivel"], d["detrator"]
        total = prom + conv + detr
        if total == 0:  # só verbatins sem classificação → sem sinal p/ ranquear
            continue
        loc = locs.get(lid)
        ratio = calcular_ratio(prom, detr)
        linhas.append(
            SimpleNamespace(
                id=lid,
                nome=loc.nome if loc else f"loja {lid}",
                cidade=(loc.cidade if loc else None),
                total=total,
                promotor=prom,
                conversivel=conv,
                detrator=detr,
                ratio=ratio,
                faixa=faixa_ratio(ratio),
            )
        )
    total_geral = sum(x.total for x in linhas) or 1
    max_total = max((x.total for x in linhas), default=1)
    for x in linhas:
        x.pct = round(x.total / total_geral * 100, 1)  # peso real no total da empresa
        x.bar = round(x.total / max_total * 100)  # largura relativa (maior = barra cheia)
    linhas.sort(key=_VIS_SORT.get(vis, lambda x: (x.ratio, -x.total)))
    return SimpleNamespace(linhas=linhas, total_geral=total_geral, vis=vis)


def _explorar_loja_detratores(s, empresa_id, local_id, corte=None, limit=5):
    """Até ``limit`` detratores mais recentes de um local (p/ o drill)."""
    from src.models.fonte import Fonte
    from src.models.verbatim import Verbatim

    q = (
        s.query(
            Verbatim.id,
            Verbatim.texto,
            Verbatim.subpilar,
            Verbatim.data_criacao_original,
            Fonte.conector_tipo,
        )
        .outerjoin(Fonte, Fonte.id == Verbatim.fonte_id)
        .filter(
            Verbatim.empresa_id == empresa_id,
            Verbatim.local_id == local_id,
            Verbatim.tipo == "detrator",
            Verbatim.tem_texto.is_(True),
        )
        .order_by(Verbatim.data_criacao_original.desc())
    )
    if corte is not None:
        q = q.filter(Verbatim.data_criacao_original >= corte)
    out = []
    for vid, texto, sub, data, fonte in q.limit(limit).all():
        out.append(
            SimpleNamespace(
                id=vid,
                texto=(texto or "")[:200],
                subpilar=sub,
                fonte=fonte,
                data=data,
            )
        )
    return out


def _explorar_loja_subpilares(s, empresa_id, local_id, corte=None):
    """Quebra por subpilar de um local (para o drill-down)."""
    from sqlalchemy import func

    from src.api.painel import NOME_SUBPILAR, SUBPILARES_ORDEM, calcular_ratio, faixa_ratio
    from src.models.verbatim import Verbatim

    q = (
        s.query(Verbatim.subpilar, Verbatim.tipo, func.count(Verbatim.id))
        .filter(
            Verbatim.empresa_id == empresa_id,
            Verbatim.local_id == local_id,
            Verbatim.subpilar.isnot(None),
        )
        .group_by(Verbatim.subpilar, Verbatim.tipo)
    )
    if corte is not None:
        q = q.filter(Verbatim.data_criacao_original >= corte)
    por_sub = {}
    for sub, tipo, n in q.all():
        d = por_sub.setdefault(sub, {"promotor": 0, "conversivel": 0, "detrator": 0})
        if tipo in d:
            d[tipo] += int(n)
    out = []
    for sub in SUBPILARES_ORDEM:
        if sub not in por_sub:
            continue
        d = por_sub[sub]
        prom, conv, detr = d["promotor"], d["conversivel"], d["detrator"]
        ratio = calcular_ratio(prom, detr)
        out.append(
            SimpleNamespace(
                subpilar=sub,
                nome=NOME_SUBPILAR.get(sub, sub),
                total=prom + conv + detr,
                promotor=prom,
                conversivel=conv,
                detrator=detr,
                ratio=ratio,
                faixa=faixa_ratio(ratio),
            )
        )
    return out


def _hm_valor(metrica, prom, conv, detr, total):
    """Valor numérico da célula conforme a métrica (espelha o v2)."""
    from src.api.painel import calcular_ratio

    if metrica == "detratores":
        return detr
    if metrica == "conversiveis":
        return conv
    if metrica == "pct_det":
        return round(100 * detr / total, 1) if total else 0.0
    return calcular_ratio(prom, detr)  # ratio (default)


def _hm_estilo(metrica, val, vmax, has_data):
    """Cor contínua normalizada por vmax (v2): ratio alto=verde / baixo=vermelho;
    demais métricas: alto=vermelho mais forte. Devolve (style_inline, display)."""
    if not has_data:
        return "background:#fafafa;color:#cbd5e1", ""
    t = min(1.0, val / vmax) if vmax else 0.0
    if metrica == "ratio":
        r_, g, b = round(250 - 200 * t), round(180 + 50 * t), round(180 + 30 * t)
        fg = "#fff" if t > 0.6 else "#444"
        return f"background:rgb({r_},{g},{b});color:{fg}", f"{val:.1f}"
    red, gb = round(255 - 50 * t), round(245 - 180 * t)
    fg = "#fff" if t > 0.4 else "#555"
    disp = f"{round(val)}%" if metrica == "pct_det" else (f"{int(val)}" if val else "")
    return f"background:rgb({red},{gb},{gb});color:{fg}", disp


def _explorar_heatmap(s, empresa_id, ag_id=None, corte=None, eixo="loja", metrica="ratio", topn=20):
    """Matriz subpilar × (loja|fonte). Colunas = top-N por volume. Cor contínua
    normalizada pelo máximo da matriz (estilo v2). Cada célula leva o drill p/
    Verbatins (subpilar × eixo)."""
    from sqlalchemy import func

    from src.api.painel import NOME_SUBPILAR, SUBPILARES_ORDEM
    from src.models.fonte import Fonte
    from src.models.local import Local
    from src.models.verbatim import Verbatim

    col_attr = Verbatim.local_id if eixo == "loja" else Verbatim.fonte_id
    q = (
        s.query(col_attr, Verbatim.subpilar, Verbatim.tipo, func.count(Verbatim.id))
        .filter(
            Verbatim.empresa_id == empresa_id,
            col_attr.isnot(None),
            Verbatim.subpilar.isnot(None),
        )
        .group_by(col_attr, Verbatim.subpilar, Verbatim.tipo)
    )
    if ag_id is not None:  # restringe a locais do agrupamento (vale p/ os dois eixos)
        locais_ag = [
            lid
            for (lid,) in s.query(Local.id)
            .filter_by(empresa_id=empresa_id, agrupamento_id=ag_id)
            .all()
        ]
        q = q.filter(Verbatim.local_id.in_(locais_ag or [-1]))
    if corte is not None:
        q = q.filter(Verbatim.data_criacao_original >= corte)

    cells = {}
    col_total = {}
    for col, sub, tipo, n in q.all():
        d = cells.setdefault((col, sub), {"promotor": 0, "conversivel": 0, "detrator": 0})
        if tipo in d:
            d[tipo] += int(n)
        col_total[col] = col_total.get(col, 0) + int(n)
    if not col_total:
        return {"linhas": [], "colunas": [], "eixo": eixo, "metrica": metrica, "topn": topn}

    ordenadas = sorted(col_total.items(), key=lambda kv: -kv[1])
    top_cols = [c for c, _ in (ordenadas if topn is None else ordenadas[:topn])]
    if eixo == "loja":
        nomes = {x.id: x.nome for x in s.query(Local).filter(Local.id.in_(top_cols)).all()}
    else:
        nomes = {x.id: x.conector_tipo for x in s.query(Fonte).filter(Fonte.id.in_(top_cols)).all()}
    colunas = [
        SimpleNamespace(id=c, nome=nomes.get(c, str(c)), total=col_total[c]) for c in top_cols
    ]
    subs_present = [sub for sub in SUBPILARES_ORDEM if any((c, sub) in cells for c in top_cols)]

    # 1ª passada: valores numéricos + vmax (p/ normalizar a cor).
    valores = {}
    vmax = 0.0
    for sub in subs_present:
        for c in top_cols:
            d = cells.get((c, sub))
            if d is None:
                continue
            prom, conv, detr = d["promotor"], d["conversivel"], d["detrator"]
            total = prom + conv + detr
            val = _hm_valor(metrica, prom, conv, detr, total)
            valores[(sub, c)] = (val, prom, conv, detr, total)
            if val > vmax:
                vmax = val

    # 2ª passada: monta as linhas com cor + display + tooltip + drill.
    linhas = []
    for sub in subs_present:
        row = []
        for c in top_cols:
            cell = valores.get((sub, c))
            if cell is None:
                style, disp = _hm_estilo(metrica, 0, vmax, False)
                row.append(
                    {"col_id": c, "sub": sub, "style": style, "v": disp, "title": "sem dados"}
                )
                continue
            val, prom, conv, detr, total = cell
            style, disp = _hm_estilo(metrica, val, vmax, True)
            titulo = (
                f"{sub} × {nomes.get(c, c)} — "
                f"det {detr} · conv {conv} · prom {prom} · total {total}"
            )
            row.append({"col_id": c, "sub": sub, "style": style, "v": disp, "title": titulo})
        linhas.append(SimpleNamespace(sub=sub, nome=NOME_SUBPILAR.get(sub, sub), cells=row))
    return {"linhas": linhas, "colunas": colunas, "eixo": eixo, "metrica": metrica, "topn": topn}


def _explorar_comparar_opcoes(s, empresa_id, ag_id=None, corte=None, tipo_elemento="loja"):
    """Opções selecionáveis: lojas (top 80 por volume) ou os 12 subpilares."""
    if tipo_elemento == "subpilar":
        from src.api.painel import NOME_SUBPILAR, SUBPILARES_ORDEM

        return [
            SimpleNamespace(v=sp, label=f"{sp} · {NOME_SUBPILAR.get(sp, sp)}")
            for sp in SUBPILARES_ORDEM
        ]
    from sqlalchemy import func

    from src.models.local import Local
    from src.models.verbatim import Verbatim

    q = (
        s.query(Verbatim.local_id, func.count(Verbatim.id))
        .filter(Verbatim.empresa_id == empresa_id, Verbatim.local_id.isnot(None))
        .group_by(Verbatim.local_id)
    )
    if ag_id is not None:
        locais_ag = [
            lid
            for (lid,) in s.query(Local.id)
            .filter_by(empresa_id=empresa_id, agrupamento_id=ag_id)
            .all()
        ]
        q = q.filter(Verbatim.local_id.in_(locais_ag or [-1]))
    if corte is not None:
        q = q.filter(Verbatim.data_criacao_original >= corte)
    tot_by = {lid: int(n) for lid, n in q.all()}
    if not tot_by:
        return []
    nomes = {x.id: x.nome for x in s.query(Local).filter(Local.id.in_(tot_by)).all()}
    ordenadas = sorted(tot_by.items(), key=lambda kv: -kv[1])[:80]
    return [
        SimpleNamespace(v=str(lid), label=f"{nomes.get(lid, lid)} ({n})") for lid, n in ordenadas
    ]


def _comparar_sparkline(s, empresa_id, el, tipo_elemento, locais_ag, corte):
    """Série de ratio por trimestre (p/ o sparkline). Devolve (ratios, labels)."""
    from sqlalchemy import func

    from src.api.painel import calcular_ratio
    from src.models.verbatim import Verbatim
    from src.utils.sql import fmt_ano_mes

    mes = fmt_ano_mes(Verbatim.data_criacao_original)
    q = s.query(mes, Verbatim.tipo, func.count(Verbatim.id)).filter(
        Verbatim.empresa_id == empresa_id, Verbatim.data_criacao_original.isnot(None)
    )
    if tipo_elemento == "loja":
        if not el.isdigit():
            return [], []
        q = q.filter(Verbatim.local_id == int(el))
    else:
        q = q.filter(Verbatim.subpilar == el)
        if locais_ag is not None:
            q = q.filter(Verbatim.local_id.in_(locais_ag))
    if corte is not None:
        q = q.filter(Verbatim.data_criacao_original >= corte)

    by_q = {}
    for m, tipo, n in q.group_by(mes, Verbatim.tipo).all():
        if not m:
            continue
        y, mo = m.split("-")
        chave = f"{y}-T{(int(mo) - 1) // 3 + 1}"
        d = by_q.setdefault(chave, {"promotor": 0, "detrator": 0})
        if tipo in d:
            d[tipo] += int(n)
    labels = sorted(by_q)
    ratios = [round(calcular_ratio(by_q[k]["promotor"], by_q[k]["detrator"]), 2) for k in labels]
    return ratios, labels


def _spark_points(serie):
    """Pontos do polyline SVG (viewBox 0 0 100 32), normalização do v2."""
    vals = [v for v in serie if v is not None]
    if len(vals) < 2:
        return ""
    vmax = max(vals + [2.0])
    vmin = min(vals + [0.0])
    span = (vmax - vmin) or 1
    n = len(serie)
    pts = []
    for i, v in enumerate(serie):
        if v is None:
            continue
        x = (i / (n - 1)) * 100 if n > 1 else 0
        y = 30 - ((v - vmin) / span) * 28
        pts.append(f"{x:.1f},{y:.1f}")
    return " ".join(pts)


def _comparar_distribuicao(s, empresa_id, el, tipo_elemento, locais_ag, corte, limite=6):
    """Distribuição do elemento: por subpilar (se loja) ou por loja (se subpilar).
    Top-N por volume, com mini-barras det/prom relativas ao maior total."""
    from sqlalchemy import func

    from src.api.painel import NOME_SUBPILAR
    from src.models.local import Local
    from src.models.verbatim import Verbatim

    if tipo_elemento == "loja":
        if not el.isdigit():
            return []
        chave = Verbatim.subpilar
        q = s.query(chave, Verbatim.tipo, func.count(Verbatim.id)).filter(
            Verbatim.empresa_id == empresa_id,
            Verbatim.local_id == int(el),
            Verbatim.subpilar.isnot(None),
        )
    else:
        chave = Verbatim.local_id
        q = s.query(chave, Verbatim.tipo, func.count(Verbatim.id)).filter(
            Verbatim.empresa_id == empresa_id,
            Verbatim.subpilar == el,
            Verbatim.local_id.isnot(None),
        )
        if locais_ag is not None:
            q = q.filter(Verbatim.local_id.in_(locais_ag))
    if corte is not None:
        q = q.filter(Verbatim.data_criacao_original >= corte)

    agg = {}
    for k, tipo, n in q.group_by(chave, Verbatim.tipo).all():
        d = agg.setdefault(k, {"det": 0, "prom": 0, "tot": 0})
        d["tot"] += int(n)
        if tipo == "detrator":
            d["det"] += int(n)
        elif tipo == "promotor":
            d["prom"] += int(n)
    if not agg:
        return []
    if tipo_elemento == "loja":
        rotulos = {k: f"{k} · {NOME_SUBPILAR.get(k, k)}" for k in agg}
    else:
        ids = [k for k in agg if k is not None]
        nomes = {x.id: x.nome for x in s.query(Local).filter(Local.id.in_(ids)).all()}
        rotulos = {k: nomes.get(k, f"loja {k}") for k in agg}
    itens = sorted(agg.items(), key=lambda kv: -kv[1]["tot"])[:limite]
    maxt = max((v["tot"] for _, v in itens), default=1) or 1
    return [
        SimpleNamespace(
            rotulo=rotulos.get(k, str(k)),
            det=v["det"],
            prom=v["prom"],
            tot=v["tot"],
            det_w=round(v["det"] / maxt * 100),
            prom_w=round(v["prom"] / maxt * 100),
        )
        for k, v in itens
    ]


def _explorar_comparar(s, empresa_id, ag_id=None, corte=None, tipo_elemento="loja", elementos=None):
    """KPIs por elemento (2-3 lojas ou subpilares) p/ comparação lado a lado.
    PASSO 3: + sparkline de ratio trimestral + distribuição (subpilar↔loja)."""
    from sqlalchemy import func

    from src.api.painel import NOME_SUBPILAR, calcular_ratio, faixa_ratio
    from src.models.local import Local
    from src.models.verbatim import Verbatim

    elementos = [e for e in (elementos or []) if e][:3]
    if not elementos:
        return []
    locais_ag = None
    if ag_id is not None:
        locais_ag = [
            lid
            for (lid,) in s.query(Local.id)
            .filter_by(empresa_id=empresa_id, agrupamento_id=ag_id)
            .all()
        ] or [-1]
    nomes = {}
    if tipo_elemento == "loja":
        ids = [int(e) for e in elementos if e.isdigit()]
        nomes = {x.id: x.nome for x in s.query(Local).filter(Local.id.in_(ids)).all()}

    cards = []
    for el in elementos:
        q = s.query(Verbatim.tipo, func.count(Verbatim.id)).filter(
            Verbatim.empresa_id == empresa_id
        )
        if tipo_elemento == "loja":
            if not el.isdigit():
                continue
            q = q.filter(Verbatim.local_id == int(el))
            label = nomes.get(int(el), f"loja {el}")
        else:
            q = q.filter(Verbatim.subpilar == el)
            if locais_ag is not None:
                q = q.filter(Verbatim.local_id.in_(locais_ag))
            label = f"{el} · {NOME_SUBPILAR.get(el, el)}"
        if corte is not None:
            q = q.filter(Verbatim.data_criacao_original >= corte)
        d = {"promotor": 0, "conversivel": 0, "detrator": 0}
        for tipo, n in q.group_by(Verbatim.tipo).all():
            if tipo in d:
                d[tipo] = int(n)
        prom, conv, detr = d["promotor"], d["conversivel"], d["detrator"]
        total = prom + conv + detr
        ratio = calcular_ratio(prom, detr)
        sparkline, buckets = _comparar_sparkline(s, empresa_id, el, tipo_elemento, locais_ag, corte)
        cards.append(
            SimpleNamespace(
                elemento=el,
                label=label,
                total=total,
                promotor=prom,
                conversivel=conv,
                detrator=detr,
                ratio=ratio,
                faixa=faixa_ratio(ratio),
                pct_det=round(100 * detr / total, 1) if total else 0.0,
                pct_conv=round(100 * conv / total, 1) if total else 0.0,
                sparkline=sparkline,
                buckets=buckets,
                spark_points=_spark_points(sparkline),
                distribuicao=_comparar_distribuicao(
                    s, empresa_id, el, tipo_elemento, locais_ag, corte
                ),
                dist_label="Subpilares" if tipo_elemento == "loja" else "Locais",
            )
        )
    return cards


def _ev_bucket(periodo, granularidade):
    """'YYYY-MM' → rótulo do bucket conforme granularidade."""
    y, m = periodo.split("-")
    mi = int(m)
    if granularidade == "trimestre":
        return f"{y}-T{(mi - 1) // 3 + 1}"
    if granularidade == "semestre":
        return f"{y}-S{(mi - 1) // 6 + 1}"
    return periodo


def _explorar_evolucao_opcoes(s, empresa_id, ag_id, corte, agrupar_por):
    """Valores selecionáveis para a série, conforme agrupar_por."""
    if agrupar_por in ("loja", "subpilar"):
        return _explorar_comparar_opcoes(s, empresa_id, ag_id, corte, agrupar_por)
    if agrupar_por == "agrupamento":
        from src.models.agrupamento import Agrupamento

        ags = s.query(Agrupamento).filter_by(empresa_id=empresa_id).order_by(Agrupamento.nome).all()
        return [SimpleNamespace(v=str(a.id), label=a.nome) for a in ags]
    return []  # empresa (total) — sem seleção


def _explorar_evolucao(
    s, empresa_id, ag_id=None, corte=None, granularidade="mes", agrupar_por="empresa", valores=None
):
    """Série temporal de ratio a partir de ``ratios_mensais`` (ML CP-2). Agrega
    por bucket (mês/trimestre/semestre) × grupo (empresa/subpilar/loja/agrupamento),
    null em buckets vazios (gap). Sem seleção explícita → top-5 grupos por volume.
    Guarda de frescor: popula ratios_mensais se estiver vazia."""
    from src.api.painel import NOME_SUBPILAR, calcular_ratio
    from src.models.agrupamento import Agrupamento
    from src.models.anomalia import RatioMensal
    from src.models.local import Local

    if s.query(RatioMensal.id).filter(RatioMensal.empresa_id == empresa_id).first() is None:
        from src.anomalias.ratios import recomputar_ratios_mensais

        recomputar_ratios_mensais(empresa_id)

    valores = [v for v in (valores or []) if v][:5]
    q = s.query(RatioMensal).filter(RatioMensal.empresa_id == empresa_id)
    if ag_id is not None:
        q = q.filter(RatioMensal.agrupamento_id == ag_id)
    if corte is not None:
        q = q.filter(RatioMensal.periodo >= corte.strftime("%Y-%m"))
    if agrupar_por == "subpilar" and valores:
        q = q.filter(RatioMensal.subpilar.in_(valores))
    elif agrupar_por == "loja" and valores:
        q = q.filter(RatioMensal.local_id.in_([int(v) for v in valores if v.isdigit()]))
    elif agrupar_por == "agrupamento" and valores:
        q = q.filter(RatioMensal.agrupamento_id.in_([int(v) for v in valores if v.isdigit()]))

    agg = {}
    grupos = set()
    for r in q.all():
        b = _ev_bucket(r.periodo, granularidade)
        if agrupar_por == "subpilar":
            g = r.subpilar
        elif agrupar_por == "loja":
            g = r.local_id
        elif agrupar_por == "agrupamento":
            g = r.agrupamento_id
        else:
            g = ""
        if g is None:
            continue
        grupos.add(g)
        d = agg.setdefault((b, g), {"prom": 0, "det": 0, "tot": 0})
        d["prom"] += r.promotor or 0
        d["det"] += r.detrator or 0
        d["tot"] += r.total or 0

    buckets = sorted({b for (b, _) in agg})
    if agrupar_por == "loja":
        nomes = {x.id: x.nome for x in s.query(Local).filter(Local.id.in_(list(grupos))).all()}
    elif agrupar_por == "agrupamento":
        nomes = {
            x.id: x.nome
            for x in s.query(Agrupamento).filter(Agrupamento.id.in_(list(grupos))).all()
        }
    else:
        nomes = {}

    grupos_ord = sorted(
        grupos, key=lambda g: -sum(agg[(b, g)]["tot"] for b in buckets if (b, g) in agg)
    )
    if agrupar_por != "empresa" and not valores:
        grupos_ord = grupos_ord[:5]  # default: top-5 por volume p/ não poluir

    series = []
    for g in grupos_ord:
        if agrupar_por == "empresa":
            label = "Empresa (total)"
        elif agrupar_por == "subpilar":
            label = f"{g} · {NOME_SUBPILAR.get(g, g)}"
        else:
            label = nomes.get(g, str(g))
        ratio, det, prom, tot = [], [], [], []
        for b in buckets:
            d = agg.get((b, g))
            if d is None or d["tot"] == 0:
                ratio.append(None)
                det.append(0)
                prom.append(0)
                tot.append(0)
            else:
                ratio.append(calcular_ratio(d["prom"], d["det"]))
                det.append(d["det"])
                prom.append(d["prom"])
                tot.append(d["tot"])
        series.append(
            {"label": label, "ratio": ratio, "detratores": det, "promotores": prom, "total": tot}
        )
    return {"buckets": buckets, "series": series}


def _escopo_loja(s, empresa_id, ag_id, local_id, modelo):
    """Resolve o escopo efetivo + monta o banner de herança (Bloco 9 CP-A4).
    Retorna (eff_ag, eff_local, escopo) onde escopo descreve transparentemente o
    que está sendo exibido (próprio da loja ou herdado, e por quê)."""
    from src.diagnostico.leituras import loja_qualifica, resolver_escopo
    from src.models.local import Local

    if local_id is None:
        return ag_id, None, None
    loc = s.get(Local, local_id)
    loja_ag = loc.agrupamento_id if loc else ag_id
    loja_nome = loc.nome if loc else f"loja {local_id}"
    r = resolver_escopo(s, modelo, empresa_id, ag_id=loja_ag, local_id=local_id)
    if r["origem"] == "loja":
        escopo = SimpleNamespace(herdado=False, loja_nome=loja_nome, origem="loja")
        return None, local_id, escopo
    # Herdou: o pedido era loja, mas o material exibido é do agrupamento/empresa.
    qualifica = loja_qualifica(s, empresa_id, local_id)
    from sqlalchemy import func

    from src.models.verbatim import Verbatim

    vol = (
        s.query(func.count(Verbatim.id))
        .filter(
            Verbatim.empresa_id == empresa_id,
            Verbatim.local_id == local_id,
            Verbatim.subpilar.isnot(None),
        )
        .scalar()
        or 0
    )
    escopo = SimpleNamespace(
        herdado=True,
        loja_nome=loja_nome,
        origem=r["origem"],  # "agrupamento" | "empresa" | None
        qualifica=qualifica,
        volume=vol,
        # "em_geracao": qualifica mas ainda sem material próprio (próximo ciclo);
        # "volume_insuficiente": não atinge o gate de 30.
        motivo=("em_geracao" if qualifica else "volume_insuficiente"),
    )
    return r["ag"], r["local"], escopo


def _explorar_diagnostico(s, empresa_id, ag_id, local_id=None):
    """Mapa de Lastro (4 pilares) + Confronto Visual (12 subpilares) + leitura/ação
    do cache. Holístico (período não se aplica). ``local_id``: escopo loja com
    herança transparente loja→agrupamento→empresa (CP-A4)."""
    from src.api.painel import (
        NOME_PILAR,
        NOME_SUBPILAR,
        PILAR_DE_SUBPILAR,
        PILARES_ORDEM,
        SUBPILARES_ORDEM,
        calcular_ratio,
        faixa_ratio,
    )
    from src.diagnostico.leituras import (
        _gargalo,
        _scope_cond,
        agregar_subpilares,
        resolver_escopo,
    )
    from src.models.diagnostico import LeituraDiagnostico
    from src.models.local import Local

    def _leituras(ag, loc):
        return {
            r.subpilar: r
            for r in s.query(LeituraDiagnostico)
            .filter(
                LeituraDiagnostico.empresa_id == empresa_id,
                *_scope_cond(LeituraDiagnostico, ag, loc),
            )
            .all()
        }

    escopo = None
    herdado_sub = {}  # subpilar -> origem do pai (str) quando herdado; ausente = próprio
    if local_id is not None:
        # Números = sempre da própria loja (com selo de volume por subpilar).
        agg = agregar_subpilares(s, empresa_id, None, local_id)
        loja_lt = _leituras(None, local_id)  # próprias (só subpilares ≥30)
        loc = s.get(Local, local_id)
        loja_ag = loc.agrupamento_id if loc else ag_id
        # Pai para herança dos subpilares ralos (agrupamento se tiver, senão empresa).
        par = resolver_escopo(s, LeituraDiagnostico, empresa_id, ag_id=loja_ag, local_id=None)
        par_lt = _leituras(par["ag"], None) if par["origem"] else {}
        leituras = {}
        for sub in agg:
            if sub in loja_lt:
                leituras[sub] = loja_lt[sub]  # próprio
            elif sub in par_lt:
                leituras[sub] = par_lt[sub]
                herdado_sub[sub] = par["origem"]  # herdado do pai
        escopo = SimpleNamespace(
            loja=True,
            loja_nome=(loc.nome if loc else f"loja {local_id}"),
            origem_pai=par["origem"],
            n_proprios=sum(1 for sub in agg if sub in loja_lt),
            n_herdados=len(herdado_sub),
        )
    else:
        agg = agregar_subpilares(s, empresa_id, ag_id)
        leituras = _leituras(ag_id, None)

    gargalo = _gargalo(agg)

    # Proximity por subpilar (CP-LG-4, leitura) do escopo do diagnóstico.
    # NÃO herda do pai: mostra a Proximity própria do escopo (NULL no subpilar
    # abaixo do floor de 10, mesmo que o ratio apareça — métricas com pisos
    # distintos: ratio em qualquer volume, Proximity só com ≥10).
    from src.governanca.leitura import garantir_governanca, proximity_subpilares_escopo

    garantir_governanca(empresa_id)
    if local_id is not None:
        _g_tipo, _g_id = "loja", local_id
    elif ag_id is not None:
        _g_tipo, _g_id = "agrupamento", ag_id
    else:
        _g_tipo, _g_id = "empresa", None
    prox_sub = proximity_subpilares_escopo(s, empresa_id, _g_tipo, _g_id)

    # R$ de ESTOQUE por subpilar (CP-impacto-rs): conversíveis × LTV_loja no grão
    # (loja, subpilar), no MESMO escopo do diagnóstico. None → "—" honesto.
    from src.governanca.impacto_rs import formatar_estoque, rs_estoque

    _estoque = rs_estoque(s, empresa_id, ag_id, local_id)

    confronto = []
    for sub in SUBPILARES_ORDEM:
        d = agg.get(sub)
        if d is None:
            continue
        lt = leituras.get(sub)
        px = prox_sub.get(sub, {"valor": None, "faixa": None})
        confronto.append(
            SimpleNamespace(
                subpilar=sub,
                nome=NOME_SUBPILAR.get(sub, sub),
                det=d["det"],
                conv=d["conv"],
                prom=d["prom"],
                ratio=d["ratio"],
                faixa=d["faixa"],
                proximity=px["valor"],
                proximity_faixa=px["faixa"],
                rs_estoque=formatar_estoque(_estoque.get(sub)),
                leitura=(lt.leitura if lt else None),
                acao=(lt.acao if lt else None),
                herdado=herdado_sub.get(sub),  # None = próprio; str = origem do pai
            )
        )

    pilares = []
    for p in PILARES_ORDEM:
        subs = [x for x in SUBPILARES_ORDEM if PILAR_DE_SUBPILAR.get(x) == p and x in agg]
        if not subs:
            continue
        prom = sum(agg[x]["prom"] for x in subs)
        conv = sum(agg[x]["conv"] for x in subs)
        det = sum(agg[x]["det"] for x in subs)
        ratio = calcular_ratio(prom, det)
        pilares.append(
            SimpleNamespace(
                pilar=p,
                nome=NOME_PILAR.get(p, p),
                ratio=ratio,
                faixa=faixa_ratio(ratio),
                total=prom + conv + det,
                prom=prom,
                conv=conv,
                det=det,
                gargalo=(p == gargalo),
                subpilares=[
                    SimpleNamespace(
                        subpilar=x,
                        nome=NOME_SUBPILAR.get(x, x),
                        ratio=agg[x]["ratio"],
                        faixa=agg[x]["faixa"],
                    )
                    for x in subs
                ],
            )
        )

    ultima = max((r.gerado_em for r in leituras.values()), default=None)
    return SimpleNamespace(
        pilares=pilares,
        gargalo=gargalo,
        confronto=confronto,
        tem_leituras=bool(leituras),
        ultima_geracao=ultima,
        regen_msg=None,
        escopo=escopo,
    )


def _explorar_governanca(s, empresa_id, ag_id=None):
    """Painel de Governança (CP-LG-8, board view). Levas 1-3: cobertura + radar +
    concentração + previsibilidade + ranking + simulação de cenários + projeção
    financeira. Tudo leitura (simulação é projeção efêmera sobre cópia)."""
    from src.api.painel import NOME_SUBPILAR
    from src.diagnostico.leituras import agregar_subpilares
    from src.governanca.leitura import (
        cobertura_governanca,
        distribuicao_previsibilidade,
        distribuicao_selos,
        garantir_governanca,
        gini_escopo,
        leitura_concentracao,
        proximity_pilares_escopo,
        radar_svg_data,
        ranking_lojas_governanca,
    )
    from src.governanca.metricas import compor_cenario, ordenar_acoes_cenario
    from src.planos.consolidar import consolidar_acoes

    garantir_governanca(empresa_id)
    escopo_tipo = "agrupamento" if ag_id else "empresa"
    escopo_id = ag_id if ag_id else None
    pilares = proximity_pilares_escopo(s, empresa_id, escopo_tipo, escopo_id)
    gini = gini_escopo(s, empresa_id, escopo_tipo, escopo_id)
    top5 = gini["lojas"][:5] if gini and not gini.get("insuficiente") else []

    # Bloco 5 — Simulação de Cenários (efêmera; dedupe por subpilar; ordem fixa).
    agg = agregar_subpilares(s, empresa_id, ag_id, None)
    cf = {"agrupamento_id": ag_id} if ag_id else {}
    subpilares_alta = [
        it.subpilar
        for it in consolidar_acoes(empresa_id, cf)
        if getattr(it, "prioridade", None) == "alto" and getattr(it, "subpilar", None)
    ]
    ordenados, lifts = ordenar_acoes_cenario(agg, subpilares_alta)
    range_max = len(ordenados)
    try:
        n = int(request.args.get("cenario_n", min(3, range_max)))
    except (TypeError, ValueError):
        n = min(3, range_max)
    n = max(0, min(n, range_max))
    cenario = compor_cenario(agg, ordenados, n) if range_max else None
    if cenario is not None:
        from src.api.painel import NOME_PILAR, PILAR_DE_SUBPILAR

        cenario["range_max"] = range_max
        cenario["aplicados_nome"] = [
            {**a, "nome": NOME_SUBPILAR.get(a["subpilar"], a["subpilar"])}
            for a in cenario["aplicados"]
        ]
        # Insight do TETO: Índice máximo do plano completo + gargalo remanescente
        # e se alguma ação alta o endereça (senão: 'plano não toca o gargalo').
        teto = compor_cenario(agg, ordenados, range_max)
        pilares_alta = {PILAR_DE_SUBPILAR.get(sub) for sub in ordenados}
        gp = teto["gargalo_pilar"]
        cenario["teto"] = {
            "indice": teto["indice_n"],
            "atingido": cenario["indice_n"] >= teto["indice_n"] - 1e-9,
            "gargalo_pilar": gp,
            "gargalo_nome": NOME_PILAR.get(gp, gp),
            "gargalo_coberto": gp in pilares_alta,
        }

    return SimpleNamespace(
        escopo_tipo=escopo_tipo,
        cobertura=cobertura_governanca(s, empresa_id),
        radar=radar_svg_data(pilares),
        pilares=pilares,
        gini=gini,
        leitura_conc=leitura_concentracao(gini),
        top5=top5,
        prev_dist=distribuicao_previsibilidade(s, empresa_id),
        selo_dist=distribuicao_selos(s, empresa_id),
        ranking=ranking_lojas_governanca(s, empresa_id),
        cenario=cenario,
    )


def _explorar_concentracao(s, empresa_id, ag_id=None):
    """Aba Concentração (CP-LG-3): Gini + faixa + leitura + barras + heatmap
    loja×subpilar (LG-3.1). Escopo empresa (ag_id None) ou agrupamento. Leitura."""
    from src.governanca.leitura import (
        garantir_governanca,
        gini_escopo,
        heatmap_detratores,
        heatmap_render,
        leitura_concentracao,
    )

    garantir_governanca(empresa_id)
    escopo_tipo = "agrupamento" if ag_id else "empresa"
    escopo_id = ag_id if ag_id else None
    d = gini_escopo(s, empresa_id, escopo_tipo, escopo_id)
    lojas = (d.get("lojas") if d else None) or []
    barras = lojas[:15]  # top 15 por contribuição; bolsão = primeiras top_n
    # Heatmap (LG-3.1): top 12 lojas × 12 subpilares, modo abs|pct via ?heat=.
    modo = "pct" if request.args.get("heat") == "pct" else "abs"
    hm_dados = heatmap_detratores(s, empresa_id, ag_id, top_n=12)
    return SimpleNamespace(
        dados=d,
        leitura=leitura_concentracao(d),
        barras=barras,
        bolsao_n=(d.get("top_n") if d else None),
        max_det=(barras[0]["detratores"] if barras else 0),
        escopo_tipo=escopo_tipo,
        heatmap=heatmap_render(hm_dados, modo),
        heatmap_dados=hm_dados,
        heatmap_modo=modo,
    )


def _explorar_leaderboard(s, empresa_id, ag_id=None, corte=None, order_by="score"):
    """Ranking de locais por score modulado (CP-E3): score = Índice Geral ×
    (engajamento/100). Três faixas de confiança (limiares = selo): ranking
    principal ≥30 (🟢), 'em formação' 10-30 (🟡), 'insuficiente' <10 (🔴).
    Retorna {ranked, formacao, insuficiente}. Badges só no ranking."""
    from sqlalchemy import func

    from src.api.engajamento import engajamento_por_loja
    from src.api.painel import calcular_indice_geral, calcular_ratio, faixa_ratio
    from src.models.local import Local
    from src.models.verbatim import Verbatim

    q = (
        s.query(Verbatim.local_id, Verbatim.subpilar, Verbatim.tipo, func.count(Verbatim.id))
        .filter(
            Verbatim.empresa_id == empresa_id,
            Verbatim.local_id.isnot(None),
            Verbatim.subpilar.isnot(None),
        )
        .group_by(Verbatim.local_id, Verbatim.subpilar, Verbatim.tipo)
    )
    if ag_id is not None:
        locais_ag = [
            lid
            for (lid,) in s.query(Local.id)
            .filter_by(empresa_id=empresa_id, agrupamento_id=ag_id)
            .all()
        ]
        q = q.filter(Verbatim.local_id.in_(locais_ag or [-1]))
    if corte is not None:
        q = q.filter(Verbatim.data_criacao_original >= corte)

    por_loja = {}
    for lid, sub, tipo, n in q.all():
        d = por_loja.setdefault(lid, {}).setdefault(
            sub, {"promotor": 0, "conversivel": 0, "detrator": 0}
        )
        if tipo in d:
            d[tipo] += int(n)
    if not por_loja:
        return {"ranked": [], "formacao": [], "insuficiente": []}
    nomes = {x.id: x for x in s.query(Local).filter(Local.id.in_(por_loja)).all()}

    linhas = []
    for lid, subs in por_loja.items():
        matriz = []
        prom = conv = det = 0
        for sub, c in subs.items():
            p, cv, dt = c["promotor"], c["conversivel"], c["detrator"]
            matriz.append(
                {
                    "subpilar": sub,
                    "ratio": calcular_ratio(p, dt),
                    "total": p + cv + dt,
                    "promotor": p,
                    "detrator": dt,
                }
            )
            prom += p
            conv += cv
            det += dt
        total = prom + conv + det
        if total == 0:
            continue
        loc = nomes.get(lid)
        ratio = calcular_ratio(prom, det)
        linhas.append(
            SimpleNamespace(
                id=lid,
                nome=loc.nome if loc else f"loja {lid}",
                cidade=loc.cidade if loc else None,
                uf=loc.uf if loc else None,
                score=calcular_indice_geral(matriz),
                ratio=ratio,
                faixa=faixa_ratio(ratio),
                total=total,
                promotor=prom,
                conversivel=conv,
                detrator=det,
                pct_conv=round(100 * conv / total, 1) if total else 0.0,
                badges=[],
            )
        )

    # Engajamento por loja (CP-E3): modula o score e separa por faixa de confiança.
    eng_map = engajamento_por_loja(empresa_id, s, ag_id, corte)
    # Proximity por loja (CP-LG-4, leitura): garante frescor e anexa a cada linha.
    from src.governanca.leitura import garantir_governanca, proximity_por_loja, selos_por_loja

    garantir_governanca(empresa_id)
    prox_map = proximity_por_loja(s, empresa_id)
    selo_map = selos_por_loja(s, empresa_id)
    for x in linhas:
        em = eng_map.get(x.id, {"engajamento": 0, "volume": 0, "selo": "baixa", "selo_emoji": "🔴"})
        x.engajamento = em["engajamento"]
        x.vol_eng = em["volume"]
        x.selo = em["selo"]
        x.selo_emoji = em["selo_emoji"]
        x.score_mod = round(x.score * em["engajamento"] / 100.0, 2)
        pm = prox_map.get(x.id, {"valor": None, "faixa": None, "n_pilares": 0})
        x.proximity = pm["valor"]
        x.proximity_faixa = pm["faixa"]
        x.proximity_n_pilares = pm.get("n_pilares", 0)
        x.selo_qualidade = selo_map.get(x.id)  # ouro|prata|bronze|None (CP-LG-6)

    # 3 faixas pelo nível do selo (≥30 🟢 / 10-30 🟡 / <10 🔴).
    ranked = [x for x in linhas if x.selo == "alta"]
    formacao = [x for x in linhas if x.selo == "media"]
    insuficiente = [x for x in linhas if x.selo == "baixa"]

    # Badges on-the-fly — só no ranking (deterministas dos agregados atuais).
    if ranked:
        max(ranked, key=lambda x: x.ratio).badges.append(("🏆", "Melhor ratio"))
        max(ranked, key=lambda x: x.total).badges.append(("📊", "Volume líder"))
        melhor_conv = max(ranked, key=lambda x: x.pct_conv)
        if melhor_conv.conversivel > 0:
            melhor_conv.badges.append(("🔄", "Maior conversão"))
        for x in ranked:
            if x.detrator == 0 and x.total >= 5:
                x.badges.append(("✨", "Zero detratores"))

    chave = {
        "ratio": lambda x: -x.ratio,
        "volume": lambda x: -x.total,
        # Proximity desc; lojas sem dado (NULL) sempre por último.
        "proximity": lambda x: (x.proximity is None, -(x.proximity or 0.0)),
    }.get(order_by, lambda x: (-x.score_mod, -x.total))
    for grupo in (ranked, formacao, insuficiente):
        grupo.sort(key=chave)
    return {"ranked": ranked, "formacao": formacao, "insuficiente": insuficiente}


_PERSP_LABELS = [
    ("marketing", "Marketing & Comunicação"),
    ("produto_preco", "Produto & Preço"),
    ("tecnologia", "Tecnologia & Inovação"),
    ("processos", "Processos & Operação"),
    ("pessoas", "Pessoas & Cultura"),
    ("ativacao", "Ativação do Cliente"),
]
_PERSP_DICT = dict(_PERSP_LABELS)


def _explorar_planos(empresa_id, ag_id, args):
    """Consolida ações (3 fontes + overlay), agrupa por perspectiva, calcula gargalo
    e lojas p/ filtro. modo cliente/loyall; vista perspectiva/tabela."""
    from src.diagnostico.leituras import _gargalo, agregar_subpilares
    from src.models.local import Local
    from src.planos.consolidar import consolidar_acoes
    from src.utils.db import db_session

    modo = "cliente" if args.get("modo") == "cliente" else "loyall"
    vista = "tabela" if args.get("vista") == "tabela" else "cards"
    filtros = {
        k: (args.get(k) or None) for k in ("perspectiva", "origem", "pilar", "prioridade", "status")
    }
    loja_raw = args.get("local_id")
    if loja_raw and loja_raw.isdigit():
        filtros["local_id"] = int(loja_raw)
    # Pílulas de perspectiva (PL-2): consolida SEM o filtro de perspectiva para
    # contar todas as frentes (contagem estável); a perspectiva ativa recorta só
    # a exibição.
    cf = {k: v for k, v in filtros.items() if k != "perspectiva"}
    if ag_id is not None:
        cf["agrupamento_id"] = ag_id
    itens_all = consolidar_acoes(empresa_id, cf)
    from collections import Counter

    contagem_persp = Counter(it.perspectiva for it in itens_all)
    persp_sel = filtros.get("perspectiva")
    itens = [it for it in itens_all if it.perspectiva == persp_sel] if persp_sel else itens_all

    with db_session() as s:
        gargalo = _gargalo(agregar_subpilares(s, empresa_id, ag_id))

        # CP-LG-5: projeção de impacto por item (efêmera, det→conversível).
        from src.governanca.leitura import anexar_impacto_acoes

        anexar_impacto_acoes(s, empresa_id, itens_all)

        lq = s.query(Local).filter_by(empresa_id=empresa_id)
        if ag_id is not None:
            lq = lq.filter_by(agrupamento_id=ag_id)
        lojas = [SimpleNamespace(id=x.id, nome=x.nome) for x in lq.order_by(Local.nome).all()]
        from src.models.sugestao_estrutural import SugestaoEstrutural

        ultima_geracao = _ultima_geracao(s, SugestaoEstrutural, empresa_id, ag_id)

    grupos = []
    for p, lbl in _PERSP_LABELS:
        g = [it for it in itens if it.perspectiva == p]
        if g:
            estrut = [it for it in g if it.origem == "Estrutural"]
            reat = [it for it in g if it.origem != "Estrutural"]
            grupos.append(
                SimpleNamespace(
                    perspectiva=p, label=lbl, estruturais=estrut, reativas=reat, total=len(g)
                )
            )
    sem = [it for it in itens if it.perspectiva not in _PERSP_DICT]
    if sem:
        grupos.append(
            SimpleNamespace(
                perspectiva=None,
                label="Sem perspectiva",
                estruturais=[it for it in sem if it.origem == "Estrutural"],
                reativas=[it for it in sem if it.origem != "Estrutural"],
                total=len(sem),
            )
        )

    return SimpleNamespace(
        itens=itens,
        grupos=grupos,
        gargalo=gargalo,
        lojas=lojas,
        total=len(itens),
        total_geral=len(itens_all),
        modo=modo,
        vista=vista,
        filtros=filtros,
        perspectivas=_PERSP_LABELS,
        persp_sel=persp_sel,
        contagem_persp=dict(contagem_persp),
        ultima_geracao=ultima_geracao,
        regen_msg=None,
    )


def _ultima_geracao(s, modelo, empresa_id, ag_id):
    """max(gerado_em) das gerações do escopo (p/ rate-limit + 'última geração')."""
    from sqlalchemy import func

    q = s.query(func.max(modelo.gerado_em)).filter(modelo.empresa_id == empresa_id)
    q = q.filter(
        modelo.agrupamento_id.is_(None) if ag_id is None else modelo.agrupamento_id == ag_id
    )
    return q.scalar()


def _explorar_contexto(empresa_id, tab):
    """Monta o contexto comum (empresa, agrupamentos, filtros, dados da tab)."""
    filtros, ag_id, corte = _explorar_filtros()
    with db_session() as s:
        empresa_db = s.get(Empresa, empresa_id)
        if empresa_db is None:
            return None
        empresa_w = _wrap_empresa(empresa_db, _ultima_coleta(s, empresa_id))
        ags = s.query(Agrupamento).filter_by(empresa_id=empresa_id).order_by(Agrupamento.nome).all()
        agrupamentos = [SimpleNamespace(id=a.id, nome=a.nome) for a in ags]
        # Loja como 3º nível do header (CP-A4): lojas do agrupamento selecionado.
        local_id = int(filtros["local_id"]) if filtros["local_id"].isdigit() else None
        lq_header = s.query(Local).filter_by(empresa_id=empresa_id)
        if ag_id is not None:
            lq_header = lq_header.filter_by(agrupamento_id=ag_id)
        lojas_header = [
            SimpleNamespace(id=x.id, nome=x.nome) for x in lq_header.order_by(Local.nome).all()
        ]
        locais = None
        if tab == "locais":
            vis = request.args.get("vis", "todos")
            vis = vis if vis in ("todos", "detratores", "conversiveis", "promotores") else "todos"
            locais = _explorar_locais_ranking(s, empresa_id, ag_id, corte, vis)
        heatmap = None
        if tab == "heatmap":
            eixo = request.args.get("eixo", "loja")
            eixo = eixo if eixo in ("loja", "fonte") else "loja"
            metrica = request.args.get("metrica", "ratio")
            if metrica not in ("ratio", "detratores", "conversiveis", "pct_det"):
                metrica = "ratio"
            topn_raw = request.args.get("topn", "20")
            topn = None if topn_raw == "all" else (int(topn_raw) if topn_raw.isdigit() else 15)
            heatmap = _explorar_heatmap(s, empresa_id, ag_id, corte, eixo, metrica, topn)
        comparar = None
        if tab == "comparar":
            tipo_el = request.args.get("tipo_elemento", "loja")
            tipo_el = tipo_el if tipo_el in ("loja", "subpilar") else "loja"
            # multi-select manda elementos repetidos; deep-link manda vírgula-separado
            raw = request.args.getlist("elementos")
            if len(raw) == 1 and "," in raw[0]:
                raw = raw[0].split(",")
            selecionados = [e for e in raw if e][:3]
            comparar = {
                "tipo_elemento": tipo_el,
                "opcoes": _explorar_comparar_opcoes(s, empresa_id, ag_id, corte, tipo_el),
                "selecionados": selecionados,
                "cards": (
                    _explorar_comparar(s, empresa_id, ag_id, corte, tipo_el, selecionados)
                    if len(selecionados) >= 2
                    else []
                ),
            }
        evolucao = None
        if tab == "evolucao":
            gran = request.args.get("granularidade", "mes")
            gran = gran if gran in ("mes", "trimestre", "semestre") else "mes"
            agr = request.args.get("agrupar_por", "empresa")
            agr = agr if agr in ("empresa", "subpilar", "loja", "agrupamento") else "empresa"
            raw = request.args.getlist("valores")
            if len(raw) == 1 and "," in raw[0]:
                raw = raw[0].split(",")
            valores = [v for v in raw if v][:5]
            dados = _explorar_evolucao(s, empresa_id, ag_id, corte, gran, agr, valores)
            evolucao = {
                "granularidade": gran,
                "agrupar_por": agr,
                "opcoes": _explorar_evolucao_opcoes(s, empresa_id, ag_id, corte, agr),
                "selecionados": valores,
                "buckets": dados["buckets"],
                "series": dados["series"],
            }
        diagnostico = (
            _explorar_diagnostico(s, empresa_id, ag_id, local_id) if tab == "diagnostico" else None
        )
        concentracao = (
            _explorar_concentracao(s, empresa_id, ag_id) if tab == "concentracao" else None
        )
        governanca = _explorar_governanca(s, empresa_id, ag_id) if tab == "governanca" else None
        leaderboard = None
        if tab == "leaderboard":
            ob = request.args.get("order_by", "score")
            ob = ob if ob in ("score", "ratio", "volume", "proximity") else "score"
            lb = _explorar_leaderboard(s, empresa_id, ag_id, corte, ob)
            leaderboard = SimpleNamespace(
                linhas=lb["ranked"],
                formacao=lb["formacao"],
                insuficiente=lb["insuficiente"],
                order_by=ob,
            )
    planos = _explorar_planos(empresa_id, ag_id, request.args) if tab == "planos" else None
    ia = _explorar_ia(empresa_id, ag_id, filtros) if tab == "ia" else None
    # Escopo declarativo (CP-A): quais dimensões o header mostra como <select>
    # nesta aba; o chip usa a mesma lista p/ exibir só o que a aba aceita. Os
    # valores vêm do escopo GLOBAL (filtros base), não sobrescritos pelo builder.
    escopo_aceito = _EXPLORAR_ESCOPO_ACEITO.get(tab, _ESCOPO_FULL)
    escopo_chip = _montar_escopo_chip(filtros, agrupamentos, lojas_header, escopo_aceito)
    _u = get_current_user()
    from src.ui.manual import slug_da_tab as _slug_da_tab

    ctx = {
        "empresa": empresa_w,
        "agrupamentos": agrupamentos,
        "lojas_header": lojas_header,
        "filtros": filtros,
        "tab": tab,
        # CP-O2: eh_loyall no ctx → chega às abas tanto no full-load quanto no
        # swap HTMX (explorar_tab renderiza os partials só com **ctx).
        "eh_loyall": bool(_u and _u.papel == PAPEL_LOYALL),
        # Âncora do "?" no header → /manual#<slug-da-tela> (só loyall vê o link).
        "manual_slug": _slug_da_tab(tab),
        "escopo_aceito": escopo_aceito,
        "escopo_chip": escopo_chip,
        "locais": locais,
        "heatmap": heatmap,
        "comparar": comparar,
        "evolucao": evolucao,
        "diagnostico": diagnostico,
        "concentracao": concentracao,
        "governanca": governanca,
        "planos": planos,
        "leaderboard": leaderboard,
        "ia": ia,
    }
    # Abas migradas (Painel/Verbatins/Temas/Anomalias/Relatórios): o builder
    # dedicado monta o contexto da aba e sobrescreve as chaves específicas
    # (ex.: `filtros`, `locais`, `agrupamentos`) com as do template original.
    # Builder retornando None ⇒ erro de dados ⇒ 404 no shell.
    builder = _ABA_BUILDERS.get(tab)
    if builder is not None:
        extra = builder(empresa_id, empresa_w)
        if extra is None:
            return None
        ctx.update(extra)
    return ctx


def _explorar_ia(empresa_id, ag_id, filtros):
    """Contexto da aba IA: perguntas-sugestão + Q&A recentes cacheadas do escopo.
    As recentes já vêm renderizadas com drill-down (marcadores → links v3)."""
    from src.ia.chat import PERGUNTAS_SUGERIDAS, escopo_hash
    from src.ia.render import render_ia_html
    from src.models.chat_cache import ChatCache
    from src.models.local import Local

    e_hash = escopo_hash(ag_id, filtros.get("periodo") or None)
    with db_session() as s:
        lojas = {
            n: lid
            for lid, n in s.query(Local.id, Local.nome).filter_by(empresa_id=empresa_id).all()
        }
        rows = (
            s.query(ChatCache)
            .filter(ChatCache.empresa_id == empresa_id, ChatCache.escopo_hash == e_hash)
            .order_by(ChatCache.criado_em.desc())
            .limit(8)
            .all()
        )
        recentes = [
            SimpleNamespace(
                pergunta=x.pergunta,
                resposta_html=render_ia_html(x.resposta, empresa_id, lojas),
            )
            for x in rows
        ]
    return SimpleNamespace(sugeridas=PERGUNTAS_SUGERIDAS, recentes=recentes)


def _explorar_render(empresa_id, tab):
    """Renderiza o shell do Hub Explorar com a aba ``tab`` ativa (status 200).

    Usado tanto pela rota /explorar (tab via querystring) quanto pelas rotas
    legadas (/verbatins, /painel, /temas, /anomalias, /relatorios), que
    preservam suas URLs e renderizam o shell in-place na aba correspondente.
    """
    r = _require_login_html()
    if r:
        return r
    user = get_current_user()
    if user.papel != PAPEL_LOYALL and user.empresa_id != empresa_id:
        return render_template("403.html"), 403
    if tab not in _EXPLORAR_TAB_IDS:
        tab = "locais"
    ctx = _explorar_contexto(empresa_id, tab)
    if ctx is None:
        return render_template("404.html"), 404
    return render_template(
        "empresas/explorar.html",
        user=user,
        tabs=_EXPLORAR_TABS,
        tabs_migradas=_EXPLORAR_TABS_MIGRADAS,
        grupos=_EXPLORAR_GRUPOS,
        **ctx,  # inclui eh_loyall (CP-O2)
    )


@ui_bp.route("/empresas/<int:empresa_id>/explorar")
def explorar_empresa(empresa_id: int):
    """Hub Explorar — shell + header global + tab ativa (server-rendered)."""
    return _explorar_render(empresa_id, request.args.get("tab", "locais"))


@ui_bp.route("/empresas/<int:empresa_id>/explorar/tab/<tab>")
def explorar_tab(empresa_id: int, tab: str):
    """Conteúdo de uma tab (HTMX swap em #explorar-conteudo)."""
    r = _require_login_html()
    if r:
        return r
    user = get_current_user()
    if user.papel != PAPEL_LOYALL and user.empresa_id != empresa_id:
        return render_template("403.html"), 403
    if tab not in _EXPLORAR_TAB_IDS:
        tab = "locais"
    ctx = _explorar_contexto(empresa_id, tab)
    if ctx is None:
        return render_template("404.html"), 404
    # Conteúdo (swap em #explorar-conteudo) + header e tab bar via OOB (ambos
    # vivem fora do alvo do swap): o header adapta o escopo por aba e a tab bar
    # acompanha o sublinhado da aba ativa (Bug 2). Servidor é a única fonte —
    # sem JS de toggle.
    conteudo = render_template("partials/explorar_conteudo.html", **ctx)
    header = render_template("partials/explorar_header.html", header_oob=True, **ctx)
    tabbar = render_template(
        "partials/explorar_tabbar.html",
        tabs=_EXPLORAR_TABS,
        tabs_migradas=_EXPLORAR_TABS_MIGRADAS,
        grupos=_EXPLORAR_GRUPOS,
        tabbar_oob=True,
        **ctx,
    )
    return conteudo + header + tabbar


@ui_bp.route("/empresas/<int:empresa_id>/explorar/locais/<int:local_id>")
def explorar_loja_drill(empresa_id: int, local_id: int):
    """Drill-down por subpilar de um local (HTMX)."""
    r = _require_login_html()
    if r:
        return r
    user = get_current_user()
    if user.papel != PAPEL_LOYALL and user.empresa_id != empresa_id:
        return render_template("403.html"), 403
    _, _, corte = _explorar_filtros()
    with db_session() as s:
        loc = s.get(Local, local_id)
        nome = loc.nome if loc and loc.empresa_id == empresa_id else None
        subpilares = _explorar_loja_subpilares(s, empresa_id, local_id, corte) if nome else []
        detratores = _explorar_loja_detratores(s, empresa_id, local_id, corte) if nome else []
    return render_template(
        "partials/explorar_loja_drill.html",
        empresa_id=empresa_id,
        local_id=local_id,
        loja_nome=nome,
        subpilares=subpilares,
        detratores=detratores,
    )


@ui_bp.route("/empresas/<int:empresa_id>/explorar/ia/perguntar", methods=["POST"])
def explorar_ia_perguntar(empresa_id: int):
    """IA Chat (CP-B4): responde uma pergunta no escopo do header (HTMX).
    Single-turn; cache exato por (empresa, escopo, pergunta)."""
    r = _require_login_html()
    if r:
        return r
    user = get_current_user()
    if user.papel != PAPEL_LOYALL and user.empresa_id != empresa_id:
        return render_template("403.html"), 403
    pergunta = (request.form.get("pergunta") or "").strip()
    filtros, ag_id, corte = _explorar_filtros()
    periodo = filtros.get("periodo") or None
    if not pergunta:
        return render_template(
            "partials/explorar_ia_resposta.html",
            pergunta="",
            resposta="",
            erro="Digite uma pergunta.",
        )
    from src.ia.chat import responder

    with db_session() as s:
        out = responder(s, empresa_id, pergunta, ag_id, corte, periodo)
    return render_template(
        "partials/explorar_ia_resposta.html",
        pergunta=pergunta,
        resposta=out.get("resposta", ""),
        cached=out.get("cached", False),
        erro=out.get("erro"),
    )


@ui_bp.route("/empresas/<int:empresa_id>/explorar/ia/stream", methods=["POST"])
def explorar_ia_stream(empresa_id: int):
    """IA Chat com streaming (IA-1): responde em deltas de texto puro. Cache-hit
    devolve a resposta inteira de uma vez; miss streama o Sonnet token a token."""
    from flask import Response

    r = _require_login_html()
    if r:
        return r
    user = get_current_user()
    if user.papel != PAPEL_LOYALL and user.empresa_id != empresa_id:
        return render_template("403.html"), 403
    pergunta = (request.form.get("pergunta") or "").strip()
    if not pergunta:
        return Response("", mimetype="text/plain; charset=utf-8")
    filtros, ag_id, corte = _explorar_filtros()
    periodo = filtros.get("periodo") or None

    from src.ia.chat import responder_stream

    gen = responder_stream(empresa_id, pergunta, ag_id, corte, periodo)
    return Response(gen, mimetype="text/plain; charset=utf-8")


# Rate-limit do botão "Regenerar" (PA.5): exceção manual; pipeline cobre o automático.
_REGEN_RATE_LIMIT_SEG = 3600


@ui_bp.route("/empresas/<int:empresa_id>/explorar/regenerar/<tipo>", methods=["POST"])
def explorar_regenerar(empresa_id: int, tipo: str):
    """Regenera diagnóstico ou sugestões estruturais do escopo (Sonnet, skip por
    hash). Rate-limit 1h via max(gerado_em). Devolve a aba atualizada (HTMX)."""
    from datetime import datetime

    r = _require_login_html()
    if r:
        return r
    user = get_current_user()
    if user.papel != PAPEL_LOYALL and user.empresa_id != empresa_id:
        return render_template("403.html"), 403
    if tipo not in ("sugestoes", "diagnostico"):
        return render_template("404.html"), 404

    from src.models.diagnostico import LeituraDiagnostico
    from src.models.sugestao_estrutural import SugestaoEstrutural

    _, ag_id, _ = _explorar_filtros()
    modelo = SugestaoEstrutural if tipo == "sugestoes" else LeituraDiagnostico
    tab = "planos" if tipo == "sugestoes" else "diagnostico"

    with db_session() as s:
        ultima = _ultima_geracao(s, modelo, empresa_id, ag_id)

    msg = None
    agora = datetime.utcnow()
    if ultima is not None and (agora - ultima).total_seconds() < _REGEN_RATE_LIMIT_SEG:
        mins = int((agora - ultima).total_seconds() // 60)
        msg = (
            f"Regenerado há {mins} min. Aguarde até 1h entre regenerações manuais "
            f"— o pipeline noturno atualiza automaticamente."
        )
    elif tipo == "sugestoes":
        from src.planos.sugestoes import gerar_e_persistir_sugestoes

        m = gerar_e_persistir_sugestoes(empresa_id, ag_id, skip_unchanged=True)
        msg = (
            f"✓ {m['sugestoes']} sugestões em {m['subpilares']} subpilares regeneradas "
            f"({m['pulados']} sem mudança)."
        )
    else:
        from src.diagnostico.leituras import gerar_e_persistir_diagnostico

        m = gerar_e_persistir_diagnostico(empresa_id, ag_id, skip_unchanged=True)
        msg = f"✓ {m['gerados']} leituras regeneradas ({m['pulados']} sem mudança)."

    ctx = _explorar_contexto(empresa_id, tab)
    if ctx is None:
        return render_template("404.html"), 404
    alvo = ctx.get("planos") if tipo == "sugestoes" else ctx.get("diagnostico")
    if alvo is not None:
        alvo.regen_msg = msg
    return render_template("partials/explorar_conteudo.html", **ctx)


@ui_bp.route("/ui/empresas/<int:empresa_id>/planos/perspectiva", methods=["POST"])
def plano_perspectiva_override(empresa_id: int):
    """Override manual da perspectiva de uma ação (HTMX). Marca confiança=manual
    (preservada em reclassificações futuras). Devolve a célula atualizada."""
    r = _require_login_html()
    if r:
        return r
    user = get_current_user()
    if user.papel != PAPEL_LOYALL and user.empresa_id != empresa_id:
        return render_template("403.html"), 403

    from src.models.plano_acao import PERSPECTIVAS
    from src.planos.perspectiva import definir_perspectiva_manual

    item_chave = request.form.get("item_chave", "")
    perspectiva = request.form.get("perspectiva", "")
    if perspectiva not in PERSPECTIVAS or not item_chave:
        return ("", 400)
    definir_perspectiva_manual(empresa_id, item_chave, perspectiva)
    cell = SimpleNamespace(
        chave=item_chave, perspectiva=perspectiva, perspectiva_confianca="manual"
    )
    return render_template(
        "partials/plano_persp_cell.html", a=cell, empresa_id=empresa_id, perspectivas=_PERSP_LABELS
    )


@ui_bp.route("/ui/empresas/<int:empresa_id>/planos/tracking", methods=["POST"])
def plano_tracking(empresa_id: int):
    """Atualiza status e/ou responsável de uma ação (HTMX, sem swap — o controle
    já reflete o valor; o servidor só persiste)."""
    r = _require_login_html()
    if r:
        return r
    user = get_current_user()
    if user.papel != PAPEL_LOYALL and user.empresa_id != empresa_id:
        return render_template("403.html"), 403

    from src.planos.perspectiva import atualizar_tracking

    item_chave = request.form.get("item_chave", "")
    if not item_chave:
        return ("", 400)
    ok = atualizar_tracking(
        empresa_id,
        item_chave,
        status=request.form.get("status"),
        responsavel=request.form.get("responsavel"),
    )
    return ("", 204) if ok else ("", 400)


# ── Glossário de termos do método (CP-glossario-cadastro) ────────────────
# CRUD admin (gated PAPEL_LOYALL). Listar por categoria + editar inline + novo
# + inativar (soft-delete). `slug` é a âncora estável dos ⓘ futuros — gerado no
# "novo" e NÃO editável depois (renomear o termo não muda a referência).


def _glossario_agrupado():
    """Lista os termos agrupados por categoria (ativos primeiro, depois inativos),
    com objetos detachados para uso no template."""
    from src.models.glossario_termo import GlossarioTermo

    with db_session() as s:
        termos = (
            s.query(GlossarioTermo)
            .order_by(
                GlossarioTermo.ativo.desc(),
                GlossarioTermo.categoria,
                GlossarioTermo.ordem,
            )
            .all()
        )
        for t in termos:
            s.expunge(t)
    grupos: dict = {}
    for t in termos:
        grupos.setdefault(t.categoria or "(sem categoria)", []).append(t)
    return grupos


def _glossario_termo_detached(termo_id: int):
    from src.models.glossario_termo import GlossarioTermo

    with db_session() as s:
        t = s.get(GlossarioTermo, termo_id)
        if t is not None:
            s.expunge(t)
    return t


@ui_bp.route("/glossario")
@loyall_required_ui
def glossario():
    r = _require_loyall_html()
    if r:
        return r
    return render_template(
        "admin/glossario.html", grupos=_glossario_agrupado(), user=get_current_user()
    )


@ui_bp.route("/manual")
@loyall_required_ui
def manual():
    """Manual do Explorar (interno/loyall): renderiza docs/DESCRITIVO_EXPLORAR.md
    como página navegável (índice + âncoras). Fonte única — ver src/ui/manual.py."""
    r = _require_loyall_html()
    if r:
        return r
    from src.ui.manual import secoes as _manual_secoes

    return render_template("admin/manual.html", secoes=_manual_secoes(), user=get_current_user())


@ui_bp.route("/ui/glossario/novo", methods=["POST"])
@loyall_required_ui
def htmx_glossario_novo():
    r = _require_loyall_html()
    if r:
        return r
    from src.models.glossario_termo import GlossarioTermo
    from src.temas.slug import slugify

    termo = (request.form.get("termo") or "").strip()
    curta = (request.form.get("definicao_curta") or "").strip()
    if not termo or not curta:
        return (
            "<div class='text-red-600 text-xs'>Termo e definição curta são obrigatórios.</div>",
            400,
        )

    base_slug = slugify(termo) or "termo"
    with db_session() as s:
        slug = base_slug
        n = 2
        while s.query(GlossarioTermo).filter(GlossarioTermo.slug == slug).first() is not None:
            slug = f"{base_slug}-{n}"
            n += 1
        s.add(
            GlossarioTermo(
                termo=termo,
                slug=slug,
                definicao_curta=curta,
                definicao_completa=(request.form.get("definicao_completa") or "").strip() or None,
                categoria=(request.form.get("categoria") or "").strip() or None,
                onde_aparece=(request.form.get("onde_aparece") or "").strip() or None,
            )
        )
    return render_template("partials/glossario_lista.html", grupos=_glossario_agrupado())


@ui_bp.route("/ui/glossario/<int:termo_id>/editar", methods=["GET"])
@loyall_required_ui
def htmx_glossario_editar_form(termo_id: int):
    r = _require_loyall_html()
    if r:
        return r
    t = _glossario_termo_detached(termo_id)
    if t is None:
        return ("", 404)
    return render_template("partials/glossario_row_edit.html", t=t)


@ui_bp.route("/ui/glossario/<int:termo_id>/row", methods=["GET"])
@loyall_required_ui
def htmx_glossario_row(termo_id: int):
    r = _require_loyall_html()
    if r:
        return r
    t = _glossario_termo_detached(termo_id)
    if t is None:
        return ("", 404)
    return render_template("partials/glossario_row.html", t=t)


@ui_bp.route("/ui/glossario/<int:termo_id>", methods=["PUT"])
@loyall_required_ui
def htmx_glossario_salvar(termo_id: int):
    r = _require_loyall_html()
    if r:
        return r
    from datetime import datetime

    from src.models.glossario_termo import GlossarioTermo

    termo = (request.form.get("termo") or "").strip()
    curta = (request.form.get("definicao_curta") or "").strip()
    if not termo or not curta:
        return (
            "<div class='text-red-600 text-xs'>Termo e definição curta são obrigatórios.</div>",
            400,
        )
    with db_session() as s:
        t = s.get(GlossarioTermo, termo_id)
        if t is None:
            return ("", 404)
        # slug NÃO é editável (âncora estável dos ⓘ).
        t.termo = termo
        t.definicao_curta = curta
        t.definicao_completa = (request.form.get("definicao_completa") or "").strip() or None
        t.categoria = (request.form.get("categoria") or "").strip() or None
        t.onde_aparece = (request.form.get("onde_aparece") or "").strip() or None
        t.atualizado_em = datetime.utcnow()
    return render_template("partials/glossario_row.html", t=_glossario_termo_detached(termo_id))


@ui_bp.route("/ui/glossario/<int:termo_id>/inativar", methods=["POST"])
@loyall_required_ui
def htmx_glossario_inativar(termo_id: int):
    """Soft-delete reversível: alterna `ativo`. Devolve a linha re-renderizada."""
    r = _require_loyall_html()
    if r:
        return r
    from src.models.glossario_termo import GlossarioTermo

    with db_session() as s:
        t = s.get(GlossarioTermo, termo_id)
        if t is None:
            return ("", 404)
        t.ativo = not t.ativo
    return render_template("partials/glossario_row.html", t=_glossario_termo_detached(termo_id))


# ── Mecanismo dos ⓘ do glossário (CP-glossario-plugar-ui CP-2a) ──────────
# glossario_i(slug) é registrado como template global em app.py (padrão do
# selo_emoji). Lê o cadastro (glossario_termo, ativo=1) por slug — fonte única,
# editar em /glossario reflete nos ⓘ. Carrega TODOS os termos ativos uma vez por
# request (flask.g) → 1 query por página, sem N+1 por ⓘ.


def _glossario_cache_dict() -> dict:
    """Mapa slug → {termo, curta, completa} de todos os termos ativos. 1 query."""
    from src.models.glossario_termo import GlossarioTermo

    out: dict = {}
    with db_session() as s:
        for t in (
            s.query(GlossarioTermo)
            .filter(GlossarioTermo.ativo.is_(True))
            .order_by(GlossarioTermo.slug)
            .all()
        ):
            out[t.slug] = {
                "termo": t.termo,
                "curta": t.definicao_curta,
                "completa": t.definicao_completa,
            }
    return out


def glossario_i(slug: str, debug: bool = False):
    """Renderiza o ⓘ do termo `slug` (Markup). Cacheia o glossário em flask.g
    (1 query/request). Slug ausente → marcador discreto se debug, senão vazio."""
    from flask import g
    from markupsafe import Markup

    cache = getattr(g, "_glossario_cache", None)
    if cache is None:
        cache = _glossario_cache_dict()
        g._glossario_cache = cache
    termo = cache.get(slug)
    if termo is None:
        if debug:
            return Markup(
                f'<span class="text-red-400 text-xs" '
                f'title="glossário: slug ausente">ⓘ?{slug}</span>'
            )
        return Markup("")
    return Markup(render_template("partials/glossario_i.html", t=termo))


# ── Gestão de usuários (loyall-only, CRUD soft) ──────────────────────────
# Backend de auth já existe e é enforced em 17+ pontos (papel + empresa_id).
# Esta tela só ESCREVE Usuario reusando hash_senha + a semântica papel/empresa_id.
# Sem migration, sem mexer na autorização. "Excluir" = SOFT (ativo=False).

_PAPEL_LABEL = {
    PAPEL_LOYALL: "Admin Loyall",
    PAPEL_CLIENTE: "Cliente",
    "cliente_restrito": "Cliente (restrito)",
}


def _usuarios_ctx(erro=None, ok=None) -> dict:
    """Lista de usuários (detached) + empresas pro dropdown + mensagem."""
    with db_session() as s:
        emp_nomes = {e.id: e.nome for e in s.query(Empresa).all()}
        usuarios = [
            {
                "id": u.id,
                "email": u.email,
                "nome": u.nome,
                "papel_label": _PAPEL_LABEL.get(u.papel, u.papel),
                "empresa_nome": (
                    "Todas" if u.papel == PAPEL_LOYALL else emp_nomes.get(u.empresa_id, "—")
                ),
                "ativo": u.ativo,
                "ultimo_login": (
                    u.ultimo_login.isoformat(sep=" ", timespec="minutes") if u.ultimo_login else "—"
                ),
            }
            for u in s.query(Usuario).order_by(Usuario.papel, Usuario.nome).all()
        ]
        empresas = [
            {"id": e.id, "nome": e.nome} for e in s.query(Empresa).order_by(Empresa.nome).all()
        ]
    return {"usuarios": usuarios, "empresas": empresas, "erro": erro, "ok": ok}


def _render_usuarios_lista(erro=None, ok=None):
    return render_template("partials/usuarios_lista.html", **_usuarios_ctx(erro=erro, ok=ok))


@ui_bp.route("/usuarios")
@loyall_required_ui
def usuarios():
    r = _require_loyall_html()
    if r:
        return r
    return render_template("admin/usuarios.html", **_usuarios_ctx())


@ui_bp.route("/ui/usuarios/novo", methods=["POST"])
@loyall_required_ui
def htmx_usuarios_novo():
    r = _require_loyall_html()
    if r:
        return r
    papel = (request.form.get("papel") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    nome = (request.form.get("nome") or "").strip()
    senha = request.form.get("senha") or ""
    empresa_raw = (request.form.get("empresa_id") or "").strip()

    if papel not in (PAPEL_LOYALL, PAPEL_CLIENTE):
        return _render_usuarios_lista(erro="Papel inválido.")
    if not email or not nome:
        return _render_usuarios_lista(erro="Email e nome são obrigatórios.")
    if len(senha) < 8:
        return _render_usuarios_lista(erro="Senha deve ter pelo menos 8 caracteres.")
    if papel == PAPEL_CLIENTE:
        if not empresa_raw:
            return _render_usuarios_lista(erro="Cliente exige uma empresa.")
        empresa_id = int(empresa_raw)
    else:
        empresa_id = None  # admin_loyall: acessa todas → empresa_id NULL forçado

    with db_session() as s:
        ja = s.query(Usuario).filter(Usuario.email == email).first()
        if ja is not None:
            return _render_usuarios_lista(erro=f"Email {email!r} já existe.")
        s.add(
            Usuario(
                email=email,
                nome=nome,
                senha_hash=hash_senha(senha),
                papel=papel,
                empresa_id=empresa_id,
                ativo=True,
            )
        )
    return _render_usuarios_lista(ok=f"Usuário {email} criado ({_PAPEL_LABEL[papel]}).")


@ui_bp.route("/ui/usuarios/<int:user_id>/toggle", methods=["POST"])
@loyall_required_ui
def htmx_usuarios_toggle(user_id: int):
    r = _require_loyall_html()
    if r:
        return r
    from sqlalchemy import func

    atual = get_current_user()
    if atual is not None and user_id == atual.id:
        return _render_usuarios_lista(erro="Você não pode desativar o próprio usuário.")
    with db_session() as s:
        u = s.get(Usuario, user_id)
        if u is None:
            return _render_usuarios_lista(erro="Usuário não encontrado.")
        # Não desativar o último Admin Loyall ativo (senão ninguém mais gere usuários).
        if u.ativo and u.papel == PAPEL_LOYALL:
            n_loyall = (
                s.query(func.count(Usuario.id))
                .filter(Usuario.papel == PAPEL_LOYALL, Usuario.ativo.is_(True))
                .scalar()
            )
            if n_loyall <= 1:
                return _render_usuarios_lista(
                    erro="Não dá pra desativar o último Admin Loyall ativo."
                )
        u.ativo = not u.ativo
        acao = "reativado" if u.ativo else "desativado"
    return _render_usuarios_lista(ok=f"Usuário {acao}.")


@ui_bp.route("/ui/usuarios/<int:user_id>/reset-senha", methods=["POST"])
@loyall_required_ui
def htmx_usuarios_reset_senha(user_id: int):
    r = _require_loyall_html()
    if r:
        return r
    senha = request.form.get("senha") or ""
    if len(senha) < 8:
        return _render_usuarios_lista(erro="Senha deve ter pelo menos 8 caracteres.")
    with db_session() as s:
        u = s.get(Usuario, user_id)
        if u is None:
            return _render_usuarios_lista(erro="Usuário não encontrado.")
        u.senha_hash = hash_senha(senha)
        email = u.email
    return _render_usuarios_lista(ok=f"Senha de {email} redefinida.")


@ui_bp.route("/ui/usuarios/<int:user_id>/editar-nome", methods=["POST"])
@loyall_required_ui
def htmx_usuarios_editar_nome(user_id: int):
    r = _require_loyall_html()
    if r:
        return r
    nome = (request.form.get("nome") or "").strip()
    if not nome:
        return _render_usuarios_lista(erro="Nome não pode ser vazio.")
    with db_session() as s:
        u = s.get(Usuario, user_id)
        if u is None:
            return _render_usuarios_lista(erro="Usuário não encontrado.")
        u.nome = nome
    return _render_usuarios_lista(ok="Nome atualizado.")


# ── 404 / 403 handlers ───────────────────────────────────────────────────


@ui_bp.app_errorhandler(BadRequest)
def _bad_request_html(e):
    return render_template("400.html", erro=str(e)), 400
