"""CRUD REST de empresas (Bloco 2).

Reaproveitado de: ``pdpa-v2/backend.py`` lns. 1924-2091 (rotas
``/api/empresa*`` inline no monólito v2).

Adaptações vs v2:
- Rotas id-based em vez de nome-based (REST: ``/api/empresas/<int:id>``);
- SQLAlchemy 2.0 (substitui ``sqlite3.Cursor`` + SQL raw);
- Desacoplado de fontes/pipeline — cadastro puro (v2 ``POST /api/empresa/add``
  acoplava Google Places auto-register + pipeline + diagnóstico);
- Filtragem por papel adiada para o briefing 04 (JWT + papéis);
- Remove o hack ``PRAGMA foreign_keys = OFF`` do v2 no DELETE — v3 já tem
  cascade por FK + cascade ORM funcionando (validado no Bloco 1).
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from flask import Blueprint, Response, jsonify, request

from src.auth import (
    PAPEL_LOYALL,
    cliente_pode_ver_empresa,
    get_current_user,
    login_required,
    loyall_required,
)
from src.models.empresa import Empresa
from src.utils.db import db_session


empresas_bp = Blueprint("empresas", __name__, url_prefix="/api/empresas")


def _serialize(e: Empresa) -> Dict[str, Any]:
    """Converte uma Empresa para dict serializável em JSON."""
    return {
        "id": e.id,
        "nome": e.nome,
        "razao_social": e.razao_social,
        "cnpj": e.cnpj,
        "setor": e.setor,
        "site": e.site,
        "observacao": e.observacao,
        "branding_json": e.branding_json,
        "criada_em": e.criada_em.isoformat() if e.criada_em else None,
        "atualizada_em": e.atualizada_em.isoformat() if e.atualizada_em else None,
    }


@empresas_bp.route("/", methods=["GET"])
@login_required
def listar_empresas() -> Response:
    """Lista empresas. Loyall vê todas; cliente vê só a própria."""
    user = get_current_user()
    with db_session() as session:
        query = session.query(Empresa).order_by(Empresa.nome)
        if user.papel != PAPEL_LOYALL:
            query = query.filter(Empresa.id == user.empresa_id)
        empresas = query.all()
        return jsonify([_serialize(e) for e in empresas])


@empresas_bp.route("/<int:empresa_id>", methods=["GET"])
@cliente_pode_ver_empresa("empresa_id")
def obter_empresa(empresa_id: int):
    """Retorna detalhes de uma empresa específica."""
    with db_session() as session:
        e = session.get(Empresa, empresa_id)
        if e is None:
            return jsonify({"erro": "Empresa não encontrada"}), 404
        return jsonify(_serialize(e))


@empresas_bp.route("/", methods=["POST"])
@loyall_required
def criar_empresa():
    """Cria uma nova empresa.

    Body JSON (campos):
        - ``nome`` (str, obrigatório, único)
        - ``razao_social`` (str, opcional)
        - ``cnpj`` (str, opcional, único)
        - ``setor`` (str, opcional)
        - ``branding_json`` (str, opcional — JSON serializado em string)

    Returns:
        201 com o objeto criado, ou 400/409 em erro de validação.
    """
    data = request.get_json(silent=True) or {}
    nome = data.get("nome")
    if not nome:
        return jsonify({"erro": "nome é obrigatório"}), 400

    with db_session() as session:
        ja_existe = session.query(Empresa).filter_by(nome=nome).first()
        if ja_existe:
            return jsonify({"erro": f"Empresa '{nome}' já existe"}), 409

        e = Empresa(
            nome=nome,
            razao_social=data.get("razao_social"),
            cnpj=data.get("cnpj"),
            setor=data.get("setor"),
            site=data.get("site"),
            observacao=data.get("observacao"),
            branding_json=data.get("branding_json"),
        )
        session.add(e)
        session.flush()
        return jsonify(_serialize(e)), 201


@empresas_bp.route("/<int:empresa_id>", methods=["PUT"])
@loyall_required
def atualizar_empresa(empresa_id: int):
    """Atualiza campos editáveis de uma empresa existente."""
    data = request.get_json(silent=True) or {}
    with db_session() as session:
        e = session.get(Empresa, empresa_id)
        if e is None:
            return jsonify({"erro": "Empresa não encontrada"}), 404
        for campo in (
            "nome",
            "razao_social",
            "cnpj",
            "setor",
            "site",
            "observacao",
            "branding_json",
        ):
            if campo in data:
                setattr(e, campo, data[campo])
        e.atualizada_em = datetime.utcnow()
        session.flush()
        return jsonify(_serialize(e))


@empresas_bp.route("/<int:empresa_id>", methods=["DELETE"])
@loyall_required
def remover_empresa(empresa_id: int):
    """Remove uma empresa.

    A cascata para ``locais``, ``agrupamentos`` e ``fontes`` é feita
    automaticamente: ON DELETE CASCADE na FK + ``cascade='all, delete-orphan'``
    no relationship. ``usuarios`` não cascata (Usuario.empresa_id é
    nullable, admin_loyall pode existir sem empresa).
    """
    with db_session() as session:
        e = session.get(Empresa, empresa_id)
        if e is None:
            return jsonify({"erro": "Empresa não encontrada"}), 404
        nome = e.nome
        session.delete(e)
        return jsonify({"removido": True, "id": empresa_id, "nome": nome})


# ── Rotas aninhadas (Bloco 4 — CP2) ──────────────────────────────────────
# Delegam para handlers nos blueprints de Agrupamento / Local / Fonte.


@empresas_bp.route("/<int:empresa_id>/agrupamentos", methods=["GET"])
@cliente_pode_ver_empresa("empresa_id")
def listar_agrupamentos_da_empresa(empresa_id: int):
    from src.api.agrupamentos import listar_agrupamentos_da_empresa as h

    return h(empresa_id)


@empresas_bp.route("/<int:empresa_id>/agrupamentos", methods=["POST"])
@loyall_required
def criar_agrupamento_na_empresa(empresa_id: int):
    from src.api.agrupamentos import criar_agrupamento_na_empresa as h

    return h(empresa_id)


@empresas_bp.route("/<int:empresa_id>/locais", methods=["GET"])
@cliente_pode_ver_empresa("empresa_id")
def listar_locais_da_empresa(empresa_id: int):
    from src.api.locais import listar_locais_da_empresa as h

    return h(empresa_id)


@empresas_bp.route("/<int:empresa_id>/locais", methods=["POST"])
@cliente_pode_ver_empresa("empresa_id")
def criar_local_na_empresa(empresa_id: int):
    from src.api.locais import criar_local_na_empresa as h

    return h(empresa_id)


@empresas_bp.route("/<int:empresa_id>/fontes", methods=["GET"])
@cliente_pode_ver_empresa("empresa_id")
def listar_fontes_da_empresa(empresa_id: int):
    from src.api.fontes import listar_fontes_da_empresa as h

    return h(empresa_id)


@empresas_bp.route("/<int:empresa_id>/fontes", methods=["POST"])
@cliente_pode_ver_empresa("empresa_id")
def criar_fonte_na_empresa(empresa_id: int):
    from src.api.fontes import criar_fonte_na_empresa as h

    return h(empresa_id)


@empresas_bp.route("/<int:empresa_id>/verbatins", methods=["GET"])
def listar_verbatins_da_empresa(empresa_id: int):
    from src.api.verbatins import listar_verbatins_da_empresa as h

    return h(empresa_id)


@empresas_bp.route("/<int:empresa_id>/verbatins/exportar.xlsx", methods=["GET"])
def exportar_verbatins_xlsx(empresa_id: int):
    from src.api.verbatins import exportar_xlsx_da_empresa as h

    return h(empresa_id)


@empresas_bp.route("/<int:empresa_id>/coletas-em-andamento", methods=["GET"])
def coletas_em_andamento_da_empresa(empresa_id: int):
    from src.api.monitoramento import coletas_em_andamento_da_empresa as h

    return h(empresa_id)


@empresas_bp.route("/<int:empresa_id>/painel/nivel1", methods=["GET"])
def painel_nivel1(empresa_id: int):
    from src.api.painel import painel_nivel1 as h

    return h(empresa_id)


@empresas_bp.route("/<int:empresa_id>/painel/nivel2", methods=["GET"])
def painel_nivel2(empresa_id: int):
    from src.api.painel import painel_nivel2 as h

    return h(empresa_id)


@empresas_bp.route("/<int:empresa_id>/painel/exportar.xlsx", methods=["GET"])
def exportar_painel_xlsx(empresa_id: int):
    from src.api.painel import exportar_painel_xlsx as h

    return h(empresa_id)


@empresas_bp.route("/<int:empresa_id>/painel/leitura", methods=["GET"])
def painel_leitura(empresa_id: int):
    from src.api.painel import painel_leitura as h

    return h(empresa_id)


# ── Temas (Bloco 6) ─────────────────────────────────────────────────


@empresas_bp.route("/<int:empresa_id>/temas", methods=["GET"])
def listar_temas_da_empresa(empresa_id: int):
    from src.api.temas import listar_temas_da_empresa as h

    return h(empresa_id)


@empresas_bp.route("/<int:empresa_id>/temas", methods=["POST"])
def criar_tema_manual(empresa_id: int):
    from src.api.temas import criar_tema_manual as h

    return h(empresa_id)


@empresas_bp.route("/<int:empresa_id>/painel/temas", methods=["GET"])
def painel_temas(empresa_id: int):
    from src.api.temas import painel_temas as h

    return h(empresa_id)


@empresas_bp.route("/<int:empresa_id>/temas/cruzamentos", methods=["GET"])
def painel_cruzamentos(empresa_id: int):
    from src.api.temas import painel_cruzamentos as h

    return h(empresa_id)


@empresas_bp.route("/<int:empresa_id>/temas/reprocessar", methods=["POST"])
def reprocessar_temas_empresa(empresa_id: int):
    from src.api.temas import reprocessar_temas_empresa as h

    return h(empresa_id)


@empresas_bp.route("/import-cadastro", methods=["POST"])
@loyall_required
def import_cadastro():
    """Importa cadastro hierárquico via Excel padronizado (Bloco 4 — CP3).

    Form fields:
        - ``arquivo``: ``.xlsx`` template simples ou completo (obrigatório).
        - ``sobrescrever``: ``"true"``/``"false"`` (opcional, default false).

    Detecção automática do template:
        - aba ``02 Agrupamentos`` presente → template completo
        - ausente → template simples

    Returns:
        200 com stats da importação se OK (campos: empresa_id, template,
        agrupamentos_criados/pulados, locais_criados/pulados,
        fontes_criadas/puladas).
        400 com lista de erros se houver problema de validação (nada é
        gravado em caso de erro — atomicidade).
    """
    if "arquivo" not in request.files:
        return jsonify({"erro": "arquivo é obrigatório"}), 400
    arquivo = request.files["arquivo"]
    if not arquivo.filename:
        return jsonify({"erro": "nome de arquivo vazio"}), 400

    sobrescrever = request.form.get("sobrescrever", "false").lower() == "true"

    suffix = Path(arquivo.filename).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        arquivo.save(str(tmp_path))
        from src.coletor.excel_cadastro import importar_cadastro

        stats = importar_cadastro(tmp_path, sobrescrever=sobrescrever)
    finally:
        tmp_path.unlink(missing_ok=True)

    if stats.get("erros"):
        return jsonify(stats), 400
    return jsonify(stats), 200
