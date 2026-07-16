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

from flask import current_app, flash, redirect, render_template, request, url_for

from src.auth import get_current_user, verificar_acesso_empresa
from src.models.empresa import Empresa
from src.pesquisa.geracao import gerar_pesquisa
from src.pesquisa.juiz import validar_completo
from src.pesquisa.persistencia import (
    adicionar_pergunta,
    apagar_pesquisa,
    aprovar,
    atualizar_pergunta,
    contar_respondentes,
    criar_rascunho,
    deletar_pergunta,
    listar,
    obter,
    tem_pendente_processamento,
)
from src.pesquisa.validador import tem_bloqueio
from src.ui import _require_loyall_html, loyall_required_ui, ui_bp
from src.utils.db import db_session


def _int(v):
    try:
        return int(v) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


def _janela_meses():
    """Janela do lado cliente do confronto, em meses (p/ rótulo na tela). Deriva
    do mesmo env dos temas (PDPA_TEMAS_JANELA_DIAS) — janela e valência consistentes."""
    from src.temas.janela import get_janela_dias

    return round(get_janela_dias() / 30)


def _resolver_escopo(s, empresa_id, escopo_tipo, escopo_ids):
    """(escopo_tipo, [ids]) → (local_ids, ag_ids) p/ a agregação multi-alvo (P2.E).

    lojas → local_ids = os ids, sem temas. agrupamentos → ag_ids = os ids +
    local_ids = união dos locais deles (fracos). empresa/sem seleção → (None, None)."""
    from src.models.local import Local

    if escopo_tipo == "local" and escopo_ids:
        return list(escopo_ids), None
    if escopo_tipo == "agrupamento" and escopo_ids:
        local_ids = [
            row[0]
            for row in s.query(Local.id).filter(
                Local.empresa_id == empresa_id, Local.agrupamento_id.in_(escopo_ids)
            )
        ]
        return local_ids, list(escopo_ids)
    return None, None  # empresa toda


@ui_bp.route("/empresas/<int:empresa_id>/pesquisas")
@loyall_required_ui
def pesquisas_lista(empresa_id):
    r = _require_loyall_html()
    if r:
        return r
    from src.models.agrupamento import Agrupamento
    from src.models.local import Local
    from src.pesquisa.escopo import sugerir_focos

    with db_session() as s:
        empresa = s.get(Empresa, empresa_id)
        if empresa is None:
            return render_template("404.html"), 404
        pesquisas = [
            {
                "id": p.id,
                "titulo": p.titulo,
                "natureza": p.natureza,
                "status": p.status,
                "total_respostas": contar_respondentes(
                    s, p.id
                ),  # nº de quem respondeu (2 propósitos) — governa também a proteção da exclusão
                "tem_pendente": tem_pendente_processamento(
                    s, p.id
                ),  # texto sem embedding → pós-coleta
            }
            for p in listar(s, empresa_id)
        ]
        nome = empresa.nome
        focos = sugerir_focos(s, empresa_id)  # inicial: empresa toda; htmx recalcula
        agrupamentos = [
            (a.id, a.nome)
            for a in s.query(Agrupamento)
            .filter_by(empresa_id=empresa_id)
            .order_by(Agrupamento.nome)
        ]
        locais = [
            (loc.id, loc.nome)
            for loc in s.query(Local).filter_by(empresa_id=empresa_id).order_by(Local.nome)
        ]
    from src.api.painel import NOME_SUBPILAR, SUBPILARES_ORDEM

    subpilares = [(sp, NOME_SUBPILAR.get(sp, sp)) for sp in SUBPILARES_ORDEM]
    return render_template(
        "pesquisa/lista.html",
        empresa_id=empresa_id,
        empresa_nome=nome,
        pesquisas=pesquisas,
        subpilares=subpilares,
        focos=focos,
        agrupamentos=agrupamentos,
        locais=locais,
    )


@ui_bp.route("/empresas/<int:empresa_id>/pesquisas/focos")
@loyall_required_ui
def pesquisa_focos(empresa_id):
    """Partial htmx (P2.E): recalcula os focos para o escopo selecionado, sem
    recarregar. Lojas → só fracos; agrupamentos → fracos + temas; empresa → tudo."""
    r = _require_loyall_html()
    if r:
        return r
    from src.pesquisa.escopo import sugerir_focos

    escopo_tipo = (request.args.get("escopo_tipo") or "empresa").strip()
    escopo_ids = [int(x) for x in request.args.getlist(f"escopo_ids_{escopo_tipo}") if x.isdigit()]
    with db_session() as s:
        local_ids, ag_ids = _resolver_escopo(s, empresa_id, escopo_tipo, escopo_ids)
        focos = sugerir_focos(s, empresa_id, local_ids=local_ids, ag_ids=ag_ids)
    return render_template("pesquisa/_focos.html", focos=focos, escopo_tipo=escopo_tipo)


