"""CRUD REST de Locais (Bloco 4 — CP2).

Locais são as unidades operacionais da Empresa (lojas, terminais, sites,
apps). Podem opcionalmente pertencer a um Agrupamento (one-to-many).

Endpoints:
    - POST /api/empresas/<empresa_id>/locais  (criar; aceita agrupamento_id opcional)
    - GET  /api/empresas/<empresa_id>/locais  (listar; query ?agrupamento_id=N filtra)
    - GET  /api/locais/<id>                   (detalhe)
    - PUT  /api/locais/<id>                   (atualizar)
    - DELETE /api/locais/<id>                 (excluir; fontes do local cascateiam
      via ON DELETE CASCADE da FK em fontes — quando a Fonte aponta para o local)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from src.auth import (
    cliente_pode_ver_empresa,
    login_required,
    verificar_acesso_empresa,
)
from src.models.agrupamento import Agrupamento
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.local import Local
from src.utils.db import db_session


locais_bp = Blueprint("locais", __name__, url_prefix="/api/locais")


def serialize_local(local: Local) -> Dict[str, Any]:
    """Converte Local em dict serializável."""
    return {
        "id": local.id,
        "empresa_id": local.empresa_id,
        "agrupamento_id": local.agrupamento_id,
        "nome": local.nome,
        "endereco": local.endereco,
        "cidade": local.cidade,
        "uf": local.uf,
        "pais": local.pais,
        "place_id_google": local.place_id_google,
        "latitude": local.latitude,
        "longitude": local.longitude,
        "status": local.status,
        "data_inicio_operacao": (
            local.data_inicio_operacao.isoformat() if local.data_inicio_operacao else None
        ),
        "observacao": local.observacao,
        # CP-impacto-rs: inputs do LTV + LTV derivado (ticket×frequencia) + origem.
        "ticket_medio": local.ticket_medio,
        "frequencia": local.frequencia,
        "ltv_origem": local.ltv_origem,
        "ltv": _ltv_local(local),
        "criado_em": local.criado_em.isoformat() if local.criado_em else None,
    }


def _ltv_local(local: Local):
    from src.governanca.impacto_rs import ltv_loja

    return ltv_loja(local)


_CAMPOS_EDITAVEIS = (
    "nome",
    "agrupamento_id",
    "endereco",
    "cidade",
    "uf",
    "pais",
    "place_id_google",
    "latitude",
    "longitude",
    "status",
    "data_inicio_operacao",
    "observacao",
    "ticket_medio",
    "frequencia",
    "ltv_origem",
)


@locais_bp.route("/<int:local_id>", methods=["GET"])
@login_required
def obter_local(local_id: int):
    with db_session() as session:
        local = session.get(Local, local_id)
        if local is None:
            return jsonify({"erro": "Local não encontrado"}), 404
        erro = verificar_acesso_empresa(local.empresa_id)
        if erro:
            return erro
        return jsonify(serialize_local(local))


@locais_bp.route("/<int:local_id>", methods=["PUT"])
@login_required
def atualizar_local(local_id: int):
    data = request.get_json(silent=True) or {}
    with db_session() as session:
        local = session.get(Local, local_id)
        if local is None:
            return jsonify({"erro": "Local não encontrado"}), 404
        erro = verificar_acesso_empresa(local.empresa_id)
        if erro:
            return erro

        # Valida agrupamento_id se fornecido (precisa pertencer à mesma empresa)
        if "agrupamento_id" in data and data["agrupamento_id"] is not None:
            ag = session.get(Agrupamento, data["agrupamento_id"])
            if ag is None or ag.empresa_id != local.empresa_id:
                return (
                    jsonify(
                        {
                            "erro": "agrupamento_id inválido — deve pertencer à "
                            "mesma empresa do local"
                        }
                    ),
                    400,
                )

        for campo in _CAMPOS_EDITAVEIS:
            if campo in data:
                setattr(local, campo, data[campo])
        # Editar ticket/frequência à mão = valor próprio: marca origem (a menos
        # que o cliente já tenha mandado ltv_origem explícito, ex.: pré-preench).
        if ("ticket_medio" in data or "frequencia" in data) and "ltv_origem" not in data:
            local.ltv_origem = "proprio"
        local.atualizado_em = datetime.utcnow()
        session.flush()
        return jsonify(serialize_local(local))


@locais_bp.route("/<int:local_id>/ltv-sugestao", methods=["GET"])
@login_required
def sugerir_ltv_local(local_id: int):
    """Pré-preenchimento hierárquico do ticket/frequência (CP-impacto-rs):
    (i) valor próprio → (ii) última loja do mesmo agrupamento → (iii) IA.
    ``?ia=0`` desliga o nível IA. Retorna a sugestão + origem, ou 204 se não há
    sugestão (loja sem agrupamento e IA off/falha → preenchimento manual)."""
    from src.governanca.impacto_rs import prefill_ltv

    usar_ia = request.args.get("ia", "1") != "0"
    with db_session() as session:
        local = session.get(Local, local_id)
        if local is None:
            return jsonify({"erro": "Local não encontrado"}), 404
        erro = verificar_acesso_empresa(local.empresa_id)
        if erro:
            return erro
        sug = prefill_ltv(session, local, usar_ia=usar_ia)
        if sug is None:
            return ("", 204)
        return jsonify(sug)


@locais_bp.route("/<int:local_id>/inativar", methods=["PATCH"])
@login_required
def toggle_ativo_local(local_id: int):
    """Toggle entre ``status='ativo'`` e ``status='desativado'``.

    Opção (a) do briefing CP-A: locais usam o enum ``status`` existente
    (sem adicionar coluna ``ativo`` boolean separada).
    """
    with db_session() as session:
        local = session.get(Local, local_id)
        if local is None:
            return jsonify({"erro": "Local não encontrado"}), 404
        erro = verificar_acesso_empresa(local.empresa_id)
        if erro:
            return erro
        local.status = "desativado" if local.status == "ativo" else "ativo"
        session.flush()
        return jsonify(serialize_local(local))


@locais_bp.route("/<int:local_id>/fontes", methods=["GET"])
@login_required
def listar_fontes_do_local_route(local_id: int):
    from src.api.fontes import listar_fontes_do_local as h

    return h(local_id)


@locais_bp.route("/<int:local_id>/fontes", methods=["POST"])
@login_required
def criar_fonte_no_local_route(local_id: int):
    from src.api.fontes import criar_fonte_no_local as h

    return h(local_id)


@locais_bp.route("/<int:local_id>", methods=["DELETE"])
@login_required
def remover_local(local_id: int):
    """Remove um Local.

    Fontes que apontam para este local (entidade_tipo='local' AND
    entidade_id=<id>) NÃO cascateam automaticamente — a FK ``empresa_id``
    em fontes aponta para empresas, não para locais (modelo polimórfico
    light). Remoção manual aqui antes do delete do Local.
    """
    with db_session() as session:
        local = session.get(Local, local_id)
        if local is None:
            return jsonify({"erro": "Local não encontrado"}), 404
        erro = verificar_acesso_empresa(local.empresa_id)
        if erro:
            return erro
        nome = local.nome
        # Remove fontes do local (polimórfico — não há FK direta)
        fontes_do_local = (
            session.query(Fonte).filter_by(entidade_tipo="local", entidade_id=local_id).all()
        )
        for f in fontes_do_local:
            session.delete(f)
        session.delete(local)
        return jsonify({"removido": True, "id": local_id, "nome": nome})


# ── Endpoints aninhados sob /api/empresas/<id> ───────────────────────────


@cliente_pode_ver_empresa("empresa_id")
def listar_locais_da_empresa(empresa_id: int):
    """Handler reusado pelo blueprint de empresas. Suporta ?agrupamento_id=N."""
    with db_session() as session:
        empresa = session.get(Empresa, empresa_id)
        if empresa is None:
            return jsonify({"erro": "Empresa não encontrada"}), 404

        query = session.query(Local).filter_by(empresa_id=empresa_id)
        agrupamento_id_raw = request.args.get("agrupamento_id")
        if agrupamento_id_raw is not None:
            if agrupamento_id_raw.lower() == "null":
                query = query.filter(Local.agrupamento_id.is_(None))
            else:
                try:
                    query = query.filter_by(agrupamento_id=int(agrupamento_id_raw))
                except ValueError:
                    return jsonify({"erro": "agrupamento_id deve ser inteiro ou 'null'"}), 400

        locais = query.order_by(Local.nome).all()
        return jsonify([serialize_local(local) for local in locais])


@cliente_pode_ver_empresa("empresa_id")
def criar_local_na_empresa(empresa_id: int):
    """Handler reusado pelo blueprint de empresas."""
    data = request.get_json(silent=True) or {}
    nome = data.get("nome")
    if not nome:
        return jsonify({"erro": "nome é obrigatório"}), 400

    with db_session() as session:
        empresa = session.get(Empresa, empresa_id)
        if empresa is None:
            return jsonify({"erro": "Empresa não encontrada"}), 404

        agrupamento_id = data.get("agrupamento_id")
        if agrupamento_id is not None:
            ag = session.get(Agrupamento, agrupamento_id)
            if ag is None or ag.empresa_id != empresa_id:
                return (
                    jsonify(
                        {"erro": "agrupamento_id inválido — deve pertencer à " "mesma empresa"}
                    ),
                    400,
                )

        local = Local(
            empresa_id=empresa_id,
            agrupamento_id=agrupamento_id,
            nome=nome,
            endereco=data.get("endereco"),
            cidade=data.get("cidade"),
            uf=data.get("uf"),
            pais=data.get("pais", "BR"),
            place_id_google=data.get("place_id_google"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            status=data.get("status", "ativo"),
            observacao=data.get("observacao"),
        )
        session.add(local)
        session.flush()
        return jsonify(serialize_local(local)), 201
