"""CRUD REST de Verbatins (Bloco 4 CP-C).

Endpoints:
    - GET    /api/empresas/<id>/verbatins  (lista filtrada+paginada)
    - GET    /api/verbatins/<id>           (detalhe + histórico de reclassificação)
    - PATCH  /api/verbatins/<id>/reclassificar
    - DELETE /api/verbatins/<id>

Filtros aceitos no GET list (via query string):
    - agrupamento_id (int)
    - local_id (int) — incluir 'null' para verbatins sem local
    - fonte_id (int)
    - data_de (YYYY-MM-DD)  — filtra data_criacao_original >=
    - data_ate (YYYY-MM-DD) — filtra data_criacao_original <=
    - subpilar (str)
    - tipo (str)
    - q (str) — busca substring case-insensitive no campo texto
    - pagina (int, default 1)
    - por_pagina (int, default 50, max 200)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from src.auth import (
    cliente_pode_ver_empresa,
    get_current_user,
    login_required,
    verificar_acesso_empresa,
)
from src.classifier.classifier_v3 import SUBPILARES_VALIDOS, TIPOS_VALIDOS
from src.models.agrupamento import Agrupamento
from src.models.fonte import Fonte
from src.models.local import Local
from src.models.verbatim import Verbatim
from src.models.verbatim_reclassificacao import VerbatimReclassificacao
from src.utils.db import db_session


verbatins_bp = Blueprint("verbatins", __name__, url_prefix="/api/verbatins")


POR_PAGINA_MAX = 200
POR_PAGINA_DEFAULT = 50
EXPORTAR_XLSX_MAX_LINHAS = 50_000


def _aplicar_filtros_listagem(q, empresa_id: int, s):
    """Aplica os mesmos filtros da listagem na query base.

    Devolve ``(q, erro_response)``. Se ``erro_response`` é não-None, é uma
    tupla ``(json, status)`` que deve ser retornada pelo caller. Caso
    contrário, ``q`` está pronta pra ser executada.
    """
    ag_id_raw = request.args.get("agrupamento_id")
    if ag_id_raw:
        try:
            ag_id = int(ag_id_raw)
        except ValueError:
            return q, (jsonify({"erro": "agrupamento_id deve ser inteiro"}), 400)
        locais_do_ag = [
            lid
            for (lid,) in s.query(Local.id)
            .filter_by(empresa_id=empresa_id, agrupamento_id=ag_id)
            .all()
        ]
        if locais_do_ag:
            q = q.filter(Verbatim.local_id.in_(locais_do_ag))
        else:
            q = q.filter(Verbatim.id.is_(None))  # resultado vazio sem erro

    local_id_raw = request.args.get("local_id")
    if local_id_raw:
        if local_id_raw.lower() == "null":
            q = q.filter(Verbatim.local_id.is_(None))
        else:
            try:
                q = q.filter(Verbatim.local_id == int(local_id_raw))
            except ValueError:
                return q, (jsonify({"erro": "local_id deve ser inteiro ou 'null'"}), 400)

    fonte_id_raw = request.args.get("fonte_id")
    if fonte_id_raw:
        try:
            q = q.filter(Verbatim.fonte_id == int(fonte_id_raw))
        except ValueError:
            return q, (jsonify({"erro": "fonte_id deve ser inteiro"}), 400)

    data_de = request.args.get("data_de")
    if data_de:
        try:
            d = datetime.fromisoformat(data_de)
            q = q.filter(Verbatim.data_criacao_original >= d)
        except ValueError:
            return q, (jsonify({"erro": "data_de deve ser YYYY-MM-DD"}), 400)

    data_ate = request.args.get("data_ate")
    if data_ate:
        try:
            d = datetime.fromisoformat(data_ate)
            q = q.filter(Verbatim.data_criacao_original <= d)
        except ValueError:
            return q, (jsonify({"erro": "data_ate deve ser YYYY-MM-DD"}), 400)

    subpilar = request.args.get("subpilar")
    if subpilar:
        q = q.filter(Verbatim.subpilar == subpilar)

    # B5 ext. CP-2: filtra verbatins sem classificação (subpilar NULL).
    # Usado pela linha "sem classificação" do painel para inspeção dos
    # verbatins que o classifier não conseguiu processar.
    sem_classif = request.args.get("sem_classificacao")
    if sem_classif in ("1", "true", "True"):
        q = q.filter(Verbatim.subpilar.is_(None))

    # B6 CP-5: filtra verbatins vinculados a um tema específico.
    tema_id_raw = request.args.get("tema_id")
    if tema_id_raw:
        try:
            tema_id = int(tema_id_raw)
        except ValueError:
            return q, (jsonify({"erro": "tema_id deve ser inteiro"}), 400)
        from src.models.temas import VerbatimTema as _VT

        sub_ids = s.query(_VT.verbatim_id).filter(_VT.tema_id == tema_id).distinct()
        q = q.filter(Verbatim.id.in_(sub_ids))

    tipo = request.args.get("tipo")
    if tipo:
        q = q.filter(Verbatim.tipo == tipo)

    esconder_ro = request.args.get("esconder_rating_only")
    if esconder_ro in ("1", "true", "True"):
        q = q.filter(Verbatim.tem_texto.is_(True))

    rating = request.args.get("rating")
    if rating:
        try:
            q = q.filter(Verbatim.rating == int(rating))
        except ValueError:
            return q, (jsonify({"erro": "rating deve ser inteiro 1-5"}), 400)

    busca = (request.args.get("q") or "").strip()
    if busca:
        like = f"%{busca}%"
        q = q.filter(or_(Verbatim.texto.ilike(like), Verbatim.justificativa.ilike(like)))

    return q, None


def _serialize_verbatim(
    v: Verbatim, ag_map: dict, local_map: dict, fonte_map: dict
) -> Dict[str, Any]:
    """Serializa Verbatim com nomes resolvidos (sem N+1 queries no loop)."""
    fonte = fonte_map.get(v.fonte_id, {})
    return {
        "id": v.id,
        "empresa_id": v.empresa_id,
        "local_id": v.local_id,
        "local_nome": local_map.get(v.local_id) if v.local_id else None,
        "agrupamento_id": fonte.get("agrupamento_id_via_local"),
        "agrupamento_nome": (
            ag_map.get(fonte.get("agrupamento_id_via_local"))
            if fonte.get("agrupamento_id_via_local")
            else None
        ),
        "fonte_id": v.fonte_id,
        "fonte_conector_tipo": fonte.get("conector_tipo"),
        "fonte_url": fonte.get("url"),
        "texto": v.texto,
        "tem_texto": bool(v.tem_texto),
        "rating": v.rating,
        "review_id_externo": v.review_id_externo,
        "autor": v.autor,
        "data_criacao_original": (
            v.data_criacao_original.isoformat() if v.data_criacao_original else None
        ),
        "data_coleta": v.data_coleta.isoformat() if v.data_coleta else None,
        "subpilar": v.subpilar,
        "tipo": v.tipo,
        "confianca": v.confianca,
        "justificativa": v.justificativa,
        "prompt_versao": v.prompt_versao,
        "reclassificado_em": v.reclassificado_em.isoformat() if v.reclassificado_em else None,
        "reclassificado_por": v.reclassificado_por,
        "subpilar_anterior": v.subpilar_anterior,
        "tipo_anterior": v.tipo_anterior,
    }


def _serialize_reclassificacao(r: VerbatimReclassificacao) -> Dict[str, Any]:
    return {
        "id": r.id,
        "subpilar_anterior": r.subpilar_anterior,
        "tipo_anterior": r.tipo_anterior,
        "subpilar_novo": r.subpilar_novo,
        "tipo_novo": r.tipo_novo,
        "justificativa": r.justificativa,
        "reclassificado_por": r.reclassificado_por,
        "reclassificado_em": r.reclassificado_em.isoformat() if r.reclassificado_em else None,
    }


# ── Endpoint nested em empresas: listagem com filtros ───────────────────


@cliente_pode_ver_empresa("empresa_id")
def listar_verbatins_da_empresa(empresa_id: int):
    """Handler reusado pelo blueprint de empresas. Lista paginada com filtros."""
    # Parse de paginação
    try:
        pagina = int(request.args.get("pagina", "1"))
        por_pagina = int(request.args.get("por_pagina", str(POR_PAGINA_DEFAULT)))
    except ValueError:
        return jsonify({"erro": "pagina/por_pagina devem ser inteiros"}), 400
    pagina = max(1, pagina)
    por_pagina = min(POR_PAGINA_MAX, max(1, por_pagina))

    with db_session() as s:
        q = s.query(Verbatim).filter(Verbatim.empresa_id == empresa_id)
        q, erro = _aplicar_filtros_listagem(q, empresa_id, s)
        if erro is not None:
            return erro

        total = q.count()
        verbatins = (
            q.order_by(Verbatim.data_criacao_original.desc().nullslast(), Verbatim.id.desc())
            .offset((pagina - 1) * por_pagina)
            .limit(por_pagina)
            .all()
        )

        # Resolve maps (nomes) sem N+1
        fonte_ids = {v.fonte_id for v in verbatins}
        local_ids = {v.local_id for v in verbatins if v.local_id}
        fontes_db = s.query(Fonte).filter(Fonte.id.in_(fonte_ids)).all() if fonte_ids else []
        locais_db = s.query(Local).filter(Local.id.in_(local_ids)).all() if local_ids else []
        ag_ids = {loc.agrupamento_id for loc in locais_db if loc.agrupamento_id}
        ags_db = s.query(Agrupamento).filter(Agrupamento.id.in_(ag_ids)).all() if ag_ids else []

        local_map = {loc.id: loc.nome for loc in locais_db}
        local_to_ag = {loc.id: loc.agrupamento_id for loc in locais_db}
        ag_map = {a.id: a.nome for a in ags_db}
        fonte_map = {
            f.id: {
                "conector_tipo": f.conector_tipo,
                "url": f.url,
                "agrupamento_id_via_local": (
                    local_to_ag.get(f.entidade_id) if f.entidade_tipo == "local" else None
                ),
            }
            for f in fontes_db
        }

        payload = [_serialize_verbatim(v, ag_map, local_map, fonte_map) for v in verbatins]

    return jsonify(
        {
            "total": total,
            "pagina": pagina,
            "por_pagina": por_pagina,
            "verbatins": payload,
        }
    )


# ── Exportar Excel ──────────────────────────────────────────────────────


@cliente_pode_ver_empresa("empresa_id")
def exportar_xlsx_da_empresa(empresa_id: int):
    """Exporta verbatins filtrados como XLSX (sem paginação, cap 50k).

    Reusa os mesmos filtros do listar (``_aplicar_filtros_listagem``).
    Se o total bate o cap, devolve 413 pedindo filtros mais restritivos.
    """
    from io import BytesIO

    from flask import send_file
    from openpyxl import Workbook

    with db_session() as s:
        q = s.query(Verbatim).filter(Verbatim.empresa_id == empresa_id)
        q, erro = _aplicar_filtros_listagem(q, empresa_id, s)
        if erro is not None:
            return erro
        total = q.count()
        if total > EXPORTAR_XLSX_MAX_LINHAS:
            return (
                jsonify(
                    {
                        "erro": (
                            f"Exportação excede o limite de {EXPORTAR_XLSX_MAX_LINHAS} linhas "
                            f"(query bate {total}). Aplique filtros mais restritivos."
                        ),
                        "total": total,
                        "limite": EXPORTAR_XLSX_MAX_LINHAS,
                    }
                ),
                413,
            )

        verbatins = q.order_by(
            Verbatim.data_criacao_original.desc().nullslast(), Verbatim.id.desc()
        ).all()

        # Mapeia metadata sem N+1
        fonte_ids = {v.fonte_id for v in verbatins}
        local_ids = {v.local_id for v in verbatins if v.local_id}
        v_ids = [v.id for v in verbatins]
        fontes_db = s.query(Fonte).filter(Fonte.id.in_(fonte_ids)).all() if fonte_ids else []
        locais_db = s.query(Local).filter(Local.id.in_(local_ids)).all() if local_ids else []
        ag_ids = {loc.agrupamento_id for loc in locais_db if loc.agrupamento_id}
        ags_db = s.query(Agrupamento).filter(Agrupamento.id.in_(ag_ids)).all() if ag_ids else []
        reclassif_db = (
            s.query(VerbatimReclassificacao)
            .filter(VerbatimReclassificacao.verbatim_id.in_(v_ids))
            .order_by(VerbatimReclassificacao.reclassificado_em.asc())
            .all()
            if v_ids
            else []
        )

        local_map = {loc.id: loc for loc in locais_db}
        ag_map = {a.id: a.nome for a in ags_db}
        fonte_map = {f.id: f for f in fontes_db}
        reclassif_map: Dict[int, list] = {}
        for r in reclassif_db:
            reclassif_map.setdefault(r.verbatim_id, []).append(r)

        # Monta workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Verbatins"
        headers = [
            "id",
            "data_criacao_original",
            "agrupamento",
            "local",
            "fonte",
            "texto",
            "subpilar",
            "tipo",
            "confianca",
            "justificativa",
            "rating",
            "tem_texto",
            "autor",
            "review_id_externo",
            "historico_reclassificacoes",
        ]
        ws.append(headers)
        for v in verbatins:
            loc = local_map.get(v.local_id) if v.local_id else None
            ag_nome = ag_map.get(loc.agrupamento_id) if loc and loc.agrupamento_id else ""
            local_nome = loc.nome if loc else ""
            f = fonte_map.get(v.fonte_id)
            fonte_str = f"{f.conector_tipo} — {f.url}" if f else ""
            hist = reclassif_map.get(v.id, [])
            hist_str = " | ".join(
                f"{(r.reclassificado_em.isoformat() if r.reclassificado_em else '')}"
                f" {r.subpilar_anterior}→{r.subpilar_novo}"
                f" {r.tipo_anterior}→{r.tipo_novo}"
                f" por_user_id={r.reclassificado_por or ''}"
                f" justif={r.justificativa or ''}"
                for r in hist
            )
            ws.append(
                [
                    v.id,
                    v.data_criacao_original.isoformat() if v.data_criacao_original else "",
                    ag_nome,
                    local_nome,
                    fonte_str,
                    v.texto or "",
                    v.subpilar or "",
                    v.tipo or "",
                    v.confianca if v.confianca is not None else "",
                    v.justificativa or "",
                    v.rating if v.rating is not None else "",
                    "sim" if v.tem_texto else "não",
                    v.autor or "",
                    v.review_id_externo or "",
                    hist_str,
                ]
            )

        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)

    fname = f"verbatins_empresa_{empresa_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        buf,
        as_attachment=True,
        download_name=fname,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ── Endpoints standalone /api/verbatins/<id>* ───────────────────────────


@verbatins_bp.route("/<int:verbatim_id>/temas", methods=["GET"])
def _temas_de_verbatim_endpoint(verbatim_id: int):
    from src.api.temas import temas_de_verbatim as h

    return h(verbatim_id)


@verbatins_bp.route("/<int:verbatim_id>", methods=["GET"])
@login_required
def obter_verbatim(verbatim_id: int):
    """Detalhe do verbatim + histórico completo de reclassificações."""
    with db_session() as s:
        v = s.get(Verbatim, verbatim_id)
        if v is None:
            return jsonify({"erro": "Verbatim não encontrado"}), 404
        erro = verificar_acesso_empresa(v.empresa_id)
        if erro:
            return erro

        # Resolve nomes
        fonte = s.get(Fonte, v.fonte_id)
        local = s.get(Local, v.local_id) if v.local_id else None
        ag = s.get(Agrupamento, local.agrupamento_id) if local and local.agrupamento_id else None
        fonte_map = {
            v.fonte_id: {
                "conector_tipo": fonte.conector_tipo if fonte else None,
                "url": fonte.url if fonte else None,
                "agrupamento_id_via_local": local.agrupamento_id if local else None,
            }
        }
        local_map = {local.id: local.nome} if local else {}
        ag_map = {ag.id: ag.nome} if ag else {}

        # Histórico
        historico = (
            s.query(VerbatimReclassificacao)
            .filter_by(verbatim_id=verbatim_id)
            .order_by(VerbatimReclassificacao.reclassificado_em.desc())
            .all()
        )
        hist_payload = [_serialize_reclassificacao(r) for r in historico]
        body = _serialize_verbatim(v, ag_map, local_map, fonte_map)
        body["historico"] = hist_payload

    return jsonify(body)


@verbatins_bp.route("/<int:verbatim_id>/reclassificar", methods=["PATCH"])
@login_required
def reclassificar_verbatim(verbatim_id: int):
    """Reclassifica manualmente um verbatim (qualquer user com acesso à empresa)."""
    data = request.get_json(silent=True) or {}
    sub_novo = (data.get("subpilar") or "").strip()
    tipo_novo = (data.get("tipo") or "").strip()
    justif = (data.get("justificativa") or "").strip() or None

    if sub_novo not in SUBPILARES_VALIDOS:
        return (
            jsonify(
                {
                    "erro": f"subpilar inválido. Aceitos: {sorted(SUBPILARES_VALIDOS)}",
                }
            ),
            400,
        )
    if tipo_novo not in TIPOS_VALIDOS:
        return (
            jsonify(
                {
                    "erro": f"tipo inválido. Aceitos: {sorted(TIPOS_VALIDOS)}",
                }
            ),
            400,
        )
    if (sub_novo == "sem_lastro") != (tipo_novo == "inativo"):
        return (
            jsonify({"erro": ("Restrição rígida: 'sem_lastro' exige 'inativo' " "e vice-versa.")}),
            400,
        )

    user = get_current_user()

    with db_session() as s:
        v = s.get(Verbatim, verbatim_id)
        if v is None:
            return jsonify({"erro": "Verbatim não encontrado"}), 404
        erro = verificar_acesso_empresa(v.empresa_id)
        if erro:
            return erro

        # Insere histórico
        recl = VerbatimReclassificacao(
            verbatim_id=v.id,
            subpilar_anterior=v.subpilar,
            tipo_anterior=v.tipo,
            subpilar_novo=sub_novo,
            tipo_novo=tipo_novo,
            justificativa=justif,
            reclassificado_por=user.id if user else None,
        )
        s.add(recl)

        # Atualiza snapshot no verbatim
        v.subpilar_anterior = v.subpilar
        v.tipo_anterior = v.tipo
        v.subpilar = sub_novo
        v.tipo = tipo_novo
        v.reclassificado_em = datetime.utcnow()
        v.reclassificado_por = user.id if user else None
        s.flush()

        return jsonify(
            {
                "id": v.id,
                "subpilar": v.subpilar,
                "tipo": v.tipo,
                "subpilar_anterior": v.subpilar_anterior,
                "tipo_anterior": v.tipo_anterior,
                "reclassificado_em": v.reclassificado_em.isoformat(),
                "reclassificado_por": v.reclassificado_por,
            }
        )


@verbatins_bp.route("/<int:verbatim_id>", methods=["DELETE"])
@login_required
def remover_verbatim(verbatim_id: int):
    with db_session() as s:
        v = s.get(Verbatim, verbatim_id)
        if v is None:
            return jsonify({"erro": "Verbatim não encontrado"}), 404
        erro = verificar_acesso_empresa(v.empresa_id)
        if erro:
            return erro
        s.delete(v)
    return jsonify({"removido": True, "id": verbatim_id})