@ui_bp.route("/empresas/<int:empresa_id>/pesquisas/gerar", methods=["POST"])
@loyall_required_ui
def pesquisa_gerar(empresa_id):
    r = _require_loyall_html()
    if r:
        return r
    natureza = (request.form.get("natureza") or "externa").strip()
    # Propósito é escolha EXPLÍCITA (não inferida da natureza): interna pode ser
    # coleta OU confronto. Default coleta. Fora do domínio → coleta (defesa).
    proposito = (request.form.get("proposito") or "coleta").strip()
    if proposito not in ("coleta", "confronto"):
        proposito = "coleta"
    titulo = (request.form.get("titulo") or "").strip()
    n_perguntas = _int(request.form.get("n_perguntas")) or 5
    # dedup: o mesmo subpilar pode vir do card de foco E da lista manual.
    subpilares = list(dict.fromkeys(s for s in request.form.getlist("subpilares_alvo") if s))
    temas_sel = [t for t in request.form.getlist("focos_tema") if t]  # tema_labels marcados
    # P2.E: escopo = empresa | agrupamento | local (um tipo, N ids).
    escopo_tipo = (request.form.get("escopo_tipo") or "empresa").strip()
    escopo_ids = [int(x) for x in request.form.getlist(f"escopo_ids_{escopo_tipo}") if x.isdigit()]

    user = get_current_user()
    # A geração chama o LLM (rede). Qualquer falha (modelo/credencial/quota/parse)
    # vira um flash amigável + redirect, NUNCA um 500 cru. O traceback completo vai
    # pro log (current_app.logger) — diagnosticável no painel do Render.
    try:
        with db_session() as s:
            from src.models.pesquisa import PesquisaEscopo
            from src.pesquisa.escopo import sugerir_focos

            local_ids, ag_ids = _resolver_escopo(s, empresa_id, escopo_tipo, escopo_ids)
            ent_tipo = escopo_tipo if (escopo_tipo != "empresa" and escopo_ids) else "empresa"
            # âncora "qual unidade?" só faz sentido se o escopo tem >1 unidade.
            escopo_local_modo = (
                "local" if (ent_tipo == "local" and len(escopo_ids) == 1) else "geral"
            )

            # Focos-tema marcados → contexto (dominante + secundários), no MESMO escopo.
            focos = []
            if temas_sel:
                temas = sugerir_focos(s, empresa_id, local_ids=local_ids, ag_ids=ag_ids)["temas"]
                por_label = {f["tema_label"]: f for f in temas}
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
                proposito=proposito,
                subpilares_alvo=subpilares,
                n_perguntas=n_perguntas,
                titulo=titulo,
                entidade_tipo=ent_tipo,
                escopo_local_modo=escopo_local_modo,
                focos=focos,
                local_ids=local_ids,
            )
            pesquisa_id = criar_rascunho(s, proposta, criada_por=getattr(user, "id", None))
            # Junção: N alvos do MESMO tipo (o tipo vive em Pesquisa.entidade_tipo).
            if ent_tipo != "empresa":
                for eid in escopo_ids:
                    s.add(PesquisaEscopo(pesquisa_id=pesquisa_id, entidade_id=eid))
    except Exception:  # noqa: BLE001 — falha de LLM/infra não pode virar 500 cru
        current_app.logger.exception("falha ao gerar pesquisa (empresa=%s)", empresa_id)
        flash(
            "Não consegui gerar a pesquisa agora (serviço de IA indisponível). "
            "Tente novamente em instantes.",
            "erro",
        )
        return redirect(url_for("ui.pesquisas_lista", empresa_id=empresa_id))
    return redirect(url_for("ui.pesquisa_revisar", empresa_id=empresa_id, pesquisa_id=pesquisa_id))


@ui_bp.route("/empresas/<int:empresa_id>/pesquisas/<int:pesquisa_id>/apagar", methods=["POST"])
@loyall_required_ui
def pesquisa_apagar(empresa_id, pesquisa_id):
    """Exclui uma pesquisa inteira (cascade). Rota EMPRESA-ESCOPADA: o guard de
    empresa fecha o Bug B AQUI — a pesquisa TEM de pertencer à empresa da URL, senão
    404 (não vaza nem apaga cross-empresa). Proteção graduada: pronta COM respostas
    exige o título digitado (apagar destrói dado de cliente). Redireciona pra lista."""
    r = _require_loyall_html()
    if r:
        return r
    with db_session() as s:
        pesq = obter(s, pesquisa_id)
        # Isolamento: a pesquisa tem de ser da empresa da URL. 404 unificado (não
        # distingue "não existe" de "de outra empresa" — não vaza existência).
        if pesq is None or pesq.empresa_id != empresa_id:
            return render_template("404.html"), 404
        erro = verificar_acesso_empresa(empresa_id)  # acesso do usuário à empresa
        if erro:
            return erro
        # Confirmação forte: pronta COM respostas exige o título exato (padrão GitHub).
        # contar_respondentes (não contar_respostas, que é 0 na coleta → deixava apagar
        # pesquisa de coleta cheia sem a confirmação forte).
        n_resp = contar_respondentes(s, pesquisa_id)
        if pesq.status != "rascunho" and n_resp > 0:
            confirmado = (request.form.get("confirmar_titulo") or "").strip()
            if confirmado != (pesq.titulo or "").strip():
                flash(
                    "Pesquisa com respostas: digite o título EXATO para confirmar a "
                    "exclusão (é irreversível).",
                    "erro",
                )
                return redirect(url_for("ui.pesquisas_lista", empresa_id=empresa_id))
        apagar_pesquisa(s, pesquisa_id)
    flash("Pesquisa apagada.", "ok")
    return redirect(url_for("ui.pesquisas_lista", empresa_id=empresa_id))


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
        "token_publico": pesq.token_publico,  # link /p/<token> exibido quando 'pronta'
        "perguntas": perguntas,
        "subpilares": _subpilares_opcoes(),  # dropdown p/ (re)atribuir subpilar manual
        "validou": veredito is not None,
        "tem_bloqueio": tem_bloqueio(veredito) if veredito else False,
    }


