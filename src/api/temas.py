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

import json
from typing import Any, Dict, List, Set

from flask import Blueprint, jsonify, request
from sqlalchemy import and_, func

from src.utils.sql import group_concat
from src.auth import (
    cliente_pode_ver_empresa,
    get_current_user,
    login_required,
    loyall_required,
    verificar_acesso_empresa,
)
from src.models.local import Local
from src.models.temas import Tema, TemaCache, TemaCruzamento, VerbatimTema
from src.models.verbatim import Verbatim
from src.temas.cobertura import tripleto_bucket
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
        # Régua live: verbatins DISTINTOS por tema (= count(VerbatimTema.id) via
        # UNIQUE(verbatim_id, tema_id), mas explícito p/ não duplicar ao agregar).
        _vol = func.count(func.distinct(VerbatimTema.verbatim_id))
        q = (
            s.query(Tema, _vol.label("volume"))
            .outerjoin(VerbatimTema, VerbatimTema.tema_id == Tema.id)
            .filter(Tema.empresa_id == empresa_id)
        )
        if not incluir_inativos:
            q = q.filter(Tema.ativo.is_(True))
        if busca:
            like = f"%{busca}%"
            q = q.filter((Tema.nome.ilike(like)) | (Tema.slug.ilike(like)))
        q = q.group_by(Tema.id).order_by(_vol.desc(), Tema.nome.asc())
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
    """Top N temas do bucket subpilar × tipo, lendo de ``temas_cache`` (CP-13).

    Lê o cache pré-computado pelo pipeline (1 SELECT, agregando o volume por
    label across agrupamentos) em vez de joins on-the-fly verbatim_temas →
    temas. Os textos dos exemplos vêm de 1 SELECT batched pelos ids guardados
    no cache. INNER JOIN em ``temas`` (ativo) descarta temas inativos e labels
    de cache órfãos (sem tema correspondente).
    """
    subpilar = (request.args.get("subpilar") or "").strip()
    tipo = (request.args.get("tipo") or "").strip()
    if not subpilar:
        return jsonify({"erro": "subpilar é obrigatório"}), 400
    try:
        limite = max(1, min(50, int(request.args.get("limite", "10"))))
    except ValueError:
        return jsonify({"erro": "limite deve ser inteiro"}), 400
    # Filtro de agrupamento (o cache é indexado por agrupamento_id). Vazio =
    # consolidado da empresa (agrega across agrupamentos).
    agrupamento_raw = (request.args.get("agrupamento_id") or "").strip()
    agrupamento_id = None
    if agrupamento_raw:
        try:
            agrupamento_id = int(agrupamento_raw)
        except ValueError:
            return jsonify({"erro": "agrupamento_id deve ser inteiro"}), 400

    with db_session() as s:
        # Régua LIVE: conta verbatins DISTINTOS do bucket (com texto) vinculados a
        # cada tema ATIVO — exatamente o que a lista "ver verbatins deste tema"
        # mostra. Substitui temas_cache.volume como número PRIMÁRIO (era snapshot e
        # divergia da lista sempre que houve reprocessamento). O split por tipo sai
        # do Verbatim.tipo vivo.
        ql = (
            s.query(
                Tema.id.label("tema_id"),
                Tema.nome.label("nome"),
                Tema.slug.label("slug"),
                Verbatim.tipo.label("tipo"),
                func.count(func.distinct(Verbatim.id)).label("n"),
            )
            .select_from(VerbatimTema)
            .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
            .join(Tema, and_(Tema.id == VerbatimTema.tema_id, Tema.ativo.is_(True)))
            .filter(
                Verbatim.empresa_id == empresa_id,
                Verbatim.tem_texto.is_(True),
                Verbatim.subpilar == subpilar,
            )
        )
        if tipo:
            ql = ql.filter(Verbatim.tipo == tipo)
        if agrupamento_id is not None:
            ql = ql.join(Local, Local.id == Verbatim.local_id).filter(
                Local.agrupamento_id == agrupamento_id
            )
        rows = ql.group_by(Tema.id, Tema.nome, Tema.slug, Verbatim.tipo).all()

        por_tema: Dict[int, Dict[str, Any]] = {}
        for r in rows:
            e = por_tema.get(r.tema_id)
            if e is None:
                e = {
                    "tema_id": r.tema_id,
                    "nome": r.nome,
                    "slug": r.slug,
                    "volume": 0,
                    "promotor": 0,
                    "conversivel": 0,
                    "detrator": 0,
                }
                por_tema[r.tema_id] = e
            n = int(r.n or 0)
            e["volume"] += n
            if r.tipo in ("promotor", "conversivel", "detrator"):
                e[r.tipo] += n

        parciais = sorted(por_tema.values(), key=lambda x: -x["volume"])[:limite]

        # Snapshot do cache (número antigo) + exemplos, por tema. Exibido só como
        # referência; a diferença vs o volume live vira o badge de "defasado".
        snap_q = (
            s.query(
                Tema.id.label("tema_id"),
                func.sum(TemaCache.volume).label("snap"),
                group_concat(TemaCache.exemplos_verbatim_ids, "|").label("ex_blobs"),
            )
            .join(
                Tema,
                and_(
                    Tema.empresa_id == TemaCache.empresa_id,
                    Tema.nome == TemaCache.tema_label,
                    Tema.ativo.is_(True),
                ),
            )
            .filter(TemaCache.empresa_id == empresa_id, TemaCache.subpilar == subpilar)
        )
        if tipo:
            snap_q = snap_q.filter(TemaCache.tipo == tipo)
        if agrupamento_id is not None:
            snap_q = snap_q.filter(TemaCache.agrupamento_id == agrupamento_id)
        snap_map: Dict[int, Dict[str, Any]] = {
            sr.tema_id: {"snap": int(sr.snap or 0), "ex_blobs": sr.ex_blobs or ""}
            for sr in snap_q.group_by(Tema.id).all()
        }

        todos_ids: Set[int] = set()
        ex_por_tema: Dict[int, List[int]] = {}
        for p in parciais:
            ids: List[int] = []
            for blob in snap_map.get(p["tema_id"], {}).get("ex_blobs", "").split("|"):
                blob = blob.strip()
                if not blob:
                    continue
                try:
                    for vid in json.loads(blob):
                        if vid not in ids:
                            ids.append(vid)
                except (ValueError, TypeError):
                    continue
            ex_por_tema[p["tema_id"]] = ids[:3]
            todos_ids.update(ids[:3])

        textos: Dict[int, str] = {}
        if todos_ids:
            for vid, texto in (
                s.query(Verbatim.id, Verbatim.texto).filter(Verbatim.id.in_(todos_ids)).all()
            ):
                textos[vid] = texto or ""

    temas: List[Dict[str, Any]] = []
    for p in parciais:
        snap = snap_map.get(p["tema_id"], {}).get("snap", 0)
        temas.append(
            {
                "tema_id": p["tema_id"],
                "nome": p["nome"],
                "slug": p["slug"],
                "volume": p["volume"],  # LIVE (= lista de verbatins)
                "volume_snapshot": snap,  # cache (referência)
                "stale": snap != p["volume"],
                "promotor": p["promotor"],
                "conversivel": p["conversivel"],
                "detrator": p["detrator"],
                "exemplos": [
                    {
                        "verbatim_id": vid,
                        "texto_curto": textos.get(vid, "")[:160],
                        "evidencia": None,
                    }
                    for vid in ex_por_tema.get(p["tema_id"], [])
                ],
            }
        )

    tripleto = tripleto_bucket(empresa_id, subpilar, tipo or None, agrupamento_id)

    return jsonify(
        {
            "empresa_id": empresa_id,
            "subpilar": subpilar,
            "tipo": tipo or None,
            "agrupamento_id": agrupamento_id,
            "tripleto": tripleto,
            "temas": temas,
        }
    )


