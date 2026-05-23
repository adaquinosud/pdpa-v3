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
from src.models.agrupamento import Agrupamento
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.local import Local
from src.models.usuario import Usuario
from src.utils.db import db_session


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
    """Carrega empresa + agrupamentos + locais + fontes para template detalhe."""
    with db_session() as s:
        empresa = s.get(Empresa, empresa_id)
        if empresa is None:
            return None
        agrupamentos = (
            s.query(Agrupamento).filter_by(empresa_id=empresa_id).order_by(Agrupamento.nome).all()
        )
        locais = s.query(Local).filter_by(empresa_id=empresa_id).order_by(Local.nome).all()
        fontes = s.query(Fonte).filter_by(empresa_id=empresa_id).order_by(Fonte.id).all()
        # Detach tudo para uso no template
        s.expunge(empresa)
        for a in agrupamentos:
            s.expunge(a)
        for loc in locais:
            s.expunge(loc)
        for f in fontes:
            s.expunge(f)
    return {
        "empresa": empresa,
        "agrupamentos": agrupamentos,
        "locais": locais,
        "fontes": fontes,
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
        a = Agrupamento(empresa_id=empresa_id, nome=nome, descricao=descricao)
        s.add(a)
        s.flush()
        _ = (a.id, a.nome, a.descricao, a.ativo)
        s.expunge(a)
    return render_template("partials/agrupamento_row.html", a=a, eh_loyall=True)


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
        _ = (loc.id, loc.nome, loc.agrupamento_id, loc.endereco, loc.observacao)
        s.expunge(loc)
    return render_template(
        "partials/local_row.html",
        loc=loc,
        agrupamento_nome={agrupamento_id: ag_nome} if agrupamento_id else {},
    )


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
    return render_template("partials/fonte_row.html", f=f, local_nome={local_id: loc_nome})


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
        return (f"<div class='text-red-600'>Falha: {exc!r}</div>", 500)
    # ``disparar_coleta`` devolve (Response, status) ou Response.
    if isinstance(resp, tuple):
        body, status = resp
        if status >= 400:
            return (
                f"<div class='text-red-600'>{body.get_json().get('erro', 'erro')}</div>",
                status,
            )
    return "<div class='text-green-700'>Coleta disparada.</div>"


# ── 404 / 403 handlers ───────────────────────────────────────────────────


@ui_bp.app_errorhandler(BadRequest)
def _bad_request_html(e):
    return render_template("400.html", erro=str(e)), 400