def _subpilares_opcoes():
    from src.api.painel import NOME_SUBPILAR, SUBPILARES_ORDEM

    return [(sp, NOME_SUBPILAR.get(sp, sp)) for sp in SUBPILARES_ORDEM]


def _sugerir_subpilar(s, empresa_id, enunciado):
    """Sugere ``subpilar_alvo`` p/ uma pergunta manual classificando o texto digitado
    (reusa ``classificar``). Falha de LLM/infra NUNCA trava o adicionar — devolve
    None e o usuário escolhe no dropdown."""
    try:
        from src.classifier.classifier_v3 import classificar
        from src.models.empresa import Empresa

        emp = s.get(Empresa, empresa_id)
        res = classificar(
            enunciado,
            empresa_nome=getattr(emp, "nome", None),
            empresa_setor=getattr(emp, "setor", None),
        )
        return getattr(res, "subpilar", None)
    except Exception:  # noqa: BLE001 — sugestão é best-effort, jamais bloqueia
        current_app.logger.exception("falha ao sugerir subpilar (empresa=%s)", empresa_id)
        return None


@ui_bp.route("/empresas/<int:empresa_id>/pesquisas/<int:pesquisa_id>/revisar")
@loyall_required_ui
def pesquisa_revisar(empresa_id, pesquisa_id):
    r = _require_loyall_html()
    if r:
        return r
    with db_session() as s:
        if obter(s, pesquisa_id, empresa_id) is None:  # guard de escopo: outra empresa → 404
            return render_template("404.html"), 404
        ctx = _ctx_revisar(s, pesquisa_id)
        if ctx is None:
            return render_template("404.html"), 404
    return render_template("pesquisa/revisar.html", **ctx)


@ui_bp.route("/empresas/<int:empresa_id>/pesquisas/<int:pesquisa_id>/validar", methods=["POST"])
@loyall_required_ui
def pesquisa_validar(empresa_id, pesquisa_id):
    r = _require_loyall_html()
    if r:
        return r
    with db_session() as s:
        pesq = obter(s, pesquisa_id, empresa_id)  # guard de escopo: outra empresa → 404
        if pesq is None:
            return render_template("404.html"), 404
        from src.pesquisa.persistencia import perguntas_dict

        veredito = validar_completo(perguntas_dict(pesq))
        ctx = _ctx_revisar(s, pesquisa_id, veredito=veredito)
    return render_template("pesquisa/_cards.html", **ctx)


@ui_bp.route(
    "/empresas/<int:empresa_id>/pesquisas/<int:pesquisa_id>/perguntas/<int:pergunta_id>",
    methods=["POST"],
)
@loyall_required_ui
def pesquisa_editar_pergunta(empresa_id, pesquisa_id, pergunta_id):
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
        bloqueio = _guard_rascunho(s, pesquisa_id, empresa_id)
        if bloqueio is not None:
            return bloqueio
        if atualizar_pergunta(s, pergunta_id, **campos) is None:
            return render_template("404.html"), 404
        ctx = _ctx_revisar(s, pesquisa_id)
    return render_template("pesquisa/_cards.html", **ctx)


def _guard_rascunho(s, pesquisa_id, empresa_id):
    """Guard de mutação: (1) escopo de empresa — outra empresa → 404 (não vaza
    existência); (2) só edita/apaga/cria pergunta em 'rascunho' — depois de 'pronta',
    mexer mudaria o que o respondente vê → 409. Devolve a Response quando não pode
    mutar, ou None quando está liberado."""
    pesq = obter(s, pesquisa_id, empresa_id)
    if pesq is None:
        return render_template("404.html"), 404
    if pesq.status != "rascunho":
        ctx = _ctx_revisar(s, pesquisa_id)
        return render_template("pesquisa/_cards.html", **ctx), 409
    return None


@ui_bp.route(
    "/empresas/<int:empresa_id>/pesquisas/<int:pesquisa_id>/perguntas/<int:pergunta_id>/apagar",
    methods=["POST"],
)
@loyall_required_ui
def pesquisa_apagar_pergunta(empresa_id, pesquisa_id, pergunta_id):
    """Apaga uma pergunta (só rascunho). Deixa buraco na ordem. htmx → re-render #cards."""
    r = _require_loyall_html()
    if r:
        return r
    with db_session() as s:
        bloqueio = _guard_rascunho(s, pesquisa_id, empresa_id)
        if bloqueio is not None:
            return bloqueio
        deletar_pergunta(s, pergunta_id)
        ctx = _ctx_revisar(s, pesquisa_id)
    return render_template("pesquisa/_cards.html", **ctx)


@ui_bp.route("/empresas/<int:empresa_id>/pesquisas/<int:pesquisa_id>/perguntas", methods=["POST"])
@loyall_required_ui
def pesquisa_adicionar_pergunta(empresa_id, pesquisa_id):
    """Cria uma pergunta manual (só rascunho). O subpilar vem SUGERIDO pelo
    classificador (best-effort) e é editável no dropdown. htmx → re-render #cards."""
    r = _require_loyall_html()
    if r:
        return r
    enunciado = (request.form.get("enunciado") or "").strip()
    formato = (request.form.get("formato") or "aberta").strip()
    with db_session() as s:
        bloqueio = _guard_rascunho(s, pesquisa_id, empresa_id)
        if bloqueio is not None:
            return bloqueio
        if enunciado:
            pesq = obter(s, pesquisa_id)
            sug = _sugerir_subpilar(s, pesq.empresa_id, enunciado)
            adicionar_pergunta(
                s, pesquisa_id, enunciado=enunciado, formato=formato, subpilar_alvo=sug
            )
        ctx = _ctx_revisar(s, pesquisa_id)
    return render_template("pesquisa/_cards.html", **ctx)


