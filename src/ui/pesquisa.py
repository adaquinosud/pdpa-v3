"""Rotas da UI do Motor de Pesquisa — Fase 1 (CP-Pesquisa-F1.5).

Criar → revisar (cards editáveis + validar + aplicar reescrita) → aprovar.
Loyall/admin only. Sem coleta (Fase 2). O aprovar RE-VALIDA server-side: recusa
se houver violação 🔴, não confia no front.

Registradas no ``ui_bp`` (importado no fim de ``src/ui/__init__.py``). Os símbolos
de geração/validação são referenciados pelo namespace deste módulo, então testes
podem monkeypatchar ``src.ui.pesquisa.gerar_pesquisa`` / ``validar_completo`` para
não tocar a rede.
"""

from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for

from src.auth import get_current_user
from src.models.empresa import Empresa
from src.pesquisa.geracao import gerar_pesquisa
from src.pesquisa.juiz import validar_completo
from src.pesquisa.persistencia import (
    aprovar,
    atualizar_pergunta,
    criar_rascunho,
    listar,
    obter,
)
from src.pesquisa.validador import tem_bloqueio
from src.ui import _require_loyall_html, loyall_required_ui, ui_bp
from src.utils.db import db_session


def _int(v):
    try:
        return int(v) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


@ui_bp.route("/empresas/<int:empresa_id>/pesquisas")
@loyall_required_ui
def pesquisas_lista(empresa_id):
    r = _require_loyall_html()
    if r:
        return r
    with db_session() as s:
        empresa = s.get(Empresa, empresa_id)
        if empresa is None:
            return render_template("404.html"), 404
        pesquisas = [
            {"id": p.id, "titulo": p.titulo, "natureza": p.natureza, "status": p.status}
            for p in listar(s, empresa_id)
        ]
        nome = empresa.nome
    from src.api.painel import NOME_SUBPILAR, SUBPILARES_ORDEM

    subpilares = [(sp, NOME_SUBPILAR.get(sp, sp)) for sp in SUBPILARES_ORDEM]
    return render_template(
        "pesquisa/lista.html",
        empresa_id=empresa_id,
        empresa_nome=nome,
        pesquisas=pesquisas,
        subpilares=subpilares,
    )


@ui_bp.route("/empresas/<int:empresa_id>/pesquisas/gerar", methods=["POST"])
@loyall_required_ui
def pesquisa_gerar(empresa_id):
    r = _require_loyall_html()
    if r:
        return r
    natureza = (request.form.get("natureza") or "externa").strip()
    titulo = (request.form.get("titulo") or "").strip()
    escopo_local_modo = (request.form.get("escopo_local_modo") or "local").strip()
    n_perguntas = _int(request.form.get("n_perguntas")) or 5
    subpilares = [s for s in request.form.getlist("subpilares_alvo") if s]
    if not subpilares:
        flash("Escolha ao menos um subpilar-alvo.", "erro")
        return redirect(url_for("ui.pesquisas_lista", empresa_id=empresa_id))

    user = get_current_user()
    with db_session() as s:
        proposta = gerar_pesquisa(
            s,
            empresa_id,
            natureza=natureza,
            subpilares_alvo=subpilares,
            n_perguntas=n_perguntas,
            titulo=titulo,
            escopo_local_modo=escopo_local_modo,
        )
        pesquisa_id = criar_rascunho(s, proposta, criada_por=getattr(user, "id", None))
    return redirect(url_for("ui.pesquisa_revisar", pesquisa_id=pesquisa_id))


def _ctx_revisar(s, pesquisa_id, veredito=None):
    pesq = obter(s, pesquisa_id)
    if pesq is None:
        return None
    veredito_por_ordem = {}
    if veredito:
        veredito_por_ordem = {v["ordem"]: v["regras"] for v in veredito["perguntas"]}
    perguntas = [
        {
            "id": p.id,
            "ordem": p.ordem,
            "enunciado": p.enunciado,
            "porque": p.porque,
            "formato": p.formato,
            "subpilar_alvo": p.subpilar_alvo,
            "gerada_por_ancora": p.gerada_por_ancora,
            "regras": veredito_por_ordem.get(p.ordem, []),
        }
        for p in pesq.perguntas
    ]
    return {
        "pesquisa_id": pesq.id,
        "empresa_id": pesq.empresa_id,
        "titulo": pesq.titulo,
        "natureza": pesq.natureza,
        "status": pesq.status,
        "perguntas": perguntas,
        "validou": veredito is not None,
        "tem_bloqueio": tem_bloqueio(veredito) if veredito else False,
    }


@ui_bp.route("/pesquisas/<int:pesquisa_id>/revisar")
@loyall_required_ui
def pesquisa_revisar(pesquisa_id):
    r = _require_loyall_html()
    if r:
        return r
    with db_session() as s:
        ctx = _ctx_revisar(s, pesquisa_id)
        if ctx is None:
            return render_template("404.html"), 404
    return render_template("pesquisa/revisar.html", **ctx)


@ui_bp.route("/pesquisas/<int:pesquisa_id>/validar", methods=["POST"])
@loyall_required_ui
def pesquisa_validar(pesquisa_id):
    r = _require_loyall_html()
    if r:
        return r
    with db_session() as s:
        pesq = obter(s, pesquisa_id)
        if pesq is None:
            return render_template("404.html"), 404
        from src.pesquisa.persistencia import perguntas_dict

        veredito = validar_completo(perguntas_dict(pesq))
        ctx = _ctx_revisar(s, pesquisa_id, veredito=veredito)
    return render_template("pesquisa/_cards.html", **ctx)


@ui_bp.route("/pesquisas/<int:pesquisa_id>/perguntas/<int:pergunta_id>", methods=["POST"])
@loyall_required_ui
def pesquisa_editar_pergunta(pesquisa_id, pergunta_id):
    r = _require_loyall_html()
    if r:
        return r
    campos = {
        "enunciado": (request.form.get("enunciado") or "").strip() or None,
        "formato": (request.form.get("formato") or "").strip() or None,
        "opcoes_json": (request.form.get("opcoes_json") or "").strip() or None,
        "subpilar_alvo": (request.form.get("subpilar_alvo") or "").strip() or None,
    }
    with db_session() as s:
        if atualizar_pergunta(s, pergunta_id, **campos) is None:
            return render_template("404.html"), 404
        ctx = _ctx_revisar(s, pesquisa_id)
    return render_template("pesquisa/_cards.html", **ctx)


@ui_bp.route("/pesquisas/<int:pesquisa_id>/aprovar", methods=["POST"])
@loyall_required_ui
def pesquisa_aprovar(pesquisa_id):
    r = _require_loyall_html()
    if r:
        return r
    with db_session() as s:
        if obter(s, pesquisa_id) is None:
            return render_template("404.html"), 404
        ok, veredito = aprovar(s, pesquisa_id)  # re-valida server-side (determinístico)
        ctx = _ctx_revisar(s, pesquisa_id, veredito=veredito)
    if not ok:
        flash("Há perguntas que bloqueiam (🔴) — corrija antes de aprovar.", "erro")
        return render_template("pesquisa/revisar.html", **ctx), 409
    flash("Pesquisa aprovada (pronta).", "ok")
    return render_template("pesquisa/revisar.html", **ctx)
