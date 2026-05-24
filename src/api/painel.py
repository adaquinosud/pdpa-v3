"""Painel Executivo (Bloco 5) — endpoints de agregação por pilar/subpilar.

Dois endpoints expostos via blueprint, registrados sob ``/api/empresas``:

- ``GET /api/empresas/<id>/painel/nivel1`` — totais por pilar (P, D, Pa, A).
- ``GET /api/empresas/<id>/painel/nivel2`` — matriz subpilar × tipo (12×3).

Decisão arquitetural CP1: **runtime, sem materialização**. SQLite resolve
``GROUP BY subpilar, tipo`` em ms para volumes < 500k verbatins. Quando o
volume justificar, materializamos via job + tabela ``painel_snapshot``
(pendência registrada em PENDENCIAS_TECNICAS.md).

Filtros aceitos via query string:

- ``agrupamento_id`` (int) — restringe a verbatins de locais do agrupamento
- ``local_id`` (int) — restringe a um local específico
- ``fonte_id`` (int) — restringe a uma fonte específica
- ``data_de`` / ``data_ate`` (YYYY-MM-DD) — janela em ``data_criacao_original``
- ``periodo`` (str) — atalho exclusivo com ``data_de``/``data_ate``:
  ``"7d"``, ``"30d"``, ``"90d"``, ``"12m"``. Calcula ``data_de=hoje−N`` e
  ``data_ate=hoje``.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from src.auth import cliente_pode_ver_empresa
from src.models.local import Local
from src.models.verbatim import Verbatim
from src.utils.db import db_session


painel_bp = Blueprint("painel", __name__)


# ── Mapeamento subpilar → pilar ────────────────────────────────────────

PILAR_DE_SUBPILAR: Dict[str, str] = {
    "P1": "P",
    "P2": "P",
    "P3": "P",
    "D1": "D",
    "D2": "D",
    "D3": "D",
    "Pa1": "Pa",
    "Pa2": "Pa",
    "Pa3": "Pa",
    "A1": "A",
    "A2": "A",
    "A3": "A",
    # sem_lastro fica de fora dos 4 pilares (vai pra "outros")
}

PILARES_ORDEM = ["P", "D", "Pa", "A"]
NOME_PILAR = {
    "P": "Produto",
    "D": "Deslumbramento",
    "Pa": "Atendimento",
    "A": "Acesso",
}
SUBPILARES_ORDEM = [
    "P1",
    "P2",
    "P3",
    "D1",
    "D2",
    "D3",
    "Pa1",
    "Pa2",
    "Pa3",
    "A1",
    "A2",
    "A3",
]
TIPOS_ORDEM = ["promotor", "conversivel", "detrator", "inativo"]


# ── Filtros (subset dos da listagem de verbatins) ─────────────────────


def _resolver_periodo(periodo: str) -> Optional[datetime]:
    """``7d``/``30d``/``90d``/``12m`` → datetime de início. Inválido → None."""
    if not periodo:
        return None
    hoje = datetime.utcnow()
    mapa = {
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "12m": timedelta(days=365),
    }
    delta = mapa.get(periodo)
    if delta is None:
        return None
    return hoje - delta


def _aplicar_filtros(q, empresa_id: int, s):
    """Aplica os filtros do painel na query base.

    Devolve ``(q, erro_response)``. ``erro_response`` é tupla (json, status)
    se houve erro de parsing — caller retorna direto.
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
            q = q.filter(Verbatim.id.is_(None))  # zera o resultado

    local_id_raw = request.args.get("local_id")
    if local_id_raw:
        try:
            q = q.filter(Verbatim.local_id == int(local_id_raw))
        except ValueError:
            return q, (jsonify({"erro": "local_id deve ser inteiro"}), 400)

    fonte_id_raw = request.args.get("fonte_id")
    if fonte_id_raw:
        try:
            q = q.filter(Verbatim.fonte_id == int(fonte_id_raw))
        except ValueError:
            return q, (jsonify({"erro": "fonte_id deve ser inteiro"}), 400)

    periodo = request.args.get("periodo")
    data_de_raw = request.args.get("data_de")
    data_ate_raw = request.args.get("data_ate")
    if periodo:
        d = _resolver_periodo(periodo)
        if d is None:
            return q, (
                jsonify({"erro": "periodo inválido. Use: 7d, 30d, 90d, 12m"}),
                400,
            )
        q = q.filter(Verbatim.data_criacao_original >= d)
    if data_de_raw:
        try:
            d = datetime.fromisoformat(data_de_raw)
            q = q.filter(Verbatim.data_criacao_original >= d)
        except ValueError:
            return q, (jsonify({"erro": "data_de deve ser YYYY-MM-DD"}), 400)
    if data_ate_raw:
        try:
            d = datetime.fromisoformat(data_ate_raw)
            q = q.filter(Verbatim.data_criacao_original <= d)
        except ValueError:
            return q, (jsonify({"erro": "data_ate deve ser YYYY-MM-DD"}), 400)

    return q, None