@ui_bp.route("/empresas/<int:empresa_id>/pesquisas/<int:pesquisa_id>/aprovar", methods=["POST"])
@loyall_required_ui
def pesquisa_aprovar(empresa_id, pesquisa_id):
    r = _require_loyall_html()
    if r:
        return r
    with db_session() as s:
        if obter(s, pesquisa_id, empresa_id) is None:  # guard de escopo: outra empresa → 404
            return render_template("404.html"), 404
        ok, veredito = aprovar(s, pesquisa_id)  # re-valida server-side (determinístico)
        ctx = _ctx_revisar(s, pesquisa_id, veredito=veredito)
    if not ok:
        flash("Há perguntas que bloqueiam (🔴) — corrija antes de aprovar.", "erro")
        return render_template("pesquisa/revisar.html", **ctx), 409
    flash("Pesquisa aprovada (pronta).", "ok")
    return render_template("pesquisa/revisar.html", **ctx)


@ui_bp.route("/empresas/<int:empresa_id>/pesquisas/<int:pesquisa_id>/respostas")
@loyall_required_ui
def pesquisa_respostas(empresa_id, pesquisa_id):
    """Tela de RETORNO (Fase 2 · Passo 4): respostas por pergunta, com filtro de
    escopo. Leitura/agregação (retorno.py), sem escrita."""
    r = _require_loyall_html()
    if r:
        return r
    from src.pesquisa.retorno import regua_pesquisa, retorno_pesquisa

    et = (request.args.get("entidade_tipo") or "").strip() or None
    eid = _int(request.args.get("entidade_id"))
    escopo = (et, eid) if et else None
    with db_session() as s:
        if obter(s, pesquisa_id, empresa_id) is None:  # guard de escopo: outra empresa → 404
            return render_template("404.html"), 404
        ret = retorno_pesquisa(s, pesquisa_id, escopo)
        if ret is None:
            return render_template("404.html"), 404
        # Régua v2 (aba padrão em coleta). DEFENSIVO: se a régua nova falhar, a vista por
        # pergunta (que já está em prod) NUNCA cai — cai pra ela com regua=None.
        try:
            regua = regua_pesquisa(s, pesquisa_id, escopo)
        except Exception:  # noqa: BLE001 — blindagem da vista pronta
            current_app.logger.exception("regua_pesquisa falhou p%s", pesquisa_id)
            regua = None
    return render_template(
        "pesquisa/respostas.html",
        ret=ret,
        regua=regua,
        escopo_sel=(et, eid),
        empresa_id=empresa_id,
    )


@ui_bp.route("/empresas/<int:empresa_id>/pessoas/<int:pessoa_id>/diagnostico")
@loyall_required_ui
def pessoa_diagnostico(empresa_id, pessoa_id):
    """Diagnóstico por PESSOA (recorte fino CROSS-FONTE) — reusa o motor da régua v2
    (regua_pessoa → regua_recorte). Mapa de Lastro + valência por subpilar + verbatins
    crus (sem temas). Guard de escopo: pessoa sem verbatim nesta empresa → 404."""
    r = _require_loyall_html()
    if r:
        return r
    from src.pesquisa.retorno import _resp_ids_das_pesquisas, regua_pessoa

    # Recorte opcional por pesquisas (funil da aba Explorar → ?pesquisas=…). Sem o
    # param = cross-fonte TOTAL (a tela de pessoa pura). "Filtra em cima, filtra embaixo."
    pesquisa_ids = [int(x) for x in request.args.getlist("pesquisas") if x.isdigit()]
    with db_session() as s:
        recorte_n = None
        resp_ids = None
        if pesquisa_ids:
            validos, resp_ids = _resp_ids_das_pesquisas(s, empresa_id, pesquisa_ids)
            recorte_n = len(validos)
        rec = regua_pessoa(s, empresa_id, pessoa_id, resp_ids=resp_ids)
        if rec is None:  # pessoa inexistente ou sem verbatim (no recorte) nesta empresa
            return render_template("404.html"), 404
    return render_template(
        "pesquisa/pessoa_diagnostico.html", rec=rec, empresa_id=empresa_id, recorte_n=recorte_n
    )


@ui_bp.route(
    "/empresas/<int:empresa_id>/pesquisas/<int:pesquisa_id>/classificar-respostas",
    methods=["POST"],
)
@loyall_required_ui
def pesquisa_classificar_respostas(empresa_id, pesquisa_id):
    """Dispara a classificação EM LOTE das Respostas de confronto (Fase 2 · 5a).
    Classifica na própria Resposta — NUNCA cria Verbatim, base do cliente intocada."""
    r = _require_loyall_html()
    if r:
        return r
    from src.pesquisa.confronto import classificar_respostas_confronto

    with db_session() as s:
        if obter(s, pesquisa_id, empresa_id) is None:  # guard de escopo: outra empresa → 404
            return render_template("404.html"), 404
        stats = classificar_respostas_confronto(s, pesquisa_id=pesquisa_id)
    flash(
        f"Classificadas {stats['classificadas']} resposta(s) "
        f"({stats['erros']} erro(s), {stats['puladas']} puladas).",
        "ok",
    )
    return redirect(
        url_for("ui.pesquisa_respostas", empresa_id=empresa_id, pesquisa_id=pesquisa_id)
    )


