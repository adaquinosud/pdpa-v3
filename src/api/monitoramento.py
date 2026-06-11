"""Endpoints de monitoramento de coletas (Bloco 4 CP-E).

Endpoints:
    GET /api/monitoramento/coletas
        Lista de execuções de coleta com filtros e paginação.
        Loyall vê tudo; cliente vê só da sua empresa.

    GET /api/monitoramento/coletas/<id>
        Detalhe de uma execução específica.

    GET /api/empresas/<id>/coletas-em-andamento
        Apenas execuções com ``status='rodando'`` da empresa.
        Usado pelo indicador inline na página de detalhe (polling HTMX).
"""

from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request

from src.auth import (
    PAPEL_LOYALL,
    cliente_pode_ver_empresa,
    get_current_user,
    login_required,
    verificar_acesso_empresa,
)
from src.models.coleta_execucao import ColetaExecucao
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.local import Local
from src.utils.db import db_session


monitoramento_bp = Blueprint("monitoramento", __name__, url_prefix="/api/monitoramento")


def _serialize_execucao(
    e: ColetaExecucao, empresa_map: dict, fonte_map: dict, local_map: dict
) -> Dict[str, Any]:
    fonte = fonte_map.get(e.fonte_id, {})
    dur = None
    if e.concluido_em is not None:
        dur = (e.concluido_em - e.iniciado_em).total_seconds()
    return {
        "id": e.id,
        "empresa_id": e.empresa_id,
        "empresa_nome": empresa_map.get(e.empresa_id),
        "fonte_id": e.fonte_id,
        "fonte_conector_tipo": fonte.get("conector_tipo"),
        "fonte_url": fonte.get("url"),
        "local_id": fonte.get("entidade_id") if fonte.get("entidade_tipo") == "local" else None,
        "local_nome": local_map.get(
            fonte.get("entidade_id") if fonte.get("entidade_tipo") == "local" else None
        ),
        "status": e.status,
        "iniciado_em": e.iniciado_em.isoformat() if e.iniciado_em else None,
        "concluido_em": e.concluido_em.isoformat() if e.concluido_em else None,
        "duracao_segundos": dur,
        "coletados": e.coletados,
        "novos": e.novos,
        "duplicados": e.duplicados,
        "erros": e.erros,
        "mensagem_erro": e.mensagem_erro,
        "custo_apify_centavos": e.custo_apify_centavos,
    }


@monitoramento_bp.route("/coletas", methods=["GET"])
@login_required
def listar_coletas():
    """Lista paginada de execuções de coleta.

    Filtros: ?status=rodando|concluido|erro, ?empresa_id=N, ?fonte_id=N,
             ?desde=YYYY-MM-DDTHH:MM (UTC; default: 24h atrás)
    """
    from datetime import datetime, timedelta

    user = get_current_user()
    try:
        pagina = int(request.args.get("pagina", "1"))
        por_pagina = min(200, max(1, int(request.args.get("por_pagina", "50"))))
    except ValueError:
        return jsonify({"erro": "pagina/por_pagina inválidos"}), 400
    pagina = max(1, pagina)

    with db_session() as s:
        q = s.query(ColetaExecucao)

        # Cliente vê só da própria empresa
        if user.papel != PAPEL_LOYALL:
            q = q.filter(ColetaExecucao.empresa_id == user.empresa_id)

        status = request.args.get("status")
        if status:
            if status not in ("rodando", "concluido", "erro"):
                return jsonify({"erro": "status inválido"}), 400
            q = q.filter(ColetaExecucao.status == status)

        empresa_id_raw = request.args.get("empresa_id")
        if empresa_id_raw:
            try:
                eid = int(empresa_id_raw)
            except ValueError:
                return jsonify({"erro": "empresa_id inválido"}), 400
            erro = verificar_acesso_empresa(eid)
            if erro:
                return erro
            q = q.filter(ColetaExecucao.empresa_id == eid)

        fonte_id_raw = request.args.get("fonte_id")
        if fonte_id_raw:
            try:
                q = q.filter(ColetaExecucao.fonte_id == int(fonte_id_raw))
            except ValueError:
                return jsonify({"erro": "fonte_id inválido"}), 400

        desde_raw = request.args.get("desde")
        if desde_raw:
            try:
                desde = datetime.fromisoformat(desde_raw)
            except ValueError:
                return jsonify({"erro": "desde inválido (YYYY-MM-DDTHH:MM)"}), 400
        else:
            desde = datetime.utcnow() - timedelta(hours=24)
        q = q.filter(ColetaExecucao.iniciado_em >= desde)

        total = q.count()
        execucoes = (
            q.order_by(ColetaExecucao.iniciado_em.desc())
            .offset((pagina - 1) * por_pagina)
            .limit(por_pagina)
            .all()
        )

        empresa_ids = {e.empresa_id for e in execucoes}
        fonte_ids = {e.fonte_id for e in execucoes}
        empresas_db = (
            s.query(Empresa).filter(Empresa.id.in_(empresa_ids)).all() if empresa_ids else []
        )
        fontes_db = s.query(Fonte).filter(Fonte.id.in_(fonte_ids)).all() if fonte_ids else []
        local_ids = {f.entidade_id for f in fontes_db if f.entidade_tipo == "local"}
        locais_db = s.query(Local).filter(Local.id.in_(local_ids)).all() if local_ids else []
        empresa_map = {e.id: e.nome for e in empresas_db}
        fonte_map = {
            f.id: {
                "conector_tipo": f.conector_tipo,
                "url": f.url,
                "entidade_tipo": f.entidade_tipo,
                "entidade_id": f.entidade_id,
            }
            for f in fontes_db
        }
        local_map = {loc.id: loc.nome for loc in locais_db}

        payload = [_serialize_execucao(e, empresa_map, fonte_map, local_map) for e in execucoes]

    return jsonify(
        {
            "total": total,
            "pagina": pagina,
            "por_pagina": por_pagina,
            "execucoes": payload,
        }
    )