# ── GET cruzamentos (Nível 4) ────────────────────────────────────────


@cliente_pode_ver_empresa("empresa_id")
def painel_cruzamentos(empresa_id: int):
    """Cruzamentos N4 da empresa, ordenados por peso (sistemicidade desc).

    Lê de ``temas_cruzamentos`` (pré-computado por ``flask temas-cruzar``).
    ``?min_subpilares=N`` filtra por sistemicidade (cross-pilar).
    """
    try:
        limite = max(1, min(100, int(request.args.get("limite", "50"))))
    except ValueError:
        return jsonify({"erro": "limite deve ser inteiro"}), 400
    try:
        min_subpilares = int(request.args.get("min_subpilares", "1"))
    except ValueError:
        return jsonify({"erro": "min_subpilares deve ser inteiro"}), 400

    with db_session() as s:
        q = s.query(TemaCruzamento).filter(TemaCruzamento.empresa_id == empresa_id)
        if min_subpilares > 1:
            q = q.filter(TemaCruzamento.n_subpilares_distintos >= min_subpilares)
        rows = q.order_by(TemaCruzamento.peso.desc()).limit(limite).all()
        cruzamentos = [
            {
                "id": r.id,
                "tema_label": r.tema_label,
                "buckets_envolvidos": json.loads(r.buckets_envolvidos_json or "[]"),
                "tipos_envolvidos": json.loads(r.tipos_envolvidos_json or "[]"),
                "membros": json.loads(r.membros_json) if r.membros_json else None,
                "n_subpilares_distintos": r.n_subpilares_distintos,
                "peso": r.peso,
                "periodo_inicio": r.periodo_inicio.isoformat() if r.periodo_inicio else None,
                "periodo_fim": r.periodo_fim.isoformat() if r.periodo_fim else None,
            }
            for r in rows
        ]
    return jsonify({"empresa_id": empresa_id, "cruzamentos": cruzamentos})


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