def _filtros_efetivos() -> Dict[str, Any]:
    """Retorna dict serializável dos filtros usados (eco para o front)."""
    return {
        k: request.args.get(k)
        for k in ("agrupamento_id", "local_id", "fonte_id", "data_de", "data_ate", "periodo")
        if request.args.get(k)
    }


# ── Endpoint Nível 1: 4 pilares ────────────────────────────────────────


@cliente_pode_ver_empresa("empresa_id")
def painel_nivel1(empresa_id: int):
    """Totais por pilar (P, D, Pa, A), com breakdown por tipo."""
    with db_session() as s:
        q = s.query(
            Verbatim.subpilar,
            Verbatim.tipo,
            func.count(Verbatim.id),
        ).filter(Verbatim.empresa_id == empresa_id)
        q, erro = _aplicar_filtros(q, empresa_id, s)
        if erro is not None:
            return erro
        q = q.group_by(Verbatim.subpilar, Verbatim.tipo)
        rows = q.all()

    # Agrega por pilar
    pilares_agg: Dict[str, Dict[str, int]] = {
        p: {"total": 0, "promotor": 0, "conversivel": 0, "detrator": 0, "inativo": 0}
        for p in PILARES_ORDEM
    }
    outros = {"sem_lastro": 0, "sem_classificacao": 0}
    total_geral = 0

    for subpilar, tipo, qtd in rows:
        total_geral += qtd
        if subpilar in PILAR_DE_SUBPILAR:
            pilar = PILAR_DE_SUBPILAR[subpilar]
            pilares_agg[pilar]["total"] += qtd
            if tipo in pilares_agg[pilar]:
                pilares_agg[pilar][tipo] += qtd
        elif subpilar == "sem_lastro":
            outros["sem_lastro"] += qtd
        else:
            outros["sem_classificacao"] += qtd

    pilares: List[Dict[str, Any]] = []
    for p in PILARES_ORDEM:
        agg = pilares_agg[p]
        pilares.append(
            {
                "pilar": p,
                "nome": NOME_PILAR[p],
                "total": agg["total"],
                "promotor": agg["promotor"],
                "conversivel": agg["conversivel"],
                "detrator": agg["detrator"],
                "inativo": agg["inativo"],
            }
        )

    return jsonify(
        {
            "empresa_id": empresa_id,
            "filtros": _filtros_efetivos(),
            "total_verbatins": total_geral,
            "pilares": pilares,
            "outros": outros,
        }
    )


# ── Endpoint Nível 2: matriz subpilar × tipo ──────────────────────────


@cliente_pode_ver_empresa("empresa_id")
def painel_nivel2(empresa_id: int):
    """Matriz 12 subpilares × 3 tipos (promotor/conversivel/detrator).

    ``inativo`` aparece como coluna informativa porque ``sem_lastro`` vai
    junto, mas a matriz principal são os 12 subpilares P/D/Pa/A.
    """
    with db_session() as s:
        q = s.query(
            Verbatim.subpilar,
            Verbatim.tipo,
            func.count(Verbatim.id),
        ).filter(Verbatim.empresa_id == empresa_id)
        q, erro = _aplicar_filtros(q, empresa_id, s)
        if erro is not None:
            return erro
        q = q.group_by(Verbatim.subpilar, Verbatim.tipo)
        rows = q.all()

    matriz_agg: Dict[str, Dict[str, int]] = {
        sp: {"promotor": 0, "conversivel": 0, "detrator": 0, "inativo": 0, "total": 0}
        for sp in SUBPILARES_ORDEM
    }
    sem_lastro_agg = {"promotor": 0, "conversivel": 0, "detrator": 0, "inativo": 0, "total": 0}
    sem_classif_agg = {"promotor": 0, "conversivel": 0, "detrator": 0, "inativo": 0, "total": 0}
    total_geral = 0

    for subpilar, tipo, qtd in rows:
        total_geral += qtd
        if subpilar in matriz_agg:
            matriz_agg[subpilar]["total"] += qtd
            if tipo in matriz_agg[subpilar]:
                matriz_agg[subpilar][tipo] += qtd
        elif subpilar == "sem_lastro":
            sem_lastro_agg["total"] += qtd
            if tipo in sem_lastro_agg:
                sem_lastro_agg[tipo] += qtd
        else:
            sem_classif_agg["total"] += qtd
            if tipo in sem_classif_agg:
                sem_classif_agg[tipo] += qtd

    matriz: List[Dict[str, Any]] = []
    for sp in SUBPILARES_ORDEM:
        cell = matriz_agg[sp]
        matriz.append(
            {
                "subpilar": sp,
                "pilar": PILAR_DE_SUBPILAR[sp],
                "promotor": cell["promotor"],
                "conversivel": cell["conversivel"],
                "detrator": cell["detrator"],
                "inativo": cell["inativo"],
                "total": cell["total"],
            }
        )

    return jsonify(
        {
            "empresa_id": empresa_id,
            "filtros": _filtros_efetivos(),
            "total_verbatins": total_geral,
            "matriz": matriz,
            "sem_lastro": sem_lastro_agg,
            "sem_classificacao": sem_classif_agg,
        }
    )
