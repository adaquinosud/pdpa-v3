"""Endpoints REST de anomalias (Monitoramento ML CP-5).

Exposto via empresas_bp:
- GET /api/empresas/<id>/anomalias  (lista persistida; filtros tipo/severidade/estado)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from flask import jsonify, request

from src.auth import cliente_pode_ver_empresa, get_current_user
from src.models.anomalia import AnomaliaDetectada
from src.utils.db import db_session

_SEV_RANK = {"critico": 2, "atencao": 1, "normal": 0}
ESTADOS_VALIDOS = {"pendente", "confirmado", "falso_positivo", "em_investigacao"}


def _serializar(a: AnomaliaDetectada) -> Dict[str, Any]:
    return {
        "id": a.id,
        "tipo": a.tipo,
        "agrupamento_id": a.agrupamento_id,
        "local_id": a.local_id,
        "subpilar": a.subpilar,
        "tema_id": a.tema_id,
        "cruzamento_id": a.cruzamento_id,
        "chave": a.chave,
        "score_final": a.score_final,
        "score_temporal": a.score_temporal,
        "score_cross_sectional": a.score_cross_sectional,
        "magnitude": a.magnitude,
        "direcao": a.direcao,
        "tendencia": a.tendencia,
        "severidade": a.severidade,
        "periodo": a.periodo,
        "leitura_editorial": a.leitura_editorial,
        "estado_validacao": a.estado_validacao,
        "revisada": a.revisada,
        "detectada_em": a.detectada_em.isoformat() if a.detectada_em else None,
    }


@cliente_pode_ver_empresa("empresa_id")
def listar_anomalias_da_empresa(empresa_id: int):
    """Lista anomalias persistidas da empresa. Filtros opcionais via query string:
    ``tipo`` (indicador|tema|cruzamento), ``severidade`` (critico|atencao),
    ``estado`` (pendente|confirmado|falso_positivo|em_investigacao)."""
    tipo = request.args.get("tipo")
    severidade = request.args.get("severidade")
    estado = request.args.get("estado")

    with db_session() as s:
        q = s.query(AnomaliaDetectada).filter(AnomaliaDetectada.empresa_id == empresa_id)
        if tipo:
            q = q.filter(AnomaliaDetectada.tipo == tipo)
        if severidade:
            q = q.filter(AnomaliaDetectada.severidade == severidade)
        if estado:
            q = q.filter(AnomaliaDetectada.estado_validacao == estado)
        linhas = q.all()
        itens = [_serializar(a) for a in linhas]

    itens.sort(key=lambda a: (-_SEV_RANK.get(a["severidade"], 0), -(a["score_final"] or 0)))
    return jsonify(
        {
            "total": len(itens),
            "por_severidade": {
                sev: sum(1 for i in itens if i["severidade"] == sev)
                for sev in ("critico", "atencao")
            },
            "anomalias": itens,
        }
    )


def aplicar_validacao(empresa_id: int, anomalia_id: int, estado: str, nota=None):
    """Atualiza estado_validacao de uma anomalia (uso compartilhado API+UI).
    Retorna (dict_serializado, erro_status) — erro_status None em sucesso."""
    if estado not in ESTADOS_VALIDOS:
        return None, 400
    user = get_current_user()
    with db_session() as s:
        a = s.get(AnomaliaDetectada, anomalia_id)
        if a is None or a.empresa_id != empresa_id:
            return None, 404
        a.estado_validacao = estado
        a.revisada = estado != "pendente"
        a.revisada_em = datetime.utcnow()
        a.revisada_por = user.id if user else None
        if nota is not None:
            a.nota_editorial = nota
        s.flush()
        out = _serializar(a)
    return out, None


@cliente_pode_ver_empresa("empresa_id")
def validar_anomalia(empresa_id: int, anomalia_id: int):
    """POST: marca a anomalia como confirmado | falso_positivo | em_investigacao
    | pendente. Body JSON ou form: ``estado`` (obrigatório), ``nota`` (opcional)."""
    dados = request.get_json(silent=True) or request.form
    estado = dados.get("estado")
    nota = dados.get("nota")
    out, erro = aplicar_validacao(empresa_id, anomalia_id, estado, nota)
    if erro == 400:
        return jsonify({"erro": f"estado inválido (use {sorted(ESTADOS_VALIDOS)})"}), 400
    if erro == 404:
        return jsonify({"erro": "anomalia não encontrada"}), 404
    return jsonify(out)
