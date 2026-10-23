"""Rotas do Avaliador — aba do Explorar, SÓ admin Loyall nesta entrega.

Registradas no ``ui_bp`` (importado no fim de ``src/ui/__init__.py``). O gate é o
``loyall_required_ui`` EM CADA ROTA, não só a aba escondida: a rota de abas do Explorar
aceita qualquer id pela URL (achado de 12/10, fora desta frente), então esconder não basta.

A aba carrega por HTMX a partir da rota própria — ``_explorar_contexto`` não é tocado.
"""

from __future__ import annotations

import json

from flask import current_app, render_template, request
from markupsafe import escape

from src.api.painel import SUBPILARES_ORDEM
from src.auth import get_current_user
from src.avaliador import parecer as parecer_mod
from src.avaliador import servico
from src.avaliador.extracao import (
    FORMATOS_COM_TABELA,
    FORMATOS_POR_SECAO,
    FRACAO_CONTROLES_ILEGIVEL,
    LIMITE_BYTES,
    LIMITE_CARACTERES,
    MIN_CARACTERES_PAGINA,
    SEPARADOR_CELULA,
    DocumentoRecusado,
)
from src.avaliador.pagina_web import MAX_PAGINAS_WEB
from src.avaliador.regua import carregar_regua
from src.avaliador.servico import AvaliacaoRecusada
from src.models.avaliador import (
    STATUS_APAGADA,
    STATUS_EM_PROCESSAMENTO,
    STATUS_PENDENTE,
    STATUS_PRONTA,
    AvaliadorAnalise,
)
from src.ui import loyall_required_ui, ui_bp
from src.utils.db import db_session
from src.utils.fuso import hora_br

ROTULO_STATUS = {
    "pendente": "Na fila",
    "lendo": "Lendo a peça",
    "pronta": "Pronta",
    "falhou": "Falhou",
}
ROTULO_TIPO = {"forte": "Forte", "falta": "Falta", "melhorar": "Melhorar"}
ROTULO_VEREDITO = {"sim": "Sim", "parcial": "Parcial", "nao": "Não"}


def _lista(s, empresa_id: int):
    return (
        s.query(AvaliadorAnalise)
        .filter_by(empresa_id=empresa_id)
        .filter(AvaliadorAnalise.status != STATUS_APAGADA)
        .order_by(AvaliadorAnalise.criado_em.desc())
        .limit(30)
        .all()
    )


def _conta_de_prospects(s, empresa_id: int) -> bool:
    from src.models.empresa import Empresa

    e = s.get(Empresa, empresa_id)
    return e is not None and e.nome == servico.CONTA_PROSPECTS


def _painel(s, empresa_id: int, erro=None, analise_html=None, form=None):
    return render_template(
        "partials/explorar_avaliador.html",
        empresa_id=empresa_id,
        analises=_lista(s, empresa_id),
        conta_de_prospects=_conta_de_prospects(s, empresa_id),
        rotulo_status=ROTULO_STATUS,
        dias_retencao=servico.dias_retencao(),
        limite_mb=LIMITE_BYTES // (1024 * 1024),
        limite_caracteres=LIMITE_CARACTERES,
        max_paginas_web=MAX_PAGINAS_WEB,
        erro=erro,
        analise_html=analise_html,
        form=form or {},
    )


def _render_lista(s, empresa_id: int, oob: bool) -> str:
    return render_template(
        "partials/explorar_avaliador_lista.html",
        empresa_id=empresa_id,
        analises=_lista(s, empresa_id),
        rotulo_status=ROTULO_STATUS,
        oob=oob,
    )


def _parecer(a: AvaliadorAnalise, tela: dict) -> dict:
    """O parecer montado a partir da tela já corrigida, com as pendências (fatia 2)."""
    return parecer_mod.montar(
        tela,
        servico.textos_do_parecer(a),
        a.id,
        hora_br(a.criado_em, "%d/%m/%Y"),
        json.loads(a.itens_json)["cobertura"],
    )


def _campos_em_branco(a: AvaliadorAnalise) -> int:
    """Quantos dos treze campos que o rascunho preenche (a ordem e os doze achados) estão
    em branco."""
    t = servico.textos_do_parecer(a)
    escrito = [t["ordem"], *(t["achados"].get(c, "") for c in SUBPILARES_ORDEM)]
    return sum(1 for x in escrito if not (x or "").strip())


