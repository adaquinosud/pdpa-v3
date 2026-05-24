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
    PAPEL_LOYALL,
    get_current_user,
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


def _wrap_fonte(f) -> SimpleNamespace:
    return SimpleNamespace(
        id=f.id,
        empresa_id=f.empresa_id,
        entidade_tipo=f.entidade_tipo,
        entidade_id=f.entidade_id,
        conector_tipo=f.conector_tipo,
        url=f.url,
        ativo=bool(f.ativo),
        ultima_coleta=f.ultima_coleta,
        criada_em=f.criada_em,
        observacao=f.observacao,
    )


def _wrap_local(loc, fontes=None) -> SimpleNamespace:
    fontes_w = [_wrap_fonte(f) for f in (fontes or [])]
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


def _wrap_empresa(e) -> SimpleNamespace:
    return SimpleNamespace(
        id=e.id,
        nome=e.nome,
        setor=e.setor,
        site=e.site,
        cnpj=e.cnpj,
        observacao=e.observacao,
        criada_em=e.criada_em,
        atualizada_em=e.atualizada_em,
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


# ── Home ─────────────────────────────────────────────────────────────────


@ui_bp.route("/")
def home():
    if get_current_user() is None:
        return redirect(url_for("ui.login_form"))
    return redirect(url_for("ui.lista_empresas"))


# ── Login / Logout ───────────────────────────────────────────────────────


@ui_bp.route("/login", methods=["GET"])
def login_form():
    if get_current_user() is not None:
        return redirect(url_for("ui.lista_empresas"))
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
    return redirect(url_for("ui.lista_empresas"))


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
    user = get_current_user()
    with db_session() as s:
        query = s.query(Empresa).order_by(Empresa.nome)
        if user.papel != PAPEL_LOYALL:
            query = query.filter(Empresa.id == user.empresa_id)
        empresas = query.all()
        # Detach para uso no template
        for e in empresas:
            s.expunge(e)
    # Cliente com 1 empresa → atalho para detalhe
    if user.papel != PAPEL_LOYALL and len(empresas) == 1:
        return redirect(url_for("ui.detalhe_empresa", empresa_id=empresas[0].id))
    return render_template("empresas/lista.html", empresas=empresas, user=user)


@ui_bp.route("/empresas/nova", methods=["GET", "POST"])
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

        empresa_w = _wrap_empresa(empresa_db)

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
    user = get_current_user()
    if user.papel != PAPEL_LOYALL and user.empresa_id != empresa_id:
        return render_template("403.html"), 403
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
def coletas_em_andamento_redirect(empresa_id: int):
    """Atalho UI -> API JSON usado pelo polling JS na página de detalhe."""
    from src.api.monitoramento import coletas_em_andamento_da_empresa as h

    return h(empresa_id)


@ui_bp.route("/ui/monitoramento/lista")
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
    """Página da lista paginada de verbatins de uma empresa."""
    r = _require_login_html()
    if r:
        return r
    user = get_current_user()
    if user.papel != PAPEL_LOYALL and user.empresa_id != empresa_id:
        return render_template("403.html"), 403

    # Chama o handler da API e usa o JSON resultante
    from src.api.verbatins import listar_verbatins_da_empresa as api_handler

    resp = api_handler(empresa_id)
    # api_handler retorna Response (200) ou tupla (response, status) em erro
    if isinstance(resp, tuple):
        return resp
    api_payload = resp.get_json()
    if api_payload is None:
        return render_template("404.html"), 404

    # Filtros lidos da URL
    filtros = {
        "q": request.args.get("q", ""),
        "agrupamento_id": request.args.get("agrupamento_id", ""),
        "local_id": request.args.get("local_id", ""),
        "fonte_id": request.args.get("fonte_id", ""),
        "subpilar": request.args.get("subpilar", ""),
        "tipo": request.args.get("tipo", ""),
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
        empresa_db = s.get(Empresa, empresa_id)
        if empresa_db is None:
            return render_template("404.html"), 404
        empresa_w = _wrap_empresa(empresa_db)
        ags = s.query(Agrupamento).filter_by(empresa_id=empresa_id).order_by(Agrupamento.nome).all()
        locs = s.query(Local).filter_by(empresa_id=empresa_id).order_by(Local.nome).all()
        fonts = s.query(Fonte).filter_by(empresa_id=empresa_id).order_by(Fonte.conector_tipo).all()
        agrupamentos = [SimpleNamespace(id=a.id, nome=a.nome) for a in ags]
        locais = [SimpleNamespace(id=loc.id, nome=loc.nome) for loc in locs]
        fontes_ = [
            SimpleNamespace(id=f.id, conector_tipo=f.conector_tipo, url=f.url) for f in fonts
        ]
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
        params = {k: v for k, v in filtros.items() if v not in ("", None) and k != "pagina"}
        params["pagina"] = pagina
        return urlencode(params)

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

    return render_template(
        "empresas/verbatins.html",
        empresa=empresa_w,
        verbatins=api_payload["verbatins"],
        total=total,
        total_paginas=total_paginas,
        agrupamentos=agrupamentos,
        locais=locais,
        fontes=fontes_,
        temas=temas_filtro,
        filtros=filtros,
        subpilares=sorted(SUBPILARES_VALIDOS),
        tipos=sorted(TIPOS_VALIDOS),
        pag_qs_anterior=_qs(filtros["pagina"] - 1),
        pag_qs_proxima=_qs(filtros["pagina"] + 1),
        voltar_url=voltar_url,
        voltar_texto=voltar_texto,
        eh_loyall=(user.papel == PAPEL_LOYALL),
        user=user,
    )


@ui_bp.route("/empresas/<int:empresa_id>/painel")
def painel_empresa(empresa_id: int):
    """Painel Executivo (Bloco 5 CP-2): Visão Geral + Detalhamento por Subpilar."""
    r = _require_login_html()
    if r:
        return r
    user = get_current_user()
    if user.papel != PAPEL_LOYALL and user.empresa_id != empresa_id:
        return render_template("403.html"), 403

    # Chama os 2 endpoints do painel via handler interno (zero HTTP overhead)
    from src.api.painel import painel_nivel1 as h_n1
    from src.api.painel import painel_nivel2 as h_n2

    resp_n1 = h_n1(empresa_id)
    resp_n2 = h_n2(empresa_id)
    if isinstance(resp_n1, tuple):
        return resp_n1
    if isinstance(resp_n2, tuple):
        return resp_n2
    n1 = resp_n1.get_json()
    n2 = resp_n2.get_json()
    if n1 is None or n2 is None:
        return render_template("404.html"), 404

    # Filtros lidos da URL (eco para o front; mesmos do n1/n2)
    filtros = {
        "agrupamento_id": request.args.get("agrupamento_id", ""),
        "local_id": request.args.get("local_id", ""),
        "fonte_id": request.args.get("fonte_id", ""),
        "periodo": request.args.get("periodo", ""),
    }

    with db_session() as s:
        empresa_db = s.get(Empresa, empresa_id)
        if empresa_db is None:
            return render_template("404.html"), 404
        empresa_w = _wrap_empresa(empresa_db)
        ags = s.query(Agrupamento).filter_by(empresa_id=empresa_id).order_by(Agrupamento.nome).all()
        locs = s.query(Local).filter_by(empresa_id=empresa_id).order_by(Local.nome).all()
        fonts = s.query(Fonte).filter_by(empresa_id=empresa_id).order_by(Fonte.conector_tipo).all()
        agrupamentos = [SimpleNamespace(id=a.id, nome=a.nome) for a in ags]
        locais = [SimpleNamespace(id=loc.id, nome=loc.nome) for loc in locs]
        fontes_ = [
            SimpleNamespace(id=f.id, conector_tipo=f.conector_tipo, url=f.url) for f in fonts
        ]

    return render_template(
        "empresas/painel.html",
        empresa=empresa_w,
        n1=n1,
        n2=n2,
        filtros=filtros,
        agrupamentos=agrupamentos,
        locais=locais,
        fontes=fontes_,
        eh_loyall=(user.papel == PAPEL_LOYALL),
        user=user,
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
    return render_template(
        "partials/painel_temas_modal.html",
        empresa_id=empresa_id,
        subpilar=body.get("subpilar"),
        tipo=body.get("tipo"),
        temas=body.get("temas", []),
    )


@ui_bp.route("/admin/temas/<int:empresa_id>", methods=["GET"])
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
        empresa_w = _wrap_empresa(empresa_db)

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
def htmx_agrupamento_row(agrupamento_id: int):
    """Devolve a row em modo view (para cancelar edição ou após save)."""
    a = _carregar_ag(agrupamento_id)
    if a is None:
        return ("", 404)
    user = get_current_user()
    eh_loyall = bool(user and user.papel == PAPEL_LOYALL)
    return render_template("partials/agrupamento_card.html", a=a, eh_loyall=eh_loyall)


@ui_bp.route("/ui/agrupamentos/<int:agrupamento_id>/editar", methods=["GET"])
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
def htmx_local_row(local_id: int):
    loc, ags, ag_map = _carregar_local_e_ags(local_id)
    if loc is None:
        return ("", 404)
    erro = _check_acesso(loc.empresa_id)
    if erro:
        return erro
    return render_template("partials/local_card.html", loc=loc, agrupamento_nome=ag_map)


@ui_bp.route("/ui/locais/<int:local_id>/editar", methods=["GET"])
def htmx_editar_local_form(local_id: int):
    loc, ags, _ag_map = _carregar_local_e_ags(local_id)
    if loc is None:
        return ("", 404)
    erro = _check_acesso(loc.empresa_id)
    if erro:
        return erro
    return render_template("partials/local_card_edit.html", loc=loc, agrupamentos=ags)


@ui_bp.route("/ui/locais/<int:local_id>", methods=["PUT"])
def htmx_salvar_local(local_id: int):
    nome = (request.form.get("nome") or "").strip()
    if not nome:
        return (
            "<tr><td colspan='5' class='text-red-600 text-xs'>" "Nome é obrigatório.</td></tr>"
        ), 400
    ag_id_raw = request.form.get("agrupamento_id") or ""
    new_ag = int(ag_id_raw) if ag_id_raw.isdigit() else None
    endereco = (request.form.get("endereco") or "").strip() or None
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
        s.flush()
    # Recarrega com fontes + ag_map
    loc, _ags, ag_map = _carregar_local_e_ags(local_id)
    return render_template("partials/local_card.html", loc=loc, agrupamento_nome=ag_map, open=True)


@ui_bp.route("/ui/locais/<int:local_id>/inativar", methods=["PATCH"])
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
    return render_template("partials/fonte_item.html", f=f, local_nome={local_id: loc_nome})


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
        f_w = _wrap_fonte(f_db)
    return f_w, local_map


@ui_bp.route("/ui/fontes/<int:fonte_id>/row", methods=["GET"])
def htmx_fonte_row(fonte_id: int):
    f, local_map = _carregar_fonte_e_local(fonte_id)
    if f is None:
        return ("", 404)
    erro = _check_acesso(f.empresa_id)
    if erro:
        return erro
    return render_template("partials/fonte_item.html", f=f, local_nome=local_map)


@ui_bp.route("/ui/fontes/<int:fonte_id>/editar", methods=["GET"])
def htmx_editar_fonte_form(fonte_id: int):
    f, _local_map = _carregar_fonte_e_local(fonte_id)
    if f is None:
        return ("", 404)
    erro = _check_acesso(f.empresa_id)
    if erro:
        return erro
    return render_template("partials/fonte_item_edit.html", f=f)


@ui_bp.route("/ui/fontes/<int:fonte_id>", methods=["PUT"])
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
        empresa.atualizada_em = _dt.utcnow()
    # Resposta vazia: o modal usa hx-on::after-request="window.location.reload()"
    return ("", 200)


@ui_bp.route("/ui/fontes/<int:fonte_id>/disparar", methods=["POST"])
def htmx_disparar_fonte(fonte_id: int):
    """Botão 'disparar coleta' na UI — chama o handler de /api/coleta/disparar."""
    with db_session() as s:
        f = s.get(Fonte, fonte_id)
        if f is None:
            return ("<div class='text-red-600'>Fonte não encontrada.</div>", 404)
        erro = _check_acesso(f.empresa_id)
        if erro:
            return erro
    # Delega para o handler já existente.
    from src.api.coleta import disparar_coleta

    try:
        resp = disparar_coleta(fonte_id)
    except Exception as exc:  # pragma: no cover — robustez
        return (f"<div class='text-red-600 text-xs'>Falha: {exc!r}</div>", 500)
    # ``disparar_coleta`` devolve (Response, status) ou Response.
    if isinstance(resp, tuple):
        body, status = resp
        if status >= 400:
            return (
                f"<div class='text-red-600 text-xs'>{body.get_json().get('erro', 'erro')}</div>",
                status,
            )
        stats = body.get_json() or {}
    else:
        stats = resp.get_json() or {}

    if stats.get("falhou_apify"):
        return (
            "<div class='text-red-600 text-xs'>Apify falhou — fonte não coletada.</div>",
            200,
        )

    coletados = stats.get("coletados", 0)
    novos = stats.get("novos", 0)
    duplicados = stats.get("duplicados", 0)
    erros = stats.get("erros", 0)
    return (
        f"<div class='text-emerald-700 text-xs'>"
        f"✓ {coletados} coletados · {novos} novos · {duplicados} dup · {erros} erros"
        f"</div>"
    )


# ── 404 / 403 handlers ───────────────────────────────────────────────────


@ui_bp.app_errorhandler(BadRequest)
def _bad_request_html(e):
    return render_template("400.html", erro=str(e)), 400
