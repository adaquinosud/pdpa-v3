"""CRUD REST de Fontes (Bloco 4 — CP2).

Fontes são os conectores de coleta (Google, Instagram, Tripadvisor, etc.)
amarrados a uma Empresa (via ``empresa_id``) e polimorficamente
a um Local OU à própria Empresa (via ``entidade_tipo`` + ``entidade_id``).

Endpoints:
    - POST /api/locais/<local_id>/fontes        (criar fonte do local)
    - GET  /api/locais/<local_id>/fontes        (listar fontes do local)
    - POST /api/empresas/<empresa_id>/fontes    (criar fonte direta da empresa)
    - GET  /api/empresas/<empresa_id>/fontes    (listar TODAS as fontes da empresa,
                                                 direta + via locais)
    - GET  /api/fontes/<id>                     (detalhe)
    - PUT  /api/fontes/<id>                     (atualizar)
    - DELETE /api/fontes/<id>                   (excluir)

Disparo da coleta continua em ``/api/coleta/disparar/<fonte_id>`` (CP6.3 do
Bloco 3). Esta API só lida com cadastro.

Lista canônica de conectores reconhecidos em ``CONECTORES_CONHECIDOS``.
Conectores fora da lista são aceitos com ``ativo=False`` (catalogação
manual sem scraper Apify) — útil para website, glassdoor, indeed que não
têm coletor ainda.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

from src.auth import (
    cliente_pode_ver_empresa,
    login_required,
    verificar_acesso_empresa,
)
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.local import Local
from src.utils.db import db_session


fontes_bp = Blueprint("fontes", __name__, url_prefix="/api/fontes")


# Conectores com coletor Apify implementado (ver src/coletor/).
CONECTORES_COM_SCRAPER = frozenset(
    {
        "google",
        "instagram",
        "facebook",
        "tripadvisor",
        "linkedin",
        "tiktok",
        "youtube",
        "appstore",
        "mercadolivre",
        "google_news",
    }
)

# Conectores reconhecidos como catalogação manual (sem scraper ativo).
CONECTORES_CATALOGADOS = frozenset(
    {
        "website",
        "glassdoor",
        "indeed",
        "reclame_aqui",
        "consumidor_gov",
        "amazon",
        "excel_manual",
    }
)

CONECTORES_CONHECIDOS = CONECTORES_COM_SCRAPER | CONECTORES_CATALOGADOS


def serialize_fonte(fonte: Fonte) -> Dict[str, Any]:
    """Converte Fonte em dict serializável."""
    return {
        "id": fonte.id,
        "empresa_id": fonte.empresa_id,
        "entidade_tipo": fonte.entidade_tipo,
        "entidade_id": fonte.entidade_id,
        "conector_tipo": fonte.conector_tipo,
        "url": fonte.url,
        "autenticacao_tipo": fonte.autenticacao_tipo,
        "status": fonte.status,
        "ativo": bool(fonte.ativo),
        "observacao": fonte.observacao,
        "ultima_coleta": (fonte.ultima_coleta.isoformat() if fonte.ultima_coleta else None),
        "criada_em": fonte.criada_em.isoformat() if fonte.criada_em else None,
    }


def _validar_conector(conector_tipo: str, ativo: bool) -> Optional[str]:
    """Valida o conector_tipo. Retorna mensagem de erro ou None se OK.

    - Conector com scraper: aceito em qualquer estado.
    - Conector catalogado (sem scraper): só aceito se ``ativo=False``.
    - Conector desconhecido: rejeitado.
    """
    if not conector_tipo or not isinstance(conector_tipo, str):
        return "conector_tipo é obrigatório"
    if conector_tipo in CONECTORES_COM_SCRAPER:
        return None
    if conector_tipo in CONECTORES_CATALOGADOS:
        if ativo:
            return (
                f"conector '{conector_tipo}' não tem scraper Apify — "
                f"cadastre com ativo=False (catalogação) ou use um conector com scraper"
            )
        return None
    return (
        f"conector_tipo '{conector_tipo}' desconhecido. "
        f"Aceitos: {sorted(CONECTORES_CONHECIDOS)}"
    )


@fontes_bp.route("/<int:fonte_id>", methods=["GET"])
@login_required
def obter_fonte(fonte_id: int):
    with db_session() as session:
        fonte = session.get(Fonte, fonte_id)
        if fonte is None:
            return jsonify({"erro": "Fonte não encontrada"}), 404
        erro = verificar_acesso_empresa(fonte.empresa_id)
        if erro:
            return erro
        return jsonify(serialize_fonte(fonte))


@fontes_bp.route("/<int:fonte_id>", methods=["PUT"])
@login_required
def atualizar_fonte(fonte_id: int):
    data = request.get_json(silent=True) or {}
    with db_session() as session:
        fonte = session.get(Fonte, fonte_id)
        if fonte is None:
            return jsonify({"erro": "Fonte não encontrada"}), 404
        erro = verificar_acesso_empresa(fonte.empresa_id)
        if erro:
            return erro

        if "conector_tipo" in data or "ativo" in data:
            novo_conector = data.get("conector_tipo", fonte.conector_tipo)
            novo_ativo = bool(data.get("ativo", fonte.ativo))
            erro = _validar_conector(novo_conector, novo_ativo)
            if erro:
                return jsonify({"erro": erro}), 400

        for campo in (
            "conector_tipo",
            "url",
            "autenticacao_tipo",
            "status",
            "ativo",
            "observacao",
        ):
            if campo in data:
                setattr(fonte, campo, data[campo])
        session.flush()
        return jsonify(serialize_fonte(fonte))


@fontes_bp.route("/<int:fonte_id>", methods=["DELETE"])
@login_required
def remover_fonte(fonte_id: int):
    with db_session() as session:
        fonte = session.get(Fonte, fonte_id)
        if fonte is None:
            return jsonify({"erro": "Fonte não encontrada"}), 404
        erro = verificar_acesso_empresa(fonte.empresa_id)
        if erro:
            return erro
        conector = fonte.conector_tipo
        session.delete(fonte)
        return jsonify({"removido": True, "id": fonte_id, "conector_tipo": conector})


# ── Helpers de criação polimórfica ───────────────────────────────────────


def _criar_fonte(
    empresa_id: int,
    entidade_tipo: str,
    entidade_id: int,
    data: Dict[str, Any],
):
    """Lógica comum de criação para nested routes."""
    conector_tipo = data.get("conector_tipo")
    url = data.get("url")
    if not url:
        return jsonify({"erro": "url é obrigatória"}), 400

    ativo = bool(data.get("ativo", True))
    erro = _validar_conector(conector_tipo, ativo)
    if erro:
        return jsonify({"erro": erro}), 400

    with db_session() as session:
        empresa = session.get(Empresa, empresa_id)
        if empresa is None:
            return jsonify({"erro": "Empresa não encontrada"}), 404

        if entidade_tipo == "local":
            local = session.get(Local, entidade_id)
            if local is None or local.empresa_id != empresa_id:
                return (
                    jsonify({"erro": "Local não encontrado ou não pertence " "à empresa indicada"}),
                    404,
                )

        fonte = Fonte(
            empresa_id=empresa_id,
            entidade_tipo=entidade_tipo,
            entidade_id=entidade_id,
            conector_tipo=conector_tipo,
            url=url,
            autenticacao_tipo=data.get("autenticacao_tipo", "publica"),
            status=data.get("status", "ativa"),
            ativo=ativo,
            observacao=data.get("observacao"),
        )
        session.add(fonte)
        session.flush()
        return jsonify(serialize_fonte(fonte)), 201


# ── Endpoints aninhados ──────────────────────────────────────────────────


def listar_fontes_do_local(local_id: int):
    """Handler reusado pelo blueprint de locais."""
    with db_session() as session:
        local = session.get(Local, local_id)
        if local is None:
            return jsonify({"erro": "Local não encontrado"}), 404
        erro = verificar_acesso_empresa(local.empresa_id)
        if erro:
            return erro
        fontes = (
            session.query(Fonte)
            .filter_by(entidade_tipo="local", entidade_id=local_id)
            .order_by(Fonte.conector_tipo)
            .all()
        )
        return jsonify([serialize_fonte(f) for f in fontes])


def criar_fonte_no_local(local_id: int):
    """Handler reusado pelo blueprint de locais."""
    with db_session() as session:
        local = session.get(Local, local_id)
        if local is None:
            return jsonify({"erro": "Local não encontrado"}), 404
        erro = verificar_acesso_empresa(local.empresa_id)
        if erro:
            return erro
        empresa_id = local.empresa_id
    return _criar_fonte(
        empresa_id=empresa_id,
        entidade_tipo="local",
        entidade_id=local_id,
        data=request.get_json(silent=True) or {},
    )


@cliente_pode_ver_empresa("empresa_id")
def listar_fontes_da_empresa(empresa_id: int):
    """Handler reusado pelo blueprint de empresas. Inclui fontes diretas
    da empresa E fontes dos locais dela."""
    with db_session() as session:
        empresa = session.get(Empresa, empresa_id)
        if empresa is None:
            return jsonify({"erro": "Empresa não encontrada"}), 404
        fontes = (
            session.query(Fonte)
            .filter_by(empresa_id=empresa_id)
            .order_by(Fonte.entidade_tipo, Fonte.conector_tipo)
            .all()
        )
        return jsonify([serialize_fonte(f) for f in fontes])


@cliente_pode_ver_empresa("empresa_id")
def criar_fonte_na_empresa(empresa_id: int):
    """Handler reusado pelo blueprint de empresas. entidade_tipo='empresa'."""
    return _criar_fonte(
        empresa_id=empresa_id,
        entidade_tipo="empresa",
        entidade_id=empresa_id,
        data=request.get_json(silent=True) or {},
    )