def _pendentes_nao_classificados(s, pesquisa_id):
    """Comentários com texto mas ainda sem classificação (5a) → o gap seria falso.
    Gate compartilhado por confronto e ORIGEM."""
    from sqlalchemy import func

    from src.models.respondente import Respondente, Resposta

    return (
        s.query(func.count(Resposta.id))
        .join(Respondente, Respondente.id == Resposta.respondente_id)
        .filter(
            Respondente.pesquisa_id == pesquisa_id,
            Resposta.valor_texto.isnot(None),
            Resposta.classificado_em.is_(None),
        )
        .scalar()
    )


@ui_bp.route("/empresas/<int:empresa_id>/pesquisas/<int:pesquisa_id>/confronto")
@loyall_required_ui
def pesquisa_confronto(empresa_id, pesquisa_id):
    """Tela do GAP (Fase 2 · 5b.2): cliente × colaborador por subpilar. Só p/
    proposito='confronto'. Sinaliza comentários não-classificados (não mostra gap
    falso). Leitura pura sobre gap_confronto."""
    r = _require_loyall_html()
    if r:
        return r
    from src.pesquisa.confronto import gap_confronto, temas_escopo
    from src.pesquisa.retorno import retorno_pesquisa

    et = (request.args.get("entidade_tipo") or "").strip() or None
    eid = _int(request.args.get("entidade_id"))
    escopo = (et, eid) if et else None
    with db_session() as s:
        pesq = obter(s, pesquisa_id, empresa_id)  # guard de escopo: outra empresa → 404
        if pesq is None:
            return render_template("404.html"), 404
        if pesq.proposito != "confronto":
            flash("O confronto é só para pesquisas de propósito 'confronto'.", "erro")
            return redirect(
                url_for("ui.pesquisa_respostas", empresa_id=empresa_id, pesquisa_id=pesquisa_id)
            )
        # Pendentes: comentários ainda não classificados (5a) → gap seria falso.
        pendentes = _pendentes_nao_classificados(s, pesquisa_id)
        ret = retorno_pesquisa(s, pesquisa_id)  # reusa só os escopos (filtro)
        escopos = ret["escopos"] if ret else []
        gap = None if pendentes else gap_confronto(s, pesquisa_id, escopo)
        temas_indisponiveis = temas_escopo(pesq, escopo)[1]  # loja → aviso, sem tema
        ctx = {
            "pesquisa_id": pesquisa_id,
            "empresa_id": pesq.empresa_id,
            "titulo": pesq.titulo,
            "temas_indisponiveis": temas_indisponiveis,
            "janela_meses": _janela_meses(),
        }
    return render_template(
        "pesquisa/confronto.html",
        gap=gap,
        pendentes=pendentes,
        escopos=escopos,
        escopo_sel=(et, eid),
        **ctx,
    )


# ── ORIGEM (fatia 3): régua de profundidade — tela irmã do confronto ─────────
# Ordem de profundidade: Essência (mais fundo) → Resultado (mais raso).
_ORIGEM_ORDEM = {"essencia": 0, "significado": 1, "direcao": 2, "caminho": 3, "resultado": 4}


@ui_bp.route("/empresas/<int:empresa_id>/pesquisas/<int:pesquisa_id>/origem")
@loyall_required_ui
def pesquisa_origem(empresa_id, pesquisa_id):
    """Tela do ORIGEM (fatia 3): a que elo da cadeia generativa mora cada gap,
    medido contra a essência declarada. Só proposito='confronto'. Leitura pura
    sobre origem_analise/origem_sintese; o botão dispara gerar_origem."""
    r = _require_loyall_html()
    if r:
        return r
    from src.api.painel import NOME_SUBPILAR
    from src.models.empresa import Empresa
    from src.models.origem import OrigemAnalise, OrigemSintese
    from src.pesquisa.origem import _essencia_vazia

    with db_session() as s:
        pesq = obter(s, pesquisa_id, empresa_id)  # guard de escopo: outra empresa → 404
        if pesq is None:
            return render_template("404.html"), 404
        if pesq.proposito != "confronto":
            flash("O ORIGEM é só para pesquisas de propósito 'confronto'.", "erro")
            return redirect(
                url_for("ui.pesquisa_respostas", empresa_id=empresa_id, pesquisa_id=pesquisa_id)
            )
        emp = s.get(Empresa, pesq.empresa_id)
        essencia_vazia = emp is None or _essencia_vazia(emp)
        pendentes = _pendentes_nao_classificados(s, pesquisa_id)
        linhas = s.query(OrigemAnalise).filter_by(pesquisa_id=pesquisa_id).all()
        analises = sorted(
            (
                {
                    "subpilar": a.subpilar,
                    "nome": NOME_SUBPILAR.get(a.subpilar, a.subpilar),
                    "nivel": a.nivel,
                    "lado": a.lado,
                    "justificativa": a.justificativa,
                }
                for a in linhas
            ),
            key=lambda a: (_ORIGEM_ORDEM.get(a["nivel"], 9), a["subpilar"]),
        )
        sint = s.get(OrigemSintese, pesquisa_id)
        # gerado_em: a análise mais recente (achado da defasagem invisível).
        gerado_em = max((a.gerado_em for a in linhas if a.gerado_em), default=None)
        # Cascata conceitual: o elo MAIS FUNDO que rompe (primeiro na ordem com
        # gravidade). Índice 0..4 (essencia..resultado); None se nenhum problema.
        grav = {a["nivel"] for a in analises if a["lado"] == "gravidade"}
        _ordem_elos = ["essencia", "significado", "direcao", "caminho", "resultado"]
        ruptura_ordem = next((i for i, n in enumerate(_ordem_elos) if n in grav), None)
        # 6a: forma degradada nomeada por elo ABAIXO da ruptura (badge curto + frase
        # no tooltip). Fallback 'herda' fica no template. Motor da ruptura intocado.
        degradacao = {}
        if ruptura_ordem is not None:
            from src.pesquisa.origem import forma_degradada

            _rompido = _ordem_elos[ruptura_ordem]
            for idx, n in enumerate(_ordem_elos):
                cel = forma_degradada(_rompido, n) if idx > ruptura_ordem else None
                if cel:
                    degradacao[n] = cel
        ctx = {
            "pesquisa_id": pesquisa_id,
            "empresa_id": pesq.empresa_id,
            "titulo": pesq.titulo,
            "essencia_vazia": essencia_vazia,
            "pendentes": pendentes,
            "analises": analises,
            "sintese": sint.texto if sint else None,
            "gerado_em": gerado_em,
            "ruptura_ordem": ruptura_ordem,
            "degradacao": degradacao,
        }
    return render_template("pesquisa/origem.html", **ctx)


