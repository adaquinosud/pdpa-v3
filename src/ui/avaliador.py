"""Rotas do Avaliador de documentos — aba do Explorar, SÓ admin Loyall nesta entrega.

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
from src.avaliador.extracao import LIMITE_BYTES, MIN_CARACTERES_PAGINA, DocumentoRecusado
from src.avaliador.regua import GRUPO_PRECO_PERGUNTA, carregar_regua
from src.avaliador.servico import AvaliacaoRecusada
from src.models.avaliador import STATUS_EM_PROCESSAMENTO, STATUS_LENDO, AvaliadorAnalise
from src.ui import loyall_required_ui, ui_bp
from src.utils.db import db_session

ROTULO_VEREDITO = {
    "respondida": "Respondida",
    "em_parte": "Em parte",
    "sem_resposta": "Sem resposta",
}
ROTULO_STATUS = {
    "pendente": "Na fila",
    "classificando": "Identificando o tipo do documento",
    "lendo": "Lendo as perguntas",
    "fechando": "Escrevendo a leitura do fim",
    "pronta": "Pronta",
    "falhou": "Falhou",
}


def _lista(s, empresa_id: int):
    return (
        s.query(AvaliadorAnalise)
        .filter_by(empresa_id=empresa_id)
        .order_by(AvaliadorAnalise.criado_em.desc())
        .limit(30)
        .all()
    )


def _painel(s, empresa_id: int, erro=None, analise_html=None):
    return render_template(
        "partials/explorar_avaliador.html",
        empresa_id=empresa_id,
        analises=_lista(s, empresa_id),
        rotulo_status=ROTULO_STATUS,
        dias_retencao=servico.dias_retencao(),
        limite_mb=LIMITE_BYTES // (1024 * 1024),
        erro=erro,
        analise_html=analise_html,
    )


def _view_analise(a: AvaliadorAnalise) -> dict:
    """Monta o que a tela mostra: perguntas que valem por bloco (com o texto da frase
    buscado pelo id), as que não valem declaradas, o bloco do preço do P1."""
    regua = carregar_regua()
    visiveis = {v["codigo"]: v for v in servico.vereditos_visiveis(regua, a)}
    valem = set(visiveis)
    blocos = []
    for codigo_bloco, bloco in regua.blocos.items():
        itens = []
        for p in regua.perguntas:
            if p.bloco != codigo_bloco:
                continue
            v = visiveis.get(p.codigo)
            item = {"p": p, "vale": p.codigo in valem, "v": v}
            if v and v.get("frase_id"):
                item["frase"] = regua.texto_frase(v["frase_id"])
            itens.append(item)
        blocos.append({"pergunta": bloco["pergunta"], "itens": itens})
    p1 = visiveis.get("P1") or {}
    preco = None
    if p1.get("pergunta_anexo"):
        preco = {"pergunta": regua.texto_frase(regua.ids_grupo(GRUPO_PRECO_PERGUNTA)[0])}
    elif p1.get("frase_id_preco"):
        preco = {"frase": regua.texto_frase(p1["frase_id_preco"])}
    tipo = regua.tipos.get(a.tipo) if a.tipo else None
    res = json.loads(a.resultado_json or "{}")
    return {
        "a": a,
        "blocos": blocos,
        "preco": preco,
        "tipo": tipo,
        "tipos": list(regua.tipos.values()),
        "paginas_sem_texto": json.loads(a.paginas_sem_texto_json or "[]"),
        "min_caracteres_pagina": MIN_CARACTERES_PAGINA,
        "rotulo_veredito": ROTULO_VEREDITO,
        "rotulo_status": ROTULO_STATUS,
        "processando": a.status in STATUS_EM_PROCESSAMENTO,
        "progresso": (
            (len([c for c in valem if c in res]), len(valem)) if a.status == STATUS_LENDO else None
        ),
        "texto_disponivel": a.texto_json is not None,
        "dias_retencao": servico.dias_retencao(),
    }


def _render_analise(empresa_id: int, a: AvaliadorAnalise, erro=None) -> str:
    return render_template(
        "partials/explorar_avaliador_analise.html",
        empresa_id=empresa_id,
        erro=erro,
        **_view_analise(a),
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
    arquivo = request.files.get("arquivo")
    with db_session() as s:
        if arquivo is None or not arquivo.filename:
            return _painel(s, empresa_id, erro="Escolha um arquivo .pptx ou .pdf.")
        if (request.content_length or 0) > LIMITE_BYTES + 1024 * 1024:
            return _painel(
                s, empresa_id, erro=f"Arquivo maior que {LIMITE_BYTES // (1024 * 1024)} MB."
            )
        dados = arquivo.read(LIMITE_BYTES + 1)  # o limite de verdade é checado na extração
        try:
            a = servico.criar_analise(s, empresa_id, get_current_user().id, arquivo.filename, dados)
        except (DocumentoRecusado, AvaliacaoRecusada) as e:
            return _painel(s, empresa_id, erro=str(e))
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
        return _render_analise(empresa_id, a)


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
            return _render_analise(empresa_id, a, erro=str(e))
        s.commit()
        if a.status == "pendente":
            servico.disparar(a.id, app=current_app._get_current_object())
        return _render_analise(empresa_id, a)


@ui_bp.route("/empresas/<int:empresa_id>/explorar/avaliador/<int:aid>/tipo", methods=["POST"])
@loyall_required_ui
def avaliador_tipo(empresa_id: int, aid: int):
    tipo = request.form.get("tipo", "")
    return _acao(empresa_id, aid, lambda s, a: servico.corrigir_tipo(s, a, tipo))


@ui_bp.route(
    "/empresas/<int:empresa_id>/explorar/avaliador/<int:aid>/preco-anexo", methods=["POST"]
)
@loyall_required_ui
def avaliador_preco_anexo(empresa_id: int, aid: int):
    em_anexo = request.form.get("em_anexo") == "sim"
    return _acao(empresa_id, aid, lambda s, a: servico.responder_anexo(a, em_anexo))


@ui_bp.route("/empresas/<int:empresa_id>/explorar/avaliador/<int:aid>/retomar", methods=["POST"])
@loyall_required_ui
def avaliador_retomar(empresa_id: int, aid: int):
    return _acao(empresa_id, aid, lambda s, a: servico.retomar(a))


@ui_bp.route("/empresas/<int:empresa_id>/explorar/avaliador/<int:aid>/concluir", methods=["POST"])
@loyall_required_ui
def avaliador_concluir(empresa_id: int, aid: int):
    return _acao(empresa_id, aid, lambda s, a: servico.concluir(a))
