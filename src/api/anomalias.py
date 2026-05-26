"""Endpoints REST de anomalias (Monitoramento ML CP-5).

Exposto via empresas_bp:
- GET /api/empresas/<id>/anomalias  (lista persistida; filtros tipo/severidade/estado)
"""

from __future__ import annotations

from typing import Any, Dict

from flask import jsonify, request

from src.auth import cliente_pode_ver_empresa
from src.models.anomalia import AnomaliaDetectada
from src.utils.db import db_session

_SEV_RANK = {"critico": 2, "atencao": 1, "normal": 0}


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