@ui_bp.route(
    "/empresas/<int:empresa_id>/pesquisas/<int:pesquisa_id>/origem/gerar", methods=["POST"]
)
@loyall_required_ui
def pesquisa_origem_gerar(empresa_id, pesquisa_id):
    """Dispara gerar_origem (1 chamada LLM, sob demanda). Falha de IA → flash, não
    500 cru. Re-rodar sobrescreve. Molde do 'Classificar comentários'."""
    r = _require_loyall_html()
    if r:
        return r
    from src.pesquisa.origem import gerar_origem

    try:
        with db_session() as s:
            if obter(s, pesquisa_id, empresa_id) is None:  # guard de escopo: outra empresa → 404
                return render_template("404.html"), 404
            out = gerar_origem(s, pesquisa_id)
    except Exception:  # noqa: BLE001 — falha de LLM/infra não vira 500 cru
        current_app.logger.exception("falha ao rodar ORIGEM (pesquisa=%s)", pesquisa_id)
        flash("Não consegui rodar o ORIGEM agora (serviço de IA indisponível).", "erro")
        return redirect(
            url_for("ui.pesquisa_origem", empresa_id=empresa_id, pesquisa_id=pesquisa_id)
        )

    status = out.get("status")
    if status == "ok":
        flash(f"ORIGEM: {out['analisados']} gap(s) analisado(s).", "ok")
    elif status == "essencia_indisponivel":
        flash("Cadastre missão, visão e valores da empresa primeiro.", "erro")
    elif status == "sem_gaps":
        flash("Nenhum gap para o ORIGEM ler (sem pontos cegos, descompassos ou forças).", "ok")
    return redirect(url_for("ui.pesquisa_origem", empresa_id=empresa_id, pesquisa_id=pesquisa_id))


# ── Quadro dos pilares (Leitura 2): topo individual × base sistêmica ─────────
# Estado do confronto por subpilar → ponto no mapa dos pilares.
_QUADRO_ESTADO = {
    "ponto_cego": ("🔴", "ponto cego"),
    "descompasso": ("🟠", "descompasso"),
    "consciencia_compartilhada": ("🟡", "consciência"),
    "forca": ("🟢", "força"),
    "nao_perguntado": ("⚪", "não perguntado"),
}


def _quadro_time(g):
    """Resumo do lado TIME (mesma leitura da coluna Time do confronto)."""
    col = (g or {}).get("colaborador")
    if col:
        v, n = col.get("valencia_dominante"), col.get("nota_media")
        if v and n is not None:
            return f"{v} · nota {n}"
        if v:
            return f"{v} · sem nota específica"
        if n is not None:
            return f"nota {n} · não apontou o problema"
        return "—"
    if g and g.get("categoria") == "ponto_cego":
        return "não consegue avaliar"
    return "—"


def _quadro_cell(sub, por_sub, nome_subpilar):
    g = por_sub.get(sub)
    emoji, label = _QUADRO_ESTADO.get((g or {}).get("categoria"), ("⚪", "sem dado"))
    cli = (g or {}).get("cliente") or {}
    return {
        "subpilar": sub,
        "nome": nome_subpilar.get(sub, sub),
        "estado_emoji": emoji,
        "estado_label": label,
        "time": _quadro_time(g),
        "cliente": cli.get("valencia_dominante") or "—",
        "faixa": cli.get("faixa"),
        "temas": [t["tema_label"] for t in ((g or {}).get("temas_cliente") or [])][:3],
    }


def _quadro_grao(s, pesq):
    """Rótulo do grão da leitura (o escopo da pesquisa) — a moldura da 'escada'."""
    et = pesq.entidade_tipo or "empresa"
    if et == "empresa":
        return "Empresa toda"
    ids = [e.entidade_id for e in pesq.escopos]
    if et == "agrupamento":
        from src.models.agrupamento import Agrupamento

        nomes = [a.nome for a in s.query(Agrupamento).filter(Agrupamento.id.in_(ids))]
        return "Agrupamento" + ("s: " if len(nomes) > 1 else ": ") + ", ".join(nomes or ["—"])
    from src.models.local import Local

    nomes = [loc.nome for loc in s.query(Local).filter(Local.id.in_(ids))]
    return "Loja" + ("s: " if len(nomes) > 1 else ": ") + ", ".join(nomes or ["—"])