def _render_analise(empresa_id: int, a: AvaliadorAnalise, erro=None, s=None) -> str:
    """Com ``s``: a lista de baixo vai junto, fora da área trocada (hx-swap-oob), e se
    atualiza a cada polling/ação. Sem ``s``: a análise vai dentro do painel, que já
    renderiza a lista."""
    formato = servico.formato_da_leitura(a)
    tela = (
        servico.organizar_marcas(carregar_regua(), a, servico.correcoes_de(a))
        if formato == servico.FORMATO_MARCAS and a.status == STATUS_PRONTA
        else None
    )
    return render_template(
        "partials/explorar_avaliador_analise.html",
        empresa_id=empresa_id,
        a=a,
        erro=erro,
        lista_oob=_render_lista(s, empresa_id, oob=True) if s is not None else None,
        formato_leitura=formato,
        aviso_formato_anterior=(
            formato in (servico.FORMATO_ITENS, servico.FORMATO_VEREDITO)
            and a.status == STATUS_PRONTA
            and formato != servico.FORMATO_ATUAL
        ),
        pilares=servico.organizar(carregar_regua(), a) if formato == servico.FORMATO_ITENS else [],
        leitura=(
            servico.organizar_veredito(carregar_regua(), a)
            if formato == servico.FORMATO_VEREDITO
            else None
        ),
        marcas=tela,
        parecer=_parecer(a, tela) if tela else None,
        parecer_textos=servico.textos_do_parecer(a) if tela else None,
        rascunho_estado=(
            parecer_mod.estado_do_rascunho(tela, servico.textos_do_parecer(a)) if tela else {}
        ),
        campos_em_branco=_campos_em_branco(a) if tela else 0,
        rascunho_teto_usd=(
            servico.estimativa_rascunho(a, tela) if tela and _campos_em_branco(a) else 0.0
        ),
        no_parecer=(
            parecer_mod.escolhidos_da_tela(tela, servico.textos_do_parecer(a)["escolhas"])
            if tela
            else set()
        ),
        rotulo_veredito=ROTULO_VEREDITO,
        paginas_sem_texto=json.loads(a.paginas_sem_texto_json or "[]"),
        por_secao=a.formato in FORMATOS_POR_SECAO,
        separa_celulas=a.formato in FORMATOS_COM_TABELA,
        separador_celula=SEPARADOR_CELULA,
        min_caracteres_pagina=MIN_CARACTERES_PAGINA,
        pct_controles_ilegivel=round(FRACAO_CONTROLES_ILEGIVEL * 100),
        rotulo_status=ROTULO_STATUS,
        rotulo_tipo=ROTULO_TIPO,
        processando=a.status in STATUS_EM_PROCESSAMENTO,
        texto_disponivel=a.texto_json is not None,
        pode_corrigir=formato == servico.FORMATO_MARCAS and a.status == STATUS_PRONTA,
        dias_retencao=servico.dias_retencao(),
        peca_de_medicao=servico.e_peca_de_medicao(a),
    )


def _analise_da_empresa(s, empresa_id: int, aid: int):
    """Leitura apagada não existe para a tela: abrir, reler ou concluir dá 404."""
    a = s.get(AvaliadorAnalise, aid)
    if a is None or a.empresa_id != empresa_id or a.status == STATUS_APAGADA:
        return None
    return a


@ui_bp.route("/empresas/<int:empresa_id>/explorar/avaliador", methods=["GET"])
@loyall_required_ui
def avaliador_painel(empresa_id: int):
    with db_session() as s:
        return _painel(s, empresa_id)


@ui_bp.route("/empresas/<int:empresa_id>/explorar/avaliador", methods=["POST"])
@loyall_required_ui
def avaliador_novo(empresa_id: int):
    descricao = request.form.get("descricao", "")
    texto = request.form.get("texto", "")
    url = request.form.get("url", "")
    arquivo = request.files.get("arquivo")
    cliente = request.form.get("cliente_nomeado", "")
    form = {"descricao": descricao, "texto": texto, "url": url, "cliente_nomeado": cliente}
    with db_session() as s:
        if (request.content_length or 0) > LIMITE_BYTES + 1024 * 1024:
            return _painel(
                s,
                empresa_id,
                erro=f"Arquivo maior que {LIMITE_BYTES // (1024 * 1024)} MB.",
                form=form,
            )
        dados = arquivo.read(LIMITE_BYTES + 1) if arquivo and arquivo.filename else None
        try:
            a = servico.criar_analise(
                s,
                empresa_id,
                get_current_user().id,
                descricao,
                nome=arquivo.filename if dados else None,
                dados=dados,
                texto=texto if not dados else None,
                url=url if not dados else None,
                cliente_nomeado={"sim": True, "nao": False}.get(cliente),
            )
        except (DocumentoRecusado, AvaliacaoRecusada) as e:
            return _painel(s, empresa_id, erro=str(e), form=form)
        s.commit()
        servico.disparar(a.id, app=current_app._get_current_object())
        return _painel(s, empresa_id, analise_html=_render_analise(empresa_id, a))