@monitoramento_bp.route("/coletas/<int:execucao_id>", methods=["GET"])
@login_required
def obter_coleta(execucao_id: int):
    user = get_current_user()
    with db_session() as s:
        e = s.get(ColetaExecucao, execucao_id)
        if e is None:
            return jsonify({"erro": "Execução não encontrada"}), 404
        if user.papel != PAPEL_LOYALL and user.empresa_id != e.empresa_id:
            return jsonify({"erro": "Acesso negado"}), 403

        empresa = s.get(Empresa, e.empresa_id)
        fonte = s.get(Fonte, e.fonte_id)
        local = None
        if fonte is not None and fonte.entidade_tipo == "local":
            local = s.get(Local, fonte.entidade_id)
        empresa_map = {empresa.id: empresa.nome} if empresa else {}
        fonte_map = (
            {
                fonte.id: {
                    "conector_tipo": fonte.conector_tipo,
                    "url": fonte.url,
                    "entidade_tipo": fonte.entidade_tipo,
                    "entidade_id": fonte.entidade_id,
                }
            }
            if fonte
            else {}
        )
        local_map = {local.id: local.nome} if local else {}
        return jsonify(_serialize_execucao(e, empresa_map, fonte_map, local_map))


@cliente_pode_ver_empresa("empresa_id")
def coletas_em_andamento_da_empresa(empresa_id: int):
    """Handler reusado pelo blueprint de empresas. Devolve só status='rodando'.

    CP-status-preso: reapa órfãs (presas em 'rodando' > 1h — thread morta em
    deploy/restart do Render) ANTES de listar, pra a tela AUTO-CURAR sem depender
    de um novo disparo de coleta. ``re_marca_orfas`` é idempotente e NÃO toca
    coleta viva (< 1h = timeout-fonte 45min + margem)."""
    from src.coletor.orquestrador import re_marca_orfas

    re_marca_orfas()
    with db_session() as s:
        execucoes = (
            s.query(ColetaExecucao)
            .filter_by(empresa_id=empresa_id, status="rodando")
            .order_by(ColetaExecucao.iniciado_em.desc())
            .all()
        )
        # ID das fontes em andamento + coletados (até o momento)
        payload = [
            {
                "id": e.id,
                "fonte_id": e.fonte_id,
                "iniciado_em": e.iniciado_em.isoformat(),
                "coletados_ate_agora": (
                    s.query(__import__("src.models.verbatim", fromlist=["Verbatim"]).Verbatim)
                    .filter_by(fonte_id=e.fonte_id)
                    .filter(
                        __import__(
                            "src.models.verbatim", fromlist=["Verbatim"]
                        ).Verbatim.data_coleta
                        >= e.iniciado_em
                    )
                    .count()
                ),
            }
            for e in execucoes
        ]
    return jsonify({"em_andamento": payload, "total": len(payload)})
