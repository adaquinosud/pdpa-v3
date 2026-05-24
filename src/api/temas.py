"""Endpoints REST de temas (Bloco 6 CP-3).

Endpoints expostos via empresas_bp / verbatins_bp / temas_bp:

- GET    /api/empresas/<id>/temas              (catálogo)
- POST   /api/empresas/<id>/temas              (cria manual — loyall_required)
- POST   /api/temas/<id>/merge                 (consolida sinônimos — loyall_required)
- GET    /api/verbatins/<id>/temas             (temas de um verbatim)
- GET    /api/empresas/<id>/painel/temas       (drill-down por subpilar×tipo)
- POST   /api/empresas/<id>/temas/reprocessar  (extração inline, batch pequeno)
"""

from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from src.auth import (
    cliente_pode_ver_empresa,
    get_current_user,
    login_required,
    loyall_required,
    verificar_acesso_empresa,
)
from src.models.temas import Tema, VerbatimTema
from src.models.verbatim import Verbatim
from src.temas.extrator import extrair_temas
from src.temas.persistencia import merge_temas, persistir_temas_de_verbatim
from src.temas.slug import slugify
from src.utils.db import db_session


temas_bp = Blueprint("temas", __name__, url_prefix="/api/temas")


@temas_bp.route("/<int:tema_id>/merge", methods=["POST"])
def _merge_tema_endpoint(tema_id: int):
    return merge_tema(tema_id)


# Limite síncrono: além disso, devolve 413 pedindo CLI (CP-4).
REPROCESSAR_INLINE_MAX = 100

# Custo estimado por verbatim com texto (Haiku 4.5 + prompt caching).
CUSTO_USD_POR_VERBATIM = 0.0005


# ── GET catálogo ──────────────────────────────────────────────────────


@cliente_pode_ver_empresa("empresa_id")
def listar_temas_da_empresa(empresa_id: int):
    incluir_inativos = request.args.get("incluir_inativos") in ("1", "true", "True")
    busca = (request.args.get("q") or "").strip().lower()

    with db_session() as s:
        q = (
            s.query(Tema, func.count(VerbatimTema.id).label("volume"))
            .outerjoin(VerbatimTema, VerbatimTema.tema_id == Tema.id)
            .filter(Tema.empresa_id == empresa_id)
        )
        if not incluir_inativos:
            q = q.filter(Tema.ativo.is_(True))
        if busca:
            like = f"%{busca}%"
            q = q.filter((Tema.nome.ilike(like)) | (Tema.slug.ilike(like)))
        q = q.group_by(Tema.id).order_by(func.count(VerbatimTema.id).desc(), Tema.nome.asc())
        payload = [
            {
                "id": t.id,
                "nome": t.nome,
                "slug": t.slug,
                "descricao": t.descricao,
                "ativo": t.ativo,
                "volume": int(vol or 0),
                "criado_em": t.criado_em.isoformat() if t.criado_em else None,
                "criado_por": t.criado_por,
            }
            for (t, vol) in q.all()
        ]
    return jsonify({"empresa_id": empresa_id, "temas": payload})


# ── POST criar manual ────────────────────────────────────────────────


@loyall_required
def criar_tema_manual(empresa_id: int):
    body = request.get_json(silent=True) or {}
    nome = (body.get("nome") or "").strip()
    if not nome:
        return jsonify({"erro": "nome obrigatório"}), 400
    slug = slugify(nome)
    if not slug:
        return jsonify({"erro": "nome gera slug vazio"}), 400

    user = get_current_user()
    with db_session() as s:
        ja = s.query(Tema).filter_by(empresa_id=empresa_id, slug=slug).first()
        if ja is not None:
            return (
                jsonify(
                    {
                        "erro": f"tema com slug {slug!r} já existe",
                        "tema_existente_id": ja.id,
                    }
                ),
                409,
            )
        t = Tema(
            empresa_id=empresa_id,
            nome=nome,
            slug=slug,
            descricao=(body.get("descricao") or "").strip() or None,
            criado_por=user.id if user else None,
        )
        s.add(t)
        s.flush()
        payload = {
            "id": t.id,
            "nome": t.nome,
            "slug": t.slug,
            "descricao": t.descricao,
            "ativo": True,
        }
    return jsonify(payload), 201