@ui_bp.route("/empresas/<int:empresa_id>/pesquisas/<int:pesquisa_id>/quadro")
@loyall_required_ui
def pesquisa_quadro(empresa_id, pesquisa_id):
    """Quadro dos pilares (Leitura 2): base sistêmica (P, D) × topo individual
    (Pa, A), com o estado do confronto de cada subpilar. Leitura pura sobre
    gap_confronto. Só proposito='confronto'."""
    r = _require_loyall_html()
    if r:
        return r
    from src.api.painel import NOME_PILAR, NOME_SUBPILAR, PILAR_DE_SUBPILAR, SUBPILARES_ORDEM
    from src.pesquisa.confronto import gap_confronto
    from src.pesquisa.retorno import retorno_pesquisa

    with db_session() as s:
        pesq = obter(s, pesquisa_id, empresa_id)  # guard de escopo: outra empresa → 404
        if pesq is None:
            return render_template("404.html"), 404
        if pesq.proposito != "confronto":
            flash("O quadro dos pilares é só para pesquisas de propósito 'confronto'.", "erro")
            return redirect(
                url_for("ui.pesquisa_respostas", empresa_id=empresa_id, pesquisa_id=pesquisa_id)
            )
        por_sub = {g["subpilar"]: g for g in (gap_confronto(s, pesquisa_id) or [])}
        ret = retorno_pesquisa(s, pesquisa_id)

        def _bloco(code):
            subs = [sp for sp in SUBPILARES_ORDEM if PILAR_DE_SUBPILAR.get(sp) == code]
            return {
                "code": code,
                "nome": NOME_PILAR.get(code, code),
                "subpilares": [_quadro_cell(sp, por_sub, NOME_SUBPILAR) for sp in subs],
            }

        faixas = [
            {
                "eyebrow": "TOPO · INDIVIDUAL",
                "frase": "conta a conta, pessoa a pessoa; não se sistematiza.",
                "pilares": [_bloco("Pa"), _bloco("A")],
            },
            {
                "eyebrow": "BASE · SISTÊMICA",
                "frase": "resolve-se uma vez, no processo, e todos se beneficiam.",
                "pilares": [_bloco("P"), _bloco("D")],
            },
        ]
        ctx = {
            "pesquisa_id": pesquisa_id,
            "empresa_id": empresa_id,
            "titulo": pesq.titulo,
            "faixas": faixas,
            "grao": _quadro_grao(s, pesq),
            "n_resp": ret["total_respondentes"] if ret else 0,
            "janela_meses": _janela_meses(),
        }
    return render_template("pesquisa/quadro.html", **ctx)


# ── Duas visões que se encontram — time × modelo × cliente, por pilar ────────
def _moda(vals):
    from collections import Counter

    return Counter(vals).most_common(1)[0][0] if vals else None


def _visoes_citacoes_time(s, pesquisa_id):
    """{pilar: [1-2 citações LITERAIS do time]} — valor_texto de respostas
    classificadas com valência clara, mais recentes primeiro, truncadas ~100
    chars. Determinístico (sem LLM). Diferente dos temas do cliente (agregados)."""
    from src.api.painel import PILAR_DE_SUBPILAR
    from src.models.respondente import Respondente, Resposta

    rows = (
        s.query(Resposta.valor_texto, Resposta.subpilar_classificado)
        .join(Respondente, Respondente.id == Resposta.respondente_id)
        .filter(
            Respondente.pesquisa_id == pesquisa_id,
            Resposta.valor_texto.isnot(None),
            Resposta.subpilar_classificado.isnot(None),
            Resposta.valencia_classificada.in_(("promotor", "conversivel", "detrator")),
        )
        .order_by(Resposta.classificado_em.desc(), Resposta.id.desc())
        .all()
    )
    out = {}
    for texto, sub in rows:
        pilar = PILAR_DE_SUBPILAR.get(sub)
        if pilar is None:
            continue
        lst = out.setdefault(pilar, [])
        if len(lst) < 2:
            t = (texto or "").strip()
            lst.append(t if len(t) <= 100 else t[:100].rstrip() + "…")
    return out


def _gauge_pct(ratio):
    """Posição 0-100 do marcador na barra de 5 faixas iguais, pela posição do ratio
    DENTRO da sua faixa (cortes de FAIXAS_RATIO — fonte única). Excelente (∞) usa um
    teto suave (10.0) só p/ POSICIONAR o marcador; não altera a faixa."""
    from src.api.painel import FAIXAS_RATIO

    seg = 100.0 / len(FAIXAS_RATIO)
    lo = 0.0
    for i, (hi, _label) in enumerate(FAIXAS_RATIO):
        teto = 10.0 if hi == float("inf") else hi
        if ratio < hi or hi == float("inf"):
            frac = (ratio - lo) / (teto - lo) if teto > lo else 1.0
            return round(i * seg + min(1.0, max(0.0, frac)) * seg, 1)
        lo = hi
    return 100.0