@ui_bp.route("/empresas/<int:empresa_id>/explorar/avaliador/<int:aid>", methods=["GET"])
@loyall_required_ui
def avaliador_analise(empresa_id: int, aid: int):
    with db_session() as s:
        a = _analise_da_empresa(s, empresa_id, aid)
        if a is None:
            return render_template("404.html"), 404
        servico.marcar_uso(a)
        s.flush()
        return _render_analise(empresa_id, a, s=s)


def _acao(empresa_id: int, aid: int, fn):
    """Executa uma ação da pessoa; se ela deixou a análise PENDENTE, dispara a thread.
    Recusa vira mensagem na própria tela da análise."""
    with db_session() as s:
        a = _analise_da_empresa(s, empresa_id, aid)
        if a is None:
            return render_template("404.html"), 404
        try:
            fn(s, a)
        except AvaliacaoRecusada as e:
            return _render_analise(empresa_id, a, erro=str(e), s=s)
        s.commit()
        if a.status == STATUS_PENDENTE:
            servico.disparar(a.id, app=current_app._get_current_object())
        return _render_analise(empresa_id, a, s=s)


@ui_bp.route("/empresas/<int:empresa_id>/explorar/avaliador/<int:aid>/refazer", methods=["POST"])
@loyall_required_ui
def avaliador_refazer(empresa_id: int, aid: int):
    descricao = request.form.get("descricao")
    return _acao(empresa_id, aid, lambda s, a: servico.refazer(s, a, descricao))


@ui_bp.route("/empresas/<int:empresa_id>/explorar/avaliador/<int:aid>/concluir", methods=["POST"])
@loyall_required_ui
def avaliador_concluir(empresa_id: int, aid: int):
    return _acao(empresa_id, aid, lambda s, a: servico.concluir(a))


@ui_bp.route(
    "/empresas/<int:empresa_id>/explorar/avaliador/<int:aid>/corrigir/<acao>", methods=["POST"]
)
@loyall_required_ui
def avaliador_corrigir(empresa_id: int, aid: int, acao: str):
    """Correção à mão (fatia 1 do parecer no app): recusar um trecho citado, incluir um trecho
    achado na peça, ou desfazer. Fica gravada; o resultado da leitura não muda."""
    usuario_id = get_current_user().id
    f = request.form
    if acao == "recusar":
        fn = lambda s, a: servico.recusar_trecho(  # noqa: E731
            s, a, f.get("codigo", ""), f.get("trecho", ""), usuario_id
        )
    elif acao == "incluir":
        fn = lambda s, a: servico.incluir_trecho(  # noqa: E731
            s, a, f.get("codigo", ""), f.get("trecho", ""), usuario_id
        )
    elif acao == "escolher":
        fn = lambda s, a: servico.escolher_trecho(  # noqa: E731
            s, a, f.get("codigo", ""), f.get("trecho", ""), usuario_id
        )
    elif acao == "naoachadas":
        fn = lambda s, a: servico.recusar_nao_achadas(  # noqa: E731
            s, a, f.get("codigo", ""), usuario_id
        )
    elif acao == "desfazer":
        fn = lambda s, a: servico.desfazer_correcao(  # noqa: E731
            s, a, int(f.get("correcao_id") or 0)
        )
    else:
        return render_template("404.html"), 404
    return _acao(empresa_id, aid, fn)