# ── POST merge ────────────────────────────────────────────────────────


@loyall_required
def merge_tema(tema_id: int):
    body = request.get_json(silent=True) or {}
    destino_raw = body.get("tema_destino_id")
    if destino_raw is None:
        return jsonify({"erro": "tema_destino_id obrigatório"}), 400
    try:
        destino_id = int(destino_raw)
    except (TypeError, ValueError):
        return jsonify({"erro": "tema_destino_id deve ser inteiro"}), 400

    motivo = (body.get("motivo") or "").strip() or None
    user = get_current_user()

    with db_session() as s:
        try:
            res = merge_temas(
                s,
                tema_origem_id=tema_id,
                tema_destino_id=destino_id,
                motivo=motivo,
                executado_por=user.id if user else None,
            )
        except ValueError as exc:
            return jsonify({"erro": str(exc)}), 400
        return jsonify(res), 200


# ── GET temas de um verbatim ─────────────────────────────────────────


@login_required
def temas_de_verbatim(verbatim_id: int):
    with db_session() as s:
        v = s.get(Verbatim, verbatim_id)
        if v is None:
            return jsonify({"erro": "Verbatim não encontrado"}), 404
        erro = verificar_acesso_empresa(v.empresa_id)
        if erro:
            return erro
        rows = (
            s.query(VerbatimTema, Tema)
            .join(Tema, Tema.id == VerbatimTema.tema_id)
            .filter(VerbatimTema.verbatim_id == verbatim_id)
            .order_by(VerbatimTema.confianca.desc())
            .all()
        )
        temas = [
            {
                "tema_id": t.id,
                "nome": t.nome,
                "slug": t.slug,
                "ativo": t.ativo,
                "confianca": vt.confianca,
                "origem": vt.origem,
                "evidencia_curta": vt.evidencia_curta,
            }
            for (vt, t) in rows
        ]
    return jsonify({"verbatim_id": verbatim_id, "temas": temas})


# ── GET painel temas (drill-down por subpilar × tipo) ───────────────


@cliente_pode_ver_empresa("empresa_id")
def painel_temas(empresa_id: int):
    """Top N temas para o bucket subpilar × tipo, com 3 verbatins exemplo."""
    subpilar = (request.args.get("subpilar") or "").strip()
    tipo = (request.args.get("tipo") or "").strip()
    if not subpilar or not tipo:
        return jsonify({"erro": "subpilar e tipo são obrigatórios"}), 400
    try:
        limite = max(1, min(50, int(request.args.get("limite", "10"))))
    except ValueError:
        return jsonify({"erro": "limite deve ser inteiro"}), 400

    with db_session() as s:
        q = (
            s.query(
                Tema.id,
                Tema.nome,
                Tema.slug,
                func.count(VerbatimTema.id).label("volume"),
            )
            .join(VerbatimTema, VerbatimTema.tema_id == Tema.id)
            .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
            .filter(
                Verbatim.empresa_id == empresa_id,
                Verbatim.subpilar == subpilar,
                Verbatim.tipo == tipo,
                Tema.ativo.is_(True),
            )
            .group_by(Tema.id)
            .order_by(func.count(VerbatimTema.id).desc())
            .limit(limite)
        )
        temas: List[Dict[str, Any]] = []
        for tema_id, nome, slug, volume in q.all():
            exemplos_rows = (
                s.query(Verbatim.id, Verbatim.texto, VerbatimTema.evidencia_curta)
                .join(VerbatimTema, VerbatimTema.verbatim_id == Verbatim.id)
                .filter(
                    VerbatimTema.tema_id == tema_id,
                    Verbatim.subpilar == subpilar,
                    Verbatim.tipo == tipo,
                )
                .order_by(Verbatim.data_criacao_original.desc().nullslast())
                .limit(3)
                .all()
            )
            temas.append(
                {
                    "tema_id": tema_id,
                    "nome": nome,
                    "slug": slug,
                    "volume": int(volume or 0),
                    "exemplos": [
                        {
                            "verbatim_id": vid,
                            "texto_curto": (texto or "")[:160],
                            "evidencia": evidencia or None,
                        }
                        for (vid, texto, evidencia) in exemplos_rows
                    ],
                }
            )

    return jsonify(
        {
            "empresa_id": empresa_id,
            "subpilar": subpilar,
            "tipo": tipo,
            "temas": temas,
        }
    )