@ui_bp.route("/empresas/<int:empresa_id>/pesquisas/<int:pesquisa_id>/visoes")
@loyall_required_ui
def pesquisa_visoes(empresa_id, pesquisa_id):
    """'Duas visões que se encontram': por pilar, a visão do TIME (valência+nota
    agregadas) × o MODELO × a voz do CLIENTE (valência + temas como citações).
    Agregado fiel (moda da valência, média da nota); o detalhe por subpilar vive
    no quadro. Leitura pura sobre gap_confronto. Só proposito='confronto'."""
    r = _require_loyall_html()
    if r:
        return r
    from src.api.painel import (
        NOME_PILAR,
        PILAR_DE_SUBPILAR,
        PILARES_ORDEM,
        SUBPILARES_ORDEM,
        calcular_ratio,
        faixa_ratio,
    )
    from src.diagnostico.leituras import agregar_subpilares
    from src.pesquisa.confronto import gap_confronto
    from src.temas.janela import data_corte

    with db_session() as s:
        pesq = obter(s, pesquisa_id, empresa_id)  # guard de escopo: outra empresa → 404
        if pesq is None:
            return render_template("404.html"), 404
        if pesq.proposito != "confronto":
            flash("As duas visões são só para pesquisas de propósito 'confronto'.", "erro")
            return redirect(
                url_for("ui.pesquisa_respostas", empresa_id=empresa_id, pesquisa_id=pesquisa_id)
            )
        por_sub = {g["subpilar"]: g for g in (gap_confronto(s, pesquisa_id) or [])}
        citacoes_time = _visoes_citacoes_time(s, pesquisa_id)  # falas literais do time
        # Ratio do CLIENTE por pilar (gauge) — MESMA janela do confronto (data_corte),
        # recomputado dos counts somados (nunca soma ratios). Referente idêntico ao do
        # confronto que o gauge acompanha. Não toca estado/categoria do gap_confronto.
        corte = data_corte(pesq.empresa_id, s)
        cliente_agg = agregar_subpilares(s, pesq.empresa_id, desde=corte)

        pilares = []
        for code in PILARES_ORDEM:
            subs = [sp for sp in SUBPILARES_ORDEM if PILAR_DE_SUBPILAR.get(sp) == code]
            time_vals, notas, cli_vals, temas = [], [], [], []
            for sp in subs:
                g = por_sub.get(sp)
                if not g:
                    continue
                col = g.get("colaborador") or {}
                if col.get("valencia_dominante"):
                    time_vals.append(col["valencia_dominante"])
                if col.get("nota_media") is not None:
                    notas.append(col["nota_media"])
                cli = g.get("cliente") or {}
                if cli.get("valencia_dominante"):
                    cli_vals.append(cli["valencia_dominante"])
                temas.extend(g.get("temas_cliente") or [])
            time_val = _moda(time_vals)
            cli_val = _moda(cli_vals)
            # ratio do CLIENTE no pilar: Σprom/Σdet dos subpilares (mesma janela) →
            # calcular_ratio (recomputa dos counts, não soma ratios) + faixa + posição.
            _prom = sum(cliente_agg.get(sp, {}).get("prom", 0) for sp in subs)
            _det = sum(cliente_agg.get(sp, {}).get("det", 0) for sp in subs)
            _tot = sum(cliente_agg.get(sp, {}).get("total", 0) for sp in subs)
            cli_ratio = calcular_ratio(_prom, _det) if _tot else None
            # top-4 temas por volume (citações curtas do cliente)
            temas_top = []
            for t in sorted(temas, key=lambda x: -x.get("volume", 0)):
                if t["tema_label"] not in temas_top:
                    temas_top.append(t["tema_label"])
                if len(temas_top) >= 4:
                    break
            pilares.append(
                {
                    "code": code,
                    "nome": NOME_PILAR.get(code, code),
                    "subpilares": subs,
                    "time_val": time_val,
                    "time_nota": round(sum(notas) / len(notas), 1) if notas else None,
                    "time_citacoes": citacoes_time.get(code, []),
                    "cli_val": cli_val,
                    "temas": temas_top,
                    # gauge de ratio do cliente (barra de faixas) — mesma janela
                    "cli_ratio": cli_ratio,
                    "cli_faixa": faixa_ratio(cli_ratio) if cli_ratio is not None else None,
                    "cli_gauge_pct": _gauge_pct(cli_ratio) if cli_ratio is not None else None,
                    # acento onde as duas visões divergem (o pilar dói)
                    "diverge": bool(time_val and cli_val and time_val != cli_val),
                }
            )
        # Radar (Chart.js, já carregado no base): valência → score 1-3 (0=sem dado),
        # comparável entre time e cliente; onde os polígonos separam = divergência.
        _score = {"detrator": 1, "conversivel": 2, "promotor": 3}
        radar = {
            "labels": [p["code"] for p in pilares],
            "nomes": [p["nome"] for p in pilares],
            "time": [_score.get(p["time_val"], 0) for p in pilares],
            "cliente": [_score.get(p["cli_val"], 0) for p in pilares],
        }
        # Corte de leitura sistêmico × individual (espelha o /quadro do ORIGEM):
        # BASE (P,D) processo · TOPO (Pa,A) relação. Reorg de apresentação — a
        # `pilares` (motor) fica intacta e alimenta o radar.
        _by_code = {p["code"]: p for p in pilares}
        grupos = [
            {
                "eyebrow": "BASE · SISTÊMICA",
                "frase": "resolve-se uma vez, no processo, e todos se beneficiam.",
                "pilares": [_by_code[c] for c in ("P", "D") if c in _by_code],
            },
            {
                "eyebrow": "TOPO · INDIVIDUAL",
                "frase": "conta a conta, pessoa a pessoa; não se sistematiza.",
                "pilares": [_by_code[c] for c in ("Pa", "A") if c in _by_code],
            },
        ]
        ctx = {
            "pesquisa_id": pesquisa_id,
            "empresa_id": empresa_id,
            "titulo": pesq.titulo,
            "pilares": pilares,
            "grupos": grupos,
            "radar": radar,
            "janela_meses": _janela_meses(),
        }
    return render_template("pesquisa/visoes.html", **ctx)
