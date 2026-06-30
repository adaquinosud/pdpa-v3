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
        from src.pesquisa.escopo import sugerir_focos

        focos = sugerir_focos(s, empresa_id)  # P2.D — assistente de escopo
    from src.api.painel import NOME_SUBPILAR, SUBPILARES_ORDEM

    fracos = {f["subpilar_alvo"]: f["justificativa"] for f in focos["fracos"]}
    subpilares = [(sp, NOME_SUBPILAR.get(sp, sp)) for sp in SUBPILARES_ORDEM]
    return render_template(
        "pesquisa/lista.html",
        empresa_id=empresa_id,
        empresa_nome=nome,
        pesquisas=pesquisas,
        subpilares=subpilares,
        fracos=fracos,
        temas_sugeridos=focos["temas"],
        tem_temas=focos["tem_temas"],
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
    temas_sel = [t for t in request.form.getlist("focos_tema") if t]  # tema_labels marcados

    user = get_current_user()
    with db_session() as s:
        # P2.D: resolve os focos-tema marcados → contexto (dominante + secundários);
        # o subpilar dominante de cada tema entra em subpilares_alvo (união limpa).
        focos = []
        if temas_sel:
            from src.pesquisa.escopo import sugerir_focos

            por_label = {f["tema_label"]: f for f in sugerir_focos(s, empresa_id)["temas"]}
            for label in temas_sel:
                f = por_label.get(label)
                if f and f.get("subpilar_alvo"):  # disperso (sem dominante) não entra
                    focos.append(f)
                    if f["subpilar_alvo"] not in subpilares:
                        subpilares.append(f["subpilar_alvo"])
        if not subpilares:
            flash("Escolha ao menos um subpilar-alvo ou um tema com foco.", "erro")
            return redirect(url_for("ui.pesquisas_lista", empresa_id=empresa_id))
        proposta = gerar_pesquisa(
            s,
            empresa_id,
            natureza=natureza,
            subpilares_alvo=subpilares,
            n_perguntas=n_perguntas,
            titulo=titulo,
            escopo_local_modo=escopo_local_modo,
            focos=focos,
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


@ui_bp.route("/pesquisas/<int:pesquisa_id>/respostas")
@loyall_required_ui
def pesquisa_respostas(pesquisa_id):
    """Tela de RETORNO (Fase 2 · Passo 4): respostas por pergunta, com filtro de
    escopo. Leitura/agregação (retorno.py), sem escrita."""
    r = _require_loyall_html()
    if r:
        return r
    from src.pesquisa.retorno import retorno_pesquisa

    et = (request.args.get("entidade_tipo") or "").strip() or None
    eid = _int(request.args.get("entidade_id"))
    escopo = (et, eid) if et else None
    with db_session() as s:
        ret = retorno_pesquisa(s, pesquisa_id, escopo)
        if ret is None:
            return render_template("404.html"), 404
    return render_template("pesquisa/respostas.html", ret=ret, escopo_sel=(et, eid))


@ui_bp.route("/pesquisas/<int:pesquisa_id>/classificar-respostas", methods=["POST"])
@loyall_required_ui
def pesquisa_classificar_respostas(pesquisa_id):
    """Dispara a classificação EM LOTE das Respostas de confronto (Fase 2 · 5a).
    Classifica na própria Resposta — NUNCA cria Verbatim, base do cliente intocada."""
    r = _require_loyall_html()
    if r:
        return r
    from src.pesquisa.confronto import classificar_respostas_confronto

    with db_session() as s:
        if obter(s, pesquisa_id) is None:
            return render_template("404.html"), 404
        stats = classificar_respostas_confronto(s, pesquisa_id=pesquisa_id)
    flash(
        f"Classificadas {stats['classificadas']} resposta(s) "
        f"({stats['erros']} erro(s), {stats['puladas']} puladas).",
        "ok",
    )
    return redirect(url_for("ui.pesquisa_respostas", pesquisa_id=pesquisa_id))


@ui_bp.route("/pesquisas/<int:pesquisa_id>/confronto")
@loyall_required_ui
def pesquisa_confronto(pesquisa_id):
    """Tela do GAP (Fase 2 · 5b.2): cliente × colaborador por subpilar. Só p/
    proposito='confronto'. Sinaliza comentários não-classificados (não mostra gap
    falso). Leitura pura sobre gap_confronto."""
    r = _require_loyall_html()
    if r:
        return r
    from sqlalchemy import func

    from src.models.respondente import Respondente, Resposta
    from src.pesquisa.confronto import gap_confronto
    from src.pesquisa.retorno import retorno_pesquisa

    et = (request.args.get("entidade_tipo") or "").strip() or None
    eid = _int(request.args.get("entidade_id"))
    escopo = (et, eid) if et else None
    with db_session() as s:
        pesq = obter(s, pesquisa_id)
        if pesq is None:
            return render_template("404.html"), 404
        if pesq.proposito != "confronto":
            flash("O confronto é só para pesquisas de propósito 'confronto'.", "erro")
            return redirect(url_for("ui.pesquisa_respostas", pesquisa_id=pesquisa_id))
        # Pendentes: comentários ainda não classificados (5a) → gap seria falso.
        pendentes = (
            s.query(func.count(Resposta.id))
            .join(Respondente, Respondente.id == Resposta.respondente_id)
            .filter(
                Respondente.pesquisa_id == pesquisa_id,
                Resposta.valor_texto.isnot(None),
                Resposta.classificado_em.is_(None),
            )
            .scalar()
        )
        ret = retorno_pesquisa(s, pesquisa_id)  # reusa só os escopos (filtro)
        escopos = ret["escopos"] if ret else []
        gap = None if pendentes else gap_confronto(s, pesquisa_id, escopo)
        ctx = {
            "pesquisa_id": pesquisa_id,
            "empresa_id": pesq.empresa_id,
            "titulo": pesq.titulo,
        }
    return render_template(
        "pesquisa/confronto.html",
        gap=gap,
        pendentes=pendentes,
        escopos=escopos,
        escopo_sel=(et, eid),
        **ctx,
    )
