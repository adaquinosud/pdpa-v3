"""Rotas do Avaliador — aba do Explorar, SÓ admin Loyall nesta entrega.

Registradas no ``ui_bp`` (importado no fim de ``src/ui/__init__.py``). O gate é o
``loyall_required_ui`` EM CADA ROTA, não só a aba escondida: a rota de abas do Explorar
aceita qualquer id pela URL (achado de 12/10, fora desta frente), então esconder não basta.

A aba carrega por HTMX a partir da rota própria — ``_explorar_contexto`` não é tocado.
"""

from __future__ import annotations

import json

from flask import current_app, render_template, request

from src.auth import get_current_user
from src.avaliador import servico
from src.avaliador.extracao import (
    FRACAO_CONTROLES_ILEGIVEL,
    LIMITE_BYTES,
    LIMITE_CARACTERES,
    MIN_CARACTERES_PAGINA,
    DocumentoRecusado,
)
from src.avaliador.regua import carregar_regua
from src.avaliador.servico import AvaliacaoRecusada
from src.models.avaliador import STATUS_EM_PROCESSAMENTO, STATUS_PENDENTE, AvaliadorAnalise
from src.ui import loyall_required_ui, ui_bp
from src.utils.db import db_session

ROTULO_STATUS = {
    "pendente": "Na fila",
    "lendo": "Lendo a peça",
    "pronta": "Pronta",
    "falhou": "Falhou",
}
ROTULO_TIPO = {"forte": "Forte", "falta": "Falta", "melhorar": "Melhorar"}


def _lista(s, empresa_id: int):
    return (
        s.query(AvaliadorAnalise)
        .filter_by(empresa_id=empresa_id)
        .order_by(AvaliadorAnalise.criado_em.desc())
        .limit(30)
        .all()
    )


def _painel(s, empresa_id: int, erro=None, analise_html=None, form=None):
    return render_template(
        "partials/explorar_avaliador.html",
        empresa_id=empresa_id,
        analises=_lista(s, empresa_id),
        rotulo_status=ROTULO_STATUS,
        dias_retencao=servico.dias_retencao(),
        limite_mb=LIMITE_BYTES // (1024 * 1024),
        limite_caracteres=LIMITE_CARACTERES,
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


def _render_analise(empresa_id: int, a: AvaliadorAnalise, erro=None, s=None) -> str:
    """Com ``s``: a lista de baixo vai junto, fora da área trocada (hx-swap-oob), e se
    atualiza a cada polling/ação. Sem ``s``: a análise vai dentro do painel, que já
    renderiza a lista."""
    return render_template(
        "partials/explorar_avaliador_analise.html",
        empresa_id=empresa_id,
        a=a,
        erro=erro,
        lista_oob=_render_lista(s, empresa_id, oob=True) if s is not None else None,
        pilares=servico.organizar(carregar_regua(), a),
        paginas_sem_texto=json.loads(a.paginas_sem_texto_json or "[]"),
        min_caracteres_pagina=MIN_CARACTERES_PAGINA,
        pct_controles_ilegivel=round(FRACAO_CONTROLES_ILEGIVEL * 100),
        rotulo_status=ROTULO_STATUS,
        rotulo_tipo=ROTULO_TIPO,
        processando=a.status in STATUS_EM_PROCESSAMENTO,
        texto_disponivel=a.texto_json is not None,
        dias_retencao=servico.dias_retencao(),
    )


def _analise_da_empresa(s, empresa_id: int, aid: int):
    a = s.get(AvaliadorAnalise, aid)
    return a if a is not None and a.empresa_id == empresa_id else None


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
    form = {"descricao": descricao, "texto": texto, "url": url}
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