# ── POST reprocessar inline ──────────────────────────────────────────


@loyall_required
def reprocessar_temas_empresa(empresa_id: int):
    body = request.get_json(silent=True) or {}
    apenas_novos = body.get("apenas_novos") in (True, "1", 1, "true", "True")
    subpilar = body.get("subpilar")
    tipo_arg = body.get("tipo")
    try:
        limite_arg = int(body.get("limite", REPROCESSAR_INLINE_MAX))
    except (TypeError, ValueError):
        return jsonify({"erro": "limite deve ser inteiro"}), 400
    limite = max(1, min(REPROCESSAR_INLINE_MAX, limite_arg))

    with db_session() as s:
        q = s.query(Verbatim).filter(
            Verbatim.empresa_id == empresa_id, Verbatim.tem_texto.is_(True)
        )
        if subpilar:
            q = q.filter(Verbatim.subpilar == subpilar)
        if tipo_arg:
            q = q.filter(Verbatim.tipo == tipo_arg)
        if apenas_novos:
            sub_ids = s.query(VerbatimTema.verbatim_id).distinct()
            q = q.filter(~Verbatim.id.in_(sub_ids))
        total_elegivel = q.count()

        if total_elegivel > REPROCESSAR_INLINE_MAX:
            return (
                jsonify(
                    {
                        "erro": (
                            f"{total_elegivel} verbatins elegíveis excede o cap "
                            f"inline de {REPROCESSAR_INLINE_MAX}. Use o CLI: "
                            f"`flask temas-extrair --empresa={empresa_id}`."
                        ),
                        "total_elegivel": total_elegivel,
                        "limite_inline": REPROCESSAR_INLINE_MAX,
                    }
                ),
                413,
            )

        verbatins = q.order_by(Verbatim.id.asc()).limit(limite).all()
        verbatins_dados = [
            {
                "id": v.id,
                "texto": v.texto,
                "subpilar": v.subpilar,
                "tipo": v.tipo,
            }
            for v in verbatins
        ]
        empresa_setor = verbatins[0].empresa.setor if (verbatins and verbatins[0].empresa) else None

        catalogo = (
            s.query(Tema.nome, Tema.slug)
            .filter(Tema.empresa_id == empresa_id, Tema.ativo.is_(True))
            .order_by(Tema.criado_em.desc())
            .limit(80)
            .all()
        )
        catalogo_lista = [{"nome": n, "slug": sl} for (n, sl) in catalogo]

    # Extração e persistência fora da sessão original (LLM call demora).
    novos_vinculos = 0
    erros = 0
    for vdata in verbatins_dados:
        try:
            temas_extraidos = extrair_temas(
                vdata["texto"],
                {
                    "subpilar": vdata.get("subpilar"),
                    "tipo": vdata.get("tipo"),
                    "setor": empresa_setor,
                },
                catalogo_recente=catalogo_lista,
            )
            if not temas_extraidos:
                continue
            with db_session() as s2:
                ids = persistir_temas_de_verbatim(
                    s2, vdata["id"], empresa_id, temas_extraidos, origem="llm"
                )
                novos_vinculos += len(ids)
        except Exception as exc:  # noqa: BLE001
            print(f"[temas/reprocessar] erro verbatim {vdata['id']}: {exc}")
            erros += 1

    custo_estimado = round(len(verbatins_dados) * CUSTO_USD_POR_VERBATIM, 4)
    return jsonify(
        {
            "verbatins_processados": len(verbatins_dados),
            "novos_vinculos": novos_vinculos,
            "erros": erros,
            "custo_estimado_usd": custo_estimado,
        }
    )