@ui_bp.route("/empresas/<int:empresa_id>/explorar/avaliador/<int:aid>/parecer", methods=["POST"])
@loyall_required_ui
def avaliador_parecer_salvar(empresa_id: int, aid: int):
    """Salva um campo do parecer (a ordem, um achado ou a nota do bloco C) e devolve as
    pendências atualizadas, fora da área trocada."""
    with db_session() as s:
        a = _analise_da_empresa(s, empresa_id, aid)
        if a is None:
            return render_template("404.html"), 404
        try:
            servico.salvar_parecer(
                s, a, request.form.get("campo", ""), request.form.get("texto", ""),
                get_current_user().id,
            )  # fmt: skip
        except AvaliacaoRecusada as e:
            return f'<span class="text-xs text-rose-700">{escape(str(e))}</span>'
        s.commit()
        tela = servico.organizar_marcas(carregar_regua(), a, servico.correcoes_de(a))
        campo = request.form.get("campo", "")
        rotulo = render_template(
            "partials/_avaliador_rascunho_rotulo.html", campo=campo, oob=True,
            rascunho_estado=parecer_mod.estado_do_rascunho(tela, servico.textos_do_parecer(a)),
            empresa_id=empresa_id, a=a,
        )  # fmt: skip
        return rotulo + render_template(
            "partials/_avaliador_parecer_pendencias.html",
            parecer=_parecer(a, tela), empresa_id=empresa_id, a=a, salvo=True, oob=True,
        )  # fmt: skip


@ui_bp.route(
    "/empresas/<int:empresa_id>/explorar/avaliador/<int:aid>/parecer/rascunho", methods=["POST"]
)
@loyall_required_ui
def avaliador_rascunho(empresa_id: int, aid: int):
    """O modelo rascunha a ordem e os achados em branco (fatia 3). Chamada paga: o teto da
    empresa é conferido antes; o gasto fica gravado mesmo na falha."""
    usuario_id = get_current_user().id
    return _acao(empresa_id, aid, lambda s, a: servico.rascunhar_parecer(s, a, usuario_id))


@ui_bp.route(
    "/empresas/<int:empresa_id>/explorar/avaliador/<int:aid>/parecer/aceitar", methods=["POST"]
)
@loyall_required_ui
def avaliador_rascunho_aceitar(empresa_id: int, aid: int):
    """ "Aceito como está": a pessoa passou pelo campo do rascunho sem mudar o texto."""
    usuario_id = get_current_user().id
    campo = request.form.get("campo", "")
    return _acao(empresa_id, aid, lambda s, a: servico.aceitar_rascunho(s, a, campo, usuario_id))


@ui_bp.route(
    "/empresas/<int:empresa_id>/explorar/avaliador/<int:aid>/parecer.docx", methods=["GET"]
)
@loyall_required_ui
def avaliador_parecer_word(empresa_id: int, aid: int):
    """O Word do parecer. É o que vai ao cliente: com pendência, não sai (CLAUDE.md §10)."""
    import io

    from flask import send_file

    with db_session() as s:
        a = _analise_da_empresa(s, empresa_id, aid)
        if a is None:
            return render_template("404.html"), 404
        if servico.formato_da_leitura(a) != servico.FORMATO_MARCAS or a.status != STATUS_PRONTA:
            return "Só uma leitura pronta, no formato atual, tem parecer.", 409
        tela = servico.organizar_marcas(carregar_regua(), a, servico.correcoes_de(a))
        p = _parecer(a, tela)
        if p["pendencias"]:
            return (
                "O parecer ainda não pode sair. Falta: " + " ".join(p["pendencias"]),
                409,
                {"Content-Type": "text/plain; charset=utf-8"},
            )
        dados = parecer_mod.gerar_docx(p)
        servico.marcar_uso(a)
        s.commit()
    return send_file(
        io.BytesIO(dados),
        as_attachment=True,
        download_name=f"Parecer_PDPA_leitura{aid}.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@ui_bp.route("/empresas/<int:empresa_id>/explorar/avaliador/<int:aid>/apagar", methods=["POST"])
@loyall_required_ui
def avaliador_apagar(empresa_id: int, aid: int):
    with db_session() as s:
        a = _analise_da_empresa(s, empresa_id, aid)
        if a is None:
            return render_template("404.html"), 404
        try:
            servico.apagar_leitura(a)
        except AvaliacaoRecusada as e:
            return _render_analise(empresa_id, a, erro=str(e), s=s)
        s.commit()
        return (
            '<div id="avaliador-analise" class="border border-loyall-200 rounded p-4 '
            'text-sm text-loyall-600 bg-white">Leitura apagada.</div>'
            + _render_lista(s, empresa_id, oob=True)
        )
