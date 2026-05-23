"""CRUD REST de Agrupamentos (Bloco 4 — CP2).

Agrupamento é nível intermediário opcional entre Empresa e Local
(estrutura hierárquica do cadastro). Cliente final consome no Painel
Executivo; cadastro/edição é privilégio de ``loyall_admin`` (a controle
de papel será aplicado no CP4 — auth).

Endpoints:
    - POST /api/empresas/<empresa_id>/agrupamentos    (criar)
    - GET  /api/empresas/<empresa_id>/agrupamentos    (listar da empresa)
    - GET  /api/agrupamentos/<id>                     (detalhe)
    - PUT  /api/agrupamentos/<id>                     (atualizar)
    - DELETE /api/agrupamentos/<id>                   (excluir; locais com
      agrupamento_id apontando viram NULL via ON DELETE SET NULL)
"""

from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request

from src.models.agrupamento import Agrupamento
from src.models.empresa import Empresa
from src.utils.db import db_session


agrupamentos_bp = Blueprint("agrupamentos", __name__, url_prefix="/api/agrupamentos")


def serialize_agrupamento(a: Agrupamento) -> Dict[str, Any]:
    """Converte Agrupamento em dict serializável."""
    return {
        "id": a.id,
        "empresa_id": a.empresa_id,
        "nome": a.nome,
        "descricao": a.descricao,
        "tipo": a.tipo,
        "ativo": bool(a.ativo),
        "criado_em": a.criado_em.isoformat() if a.criado_em else None,
    }


@agrupamentos_bp.route("/<int:agrupamento_id>", methods=["GET"])
def obter_agrupamento(agrupamento_id: int):
    with db_session() as session:
        a = session.get(Agrupamento, agrupamento_id)
        if a is None:
            return jsonify({"erro": "Agrupamento não encontrado"}), 404
        return jsonify(serialize_agrupamento(a))


@agrupamentos_bp.route("/<int:agrupamento_id>", methods=["PUT"])
def atualizar_agrupamento(agrupamento_id: int):
    data = request.get_json(silent=True) or {}
    with db_session() as session:
        a = session.get(Agrupamento, agrupamento_id)
        if a is None:
            return jsonify({"erro": "Agrupamento não encontrado"}), 404
        for campo in ("nome", "descricao", "ativo"):
            if campo in data:
                setattr(a, campo, data[campo])
        session.flush()
        return jsonify(serialize_agrupamento(a))


@agrupamentos_bp.route("/<int:agrupamento_id>", methods=["DELETE"])
def remover_agrupamento(agrupamento_id: int):
    """Remove um Agrupamento.

    Locais que apontavam para este agrupamento ficam com
    ``agrupamento_id = NULL`` (ON DELETE SET NULL na FK da migration 011).
    """
    with db_session() as session:
        a = session.get(Agrupamento, agrupamento_id)
        if a is None:
            return jsonify({"erro": "Agrupamento não encontrado"}), 404
        nome = a.nome
        session.delete(a)
        return jsonify({"removido": True, "id": agrupamento_id, "nome": nome})


# ── Endpoints aninhados sob /api/empresas/<id> ───────────────────────────


def listar_agrupamentos_da_empresa(empresa_id: int):
    """Handler reusado pelo blueprint de empresas."""
    with db_session() as session:
        empresa = session.get(Empresa, empresa_id)
        if empresa is None:
            return jsonify({"erro": "Empresa não encontrada"}), 404
        ags = (
            session.query(Agrupamento)
            .filter_by(empresa_id=empresa_id)
            .order_by(Agrupamento.nome)
            .all()
        )
        return jsonify([serialize_agrupamento(a) for a in ags])


def criar_agrupamento_na_empresa(empresa_id: int):
    """Handler reusado pelo blueprint de empresas."""
    data = request.get_json(silent=True) or {}
    nome = data.get("nome")
    if not nome:
        return jsonify({"erro": "nome é obrigatório"}), 400

    with db_session() as session:
        empresa = session.get(Empresa, empresa_id)
        if empresa is None:
            return jsonify({"erro": "Empresa não encontrada"}), 404

        ja_existe = session.query(Agrupamento).filter_by(empresa_id=empresa_id, nome=nome).first()
        if ja_existe:
            return (
                jsonify({"erro": f"Agrupamento '{nome}' já existe para esta empresa"}),
                409,
            )

        ativo = data.get("ativo", True)
        a = Agrupamento(
            empresa_id=empresa_id,
            nome=nome,
            descricao=data.get("descricao"),
            ativo=bool(ativo),
        )
        session.add(a)
        session.flush()
        return jsonify(serialize_agrupamento(a)), 201
