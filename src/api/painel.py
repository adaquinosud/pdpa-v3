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
- ``periodo`` (str) — ``"7d"``, ``"30d"``, ``"90d"``, ``"6m"``, ``"12m"``
  ou ``"15m"`` (Manual Cap. 4). Calcula ``data_inicio = hoje−N`` e filtra
  ``Verbatim.data_criacao_original >= data_inicio``. Vazio = tudo.
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
# Nomenclatura oficial PDPA Loyall. Fonte canônica:
# data/PDPA_Manual_Operacao_v3.docx, Capítulo 2.
NOME_PILAR = {
    "P": "Precisão",
    "D": "Disponibilidade",
    "Pa": "Parceria",
    "A": "Aconselhamento",
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
# Manual PDPA v3, Capítulo 2 — nomes oficiais.
NOME_SUBPILAR = {
    "P1": "Calibração da Promessa",
    "P2": "Qualidade da Entrega",
    "P3": "Consistência ao Longo do Tempo",
    "D1": "Acessibilidade",
    "D2": "Eficácia Operacional",
    "D3": "Proatividade Estruturada",
    "Pa1": "Empatia Comercial",
    "Pa2": "Mutualidade",
    "Pa3": "Comprometimento Relacional",
    "A1": "Exemplo",
    "A2": "Orientação",
    "A3": "Recomendação Proativa",
}
TIPOS_ORDEM = ["promotor", "conversivel", "detrator", "inativo"]


# ── Ratio P/D (Manual Cap. 4) ─────────────────────────────────────────

RATIO_CAP_SUPERIOR = 9.99
RATIO_CAP_INFERIOR = 0.0


def calcular_ratio(promotor: int, detrator: int) -> float:
    """Ratio P/D conforme Manual Cap. 4.

    - Zero detratores → cap 9.99 (saturação positiva máxima).
    - Zero promotores → 0.0 (sinal crítico).
    - Caso normal: promotor / detrator, com cap em 9.99.
    """
    if promotor == 0 and detrator == 0:
        return 0.0
    if detrator == 0:
        return RATIO_CAP_SUPERIOR
    if promotor == 0:
        return RATIO_CAP_INFERIOR
    return min(RATIO_CAP_SUPERIOR, round(promotor / detrator, 2))


def faixa_ratio(ratio: float) -> str:
    """Devolve a faixa semântica do ratio (5 níveis, cores do painel).

    - 0.0–0.5  : critico       (vermelho)
    - 0.5–1.0  : fraco         (laranja)
    - 1.0–2.0  : atencao       (amarelo)
    - 2.0–5.0  : bom           (verde claro)
    - 5.0–9.99 : excelente     (verde escuro)
    """
    if ratio < 0.5:
        return "critico"
    if ratio < 1.0:
        return "fraco"
    if ratio < 2.0:
        return "atencao"
    if ratio < 5.0:
        return "bom"
    return "excelente"


# ── Métricas consolidadas (Manual Cap. 4) ─────────────────────────────


def calcular_indice_geral(
    matriz_subpilares: List[Dict[str, Any]],
    pilares: Optional[List[Dict[str, Any]]] = None,
) -> float:
    """Índice Geral (escala 0-10) conforme Manual Cap. 3-4.

    Fórmula (opção B do hotfix, 2026-05-24):

        indice = min(ratio_pior_pilar, ratio_medio_ponderado) × 2
        cap em 10

    Justificativa: o Manual Cap. 3 define o Lastro como sequência
    evolutiva P→D→Pa→A — pilar travado puxa tudo. Média ponderada
    sozinha permite pilares saturados (Pa1 9.99) mascararem um pilar
    crítico (P 0.4). O min() força o pior pilar a determinar o teto.

    Args:
        matriz_subpilares: lista de dicts {ratio, total} por subpilar
            (12 entradas). Usado pra calcular o ratio médio ponderado.
        pilares: lista de 4 dicts {pilar, ratio, total} por pilar
            (P/D/Pa/A). Usado pra extrair o ratio do pior pilar.
            Quando None, calcula da matriz agregando por prefixo.

    Returns:
        0.0 quando não há volume.
    """
    total_volume = sum(c.get("total", 0) for c in matriz_subpilares)
    if total_volume == 0:
        return 0.0

    # Ratio médio ponderado por volume (sobre os 12 subpilares).
    soma_ponderada = sum(c.get("ratio", 0.0) * c.get("total", 0) for c in matriz_subpilares)
    ratio_medio_ponderado = soma_ponderada / total_volume

    # Ratio do pior pilar — considera apenas pilares com volume > 0.
    if pilares is not None:
        ratios_pilares = [p["ratio"] for p in pilares if p.get("total", 0) > 0]
    else:
        # Agrega da matriz por prefixo do código (P/D/Pa/A).
        agg: Dict[str, Dict[str, int]] = {}
        for c in matriz_subpilares:
            sub = c.get("subpilar", "")
            p_code = PILAR_DE_SUBPILAR.get(sub)
            if p_code is None:
                continue
            d = agg.setdefault(p_code, {"promotor": 0, "detrator": 0, "total": 0})
            d["promotor"] += c.get("promotor", 0)
            d["detrator"] += c.get("detrator", 0)
            d["total"] += c.get("total", 0)
        ratios_pilares = [
            calcular_ratio(d["promotor"], d["detrator"]) for d in agg.values() if d["total"] > 0
        ]
    if not ratios_pilares:
        return 0.0
    ratio_pior_pilar = min(ratios_pilares)

    # min() das duas referências → ×2 → cap em 10.
    base = min(ratio_pior_pilar, ratio_medio_ponderado)
    return round(min(10.0, base * 2.0), 2)


def faixa_indice_geral(indice: float) -> str:
    """Faixa do Índice Geral (Manual Cap. 4): ≥7 saudavel, 5-7 atencao, <5 critico."""
    if indice >= 7.0:
        return "saudavel"
    if indice >= 5.0:
        return "atencao"
    return "critico"


def calcular_previsibilidade(
    empresa_id: int,
    s,
    base_query_args: Dict[str, Any],
    pct_conversiveis: float,
) -> float:
    """Previsibilidade (escala 0-100) conforme Manual Cap. 4 + v2.

    Reescrita 2026-05-24 (hotfix B5): a versão anterior dispersava entre
    os 12 subpilares — conceitualmente errado, porque cada subpilar mede
    coisa diferente. O Manual fala "homogeneidade entre lojas, períodos
    e situações". Adotamos a fórmula validada no v2 (analytics.py:1356):

        var_locais  = min(CV(ratios_locais) / 2, 1)   # >= 5 verb/local
        vol_temporal= min(CV(ratios_meses) / 2, 1)    # >= 3 verb/mês
        score = ((1-var_locais)*0.4 + (1-vol_temporal)*0.3 + pct_conv*0.3) * 100

    Filtros de volume mínimo (v2): lojas >= 5 verbatins, meses >= 3.
    Mesmos filtros do painel aplicados (agrupamento, local, fonte, período).
    """
    import statistics

    # 1. Ratios por local (lojas) — usa só locais com >= 5 verbatins
    q_locais = (
        s.query(
            Verbatim.local_id,
            Verbatim.tipo,
            func.count(Verbatim.id),
        )
        .filter(Verbatim.empresa_id == empresa_id)
        .filter(Verbatim.local_id.isnot(None))
        .group_by(Verbatim.local_id, Verbatim.tipo)
    )
    _apply_query_args(q_locais, empresa_id, s, base_query_args)  # filtros painel
    rows_locais = _apply_query_args(q_locais, empresa_id, s, base_query_args).all()
    por_local: Dict[int, Dict[str, int]] = {}
    for lid, tipo, qtd in rows_locais:
        d = por_local.setdefault(lid, {"promotor": 0, "detrator": 0, "total": 0})
        d["total"] += qtd
        if tipo in d:
            d[tipo] += qtd
    ratios_locais = [
        calcular_ratio(d["promotor"], d["detrator"]) for d in por_local.values() if d["total"] >= 5
    ]

    # 2. Ratios por mês — usa só meses com >= 3 verbatins
    mes_expr = func.strftime("%Y-%m", Verbatim.data_criacao_original)
    q_meses = (
        s.query(mes_expr.label("mes"), Verbatim.tipo, func.count(Verbatim.id))
        .filter(Verbatim.empresa_id == empresa_id)
        .filter(Verbatim.data_criacao_original.isnot(None))
        .group_by(mes_expr, Verbatim.tipo)
    )
    rows_meses = _apply_query_args(q_meses, empresa_id, s, base_query_args).all()
    por_mes: Dict[str, Dict[str, int]] = {}
    for mes, tipo, qtd in rows_meses:
        d = por_mes.setdefault(mes, {"promotor": 0, "detrator": 0, "total": 0})
        d["total"] += qtd
        if tipo in d:
            d[tipo] += qtd
    ratios_meses = [
        calcular_ratio(d["promotor"], d["detrator"]) for d in por_mes.values() if d["total"] >= 3
    ]

    # 3. CV de cada eixo
    if len(ratios_locais) >= 2:
        cv = statistics.stdev(ratios_locais) / max(statistics.mean(ratios_locais), 0.01)
        var_locais = min(cv / 2.0, 1.0)
    else:
        var_locais = 0.0
    if len(ratios_meses) >= 3:
        cv = statistics.stdev(ratios_meses) / max(statistics.mean(ratios_meses), 0.01)
        vol_temporal = min(cv / 2.0, 1.0)
    else:
        vol_temporal = 0.0

    # 4. Score combinado (pesos v2)
    score = ((1 - var_locais) * 0.4 + (1 - vol_temporal) * 0.3 + pct_conversiveis * 0.3) * 100
    return round(max(0.0, min(100.0, score)), 1)


def _apply_query_args(q, empresa_id: int, s, base_query_args: Dict[str, Any]):
    """Reaplica os filtros painel numa query base (uso interno de
    calcular_previsibilidade e calcular_concentracao_detratores)."""
    if base_query_args.get("agrupamento_id"):
        try:
            ag_id = int(base_query_args["agrupamento_id"])
            locais_do_ag = [
                lid
                for (lid,) in s.query(Local.id)
                .filter_by(empresa_id=empresa_id, agrupamento_id=ag_id)
                .all()
            ]
            q = q.filter(Verbatim.local_id.in_(locais_do_ag or [-1]))
        except (ValueError, TypeError):
            pass
    if base_query_args.get("local_id"):
        try:
            q = q.filter(Verbatim.local_id == int(base_query_args["local_id"]))
        except (ValueError, TypeError):
            pass
    if base_query_args.get("fonte_id"):
        try:
            q = q.filter(Verbatim.fonte_id == int(base_query_args["fonte_id"]))
        except (ValueError, TypeError):
            pass
    if base_query_args.get("data_inicio_periodo"):
        q = q.filter(Verbatim.data_criacao_original >= base_query_args["data_inicio_periodo"])
    return q


def calcular_concentracao_detratores(
    empresa_id: int, s, base_query_args: Dict[str, Any]
) -> Optional[float]:
    """Concentração de Detratores (%) conforme Manual Cap. 4.

    Ranqueia locais ascendentemente por ratio (piores primeiro). Soma os
    detratores das 5 piores lojas e divide pelo total de detratores da
    empresa, em %.

    Devolve ``None`` se a empresa não tem locais suficientes para
    interpretação (>0 mas <5 locais com volume — métrica perde sentido).

    > 60% = cirúrgico (poucas lojas concentram o problema).
    < 30% = sistêmico (distribuído, processo central).
    """
    # Agrega por local: total de promotores e detratores em verbatins
    # da empresa (com filtros do painel ja aplicados via base_query).
    q = (
        s.query(
            Verbatim.local_id,
            Verbatim.tipo,
            func.count(Verbatim.id),
        )
        .filter(Verbatim.empresa_id == empresa_id)
        .filter(Verbatim.local_id.isnot(None))
        .group_by(Verbatim.local_id, Verbatim.tipo)
    )

    # Aplica filtros opcionais que vieram do request (mesma assinatura
    # de _aplicar_filtros, mas tem que ser inline aqui pra não duplicar)
    if base_query_args.get("agrupamento_id"):
        try:
            ag_id = int(base_query_args["agrupamento_id"])
            locais_do_ag = [
                lid
                for (lid,) in s.query(Local.id)
                .filter_by(empresa_id=empresa_id, agrupamento_id=ag_id)
                .all()
            ]
            q = q.filter(Verbatim.local_id.in_(locais_do_ag or [-1]))
        except (ValueError, TypeError):
            pass
    if base_query_args.get("local_id"):
        try:
            q = q.filter(Verbatim.local_id == int(base_query_args["local_id"]))
        except (ValueError, TypeError):
            pass
    if base_query_args.get("fonte_id"):
        try:
            q = q.filter(Verbatim.fonte_id == int(base_query_args["fonte_id"]))
        except (ValueError, TypeError):
            pass
    if base_query_args.get("data_inicio_periodo"):
        q = q.filter(Verbatim.data_criacao_original >= base_query_args["data_inicio_periodo"])

    rows = q.all()

    # Constrói (local_id → {promotor, detrator, total})
    por_local: Dict[int, Dict[str, int]] = {}
    for local_id, tipo, qtd in rows:
        d = por_local.setdefault(local_id, {"promotor": 0, "detrator": 0, "total": 0})
        d["total"] += qtd
        if tipo in d:
            d[tipo] += qtd

    # Filtro de volume mínimo (Manual: "ratio confiável precisa volume").
    # v2 usava >= 5; mesmo critério.
    LOCAL_VOLUME_MIN = 5
    locais_com_volume = [(lid, d) for lid, d in por_local.items() if d["total"] >= LOCAL_VOLUME_MIN]
    total_locais = len(locais_com_volume)
    total_detratores = sum(d["detrator"] for _, d in locais_com_volume)
    if total_locais < 5 or total_detratores == 0:
        return None

    # Ranqueia ascendentemente por ratio (piores primeiro)
    def _ratio(d: Dict[str, int]) -> float:
        return calcular_ratio(d["promotor"], d["detrator"])

    locais_com_volume.sort(key=lambda x: _ratio(x[1]))
    piores_5 = locais_com_volume[:5]
    detratores_top5 = sum(d["detrator"] for _, d in piores_5)
    return round(100.0 * detratores_top5 / total_detratores, 1)


def faixa_concentracao(pct: Optional[float]) -> str:
    """Faixa da Concentração de Detratores (Manual Cap. 4).

    - > 60%: cirurgico (intervenção em poucas lojas resolve)
    - 30-60%: misto
    - < 30%: sistemico (processo central precisa revisão)
    - None: indisponivel (< 5 locais com volume, ou zero detratores)
    """
    if pct is None:
        return "indisponivel"
    if pct > 60.0:
        return "cirurgico"
    if pct >= 30.0:
        return "misto"
    return "sistemico"


# ── Filtros (subset dos da listagem de verbatins) ─────────────────────


def _resolver_periodo(periodo: str) -> Optional[datetime]:
    """``7d``/``30d``/``90d``/``6m``/``12m``/``15m`` → datetime início.

    Inválido → None (e o caller devolve 400). Vazio = sem filtro (tudo).
    """
    if not periodo:
        return None
    hoje = datetime.utcnow()
    mapa = {
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "6m": timedelta(days=180),
        "12m": timedelta(days=365),
        "15m": timedelta(days=450),
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
    if periodo:
        d = _resolver_periodo(periodo)
        if d is None:
            return q, (
                jsonify({"erro": "periodo inválido. Use: 7d, 30d, 90d, 6m, 12m, 15m"}),
                400,
            )
        q = q.filter(Verbatim.data_criacao_original >= d)

    return q, None


def _filtros_efetivos() -> Dict[str, Any]:
    """Retorna dict serializável dos filtros usados (eco para o front)."""
    return {
        k: request.args.get(k)
        for k in ("agrupamento_id", "local_id", "fonte_id", "periodo")
        if request.args.get(k)
    }


# ── Endpoint Nível 1: 4 pilares ────────────────────────────────────────


@cliente_pode_ver_empresa("empresa_id")
def painel_nivel1(empresa_id: int):
    """Totais por pilar (P, D, Pa, A) + métricas consolidadas (Cap. 4)."""
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

        # Agrega por pilar e também monta a matriz por subpilar
        # (mesma estrutura do nivel2) para alimentar Índice/Previsibilidade.
        pilares_agg: Dict[str, Dict[str, int]] = {
            p: {"total": 0, "promotor": 0, "conversivel": 0, "detrator": 0, "inativo": 0}
            for p in PILARES_ORDEM
        }
        subpilares_agg: Dict[str, Dict[str, int]] = {
            sp: {"promotor": 0, "conversivel": 0, "detrator": 0, "inativo": 0, "total": 0}
            for sp in SUBPILARES_ORDEM
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
                subpilares_agg[subpilar]["total"] += qtd
                if tipo in subpilares_agg[subpilar]:
                    subpilares_agg[subpilar][tipo] += qtd
            elif subpilar == "sem_lastro":
                outros["sem_lastro"] += qtd
            else:
                outros["sem_classificacao"] += qtd

        # Constrói matriz com ratios para alimentar as 3 métricas.
        matriz_para_metricas: List[Dict[str, Any]] = []
        for sp in SUBPILARES_ORDEM:
            cell = subpilares_agg[sp]
            ratio = calcular_ratio(cell["promotor"], cell["detrator"])
            matriz_para_metricas.append({**cell, "subpilar": sp, "ratio": ratio})

        # Pilares construídos antes pra passar ao calcular_indice_geral (opção B).
        pilares: List[Dict[str, Any]] = []
        for p in PILARES_ORDEM:
            agg = pilares_agg[p]
            ratio = calcular_ratio(agg["promotor"], agg["detrator"])
            pilares.append(
                {
                    "pilar": p,
                    "nome": NOME_PILAR[p],
                    "total": agg["total"],
                    "promotor": agg["promotor"],
                    "conversivel": agg["conversivel"],
                    "detrator": agg["detrator"],
                    "inativo": agg["inativo"],
                    "ratio": ratio,
                    "faixa": faixa_ratio(ratio),
                }
            )

        # Resolve data_inicio_periodo para reusar em previsibilidade/concentração
        periodo_arg = request.args.get("periodo")
        data_inicio_periodo = _resolver_periodo(periodo_arg) if periodo_arg else None
        filtros_query = {
            "agrupamento_id": request.args.get("agrupamento_id"),
            "local_id": request.args.get("local_id"),
            "fonte_id": request.args.get("fonte_id"),
            "data_inicio_periodo": data_inicio_periodo,
        }

        # Previsibilidade precisa de pct_conversiveis (verbatins classificados,
        # excluindo sem_lastro/inativo do denominador conforme decisão arq.).
        verbatins_classificados = sum(p["total"] for p in pilares)
        conversiveis = sum(p["conversivel"] for p in pilares)
        pct_conv = (conversiveis / verbatins_classificados) if verbatins_classificados else 0.0

        previsibilidade = calcular_previsibilidade(empresa_id, s, filtros_query, pct_conv)
        concentracao_pct = calcular_concentracao_detratores(empresa_id, s, filtros_query)

    # Índice Geral (opção B: min(pior_pilar, ratio_medio) × 2)
    indice_geral = calcular_indice_geral(matriz_para_metricas, pilares=pilares)

    return jsonify(
        {
            "empresa_id": empresa_id,
            "filtros": _filtros_efetivos(),
            "total_verbatins": total_geral,
            "pilares": pilares,
            "outros": outros,
            # B5 ext. CP-3: métricas consolidadas (Manual Cap. 4)
            "indice_geral": indice_geral,
            "indice_geral_faixa": faixa_indice_geral(indice_geral),
            "previsibilidade": previsibilidade,
            "concentracao_detratores": concentracao_pct,
            "concentracao_faixa": faixa_concentracao(concentracao_pct),
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
        ratio = calcular_ratio(cell["promotor"], cell["detrator"])
        matriz.append(
            {
                "subpilar": sp,
                "nome": NOME_SUBPILAR[sp],
                "pilar": PILAR_DE_SUBPILAR[sp],
                "promotor": cell["promotor"],
                "conversivel": cell["conversivel"],
                "detrator": cell["detrator"],
                "inativo": cell["inativo"],
                "total": cell["total"],
                "ratio": ratio,
                "faixa": faixa_ratio(ratio),
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


# ── Leitura textual sequencial (Bloco 5 ext. CP-5) ────────────────────


@cliente_pode_ver_empresa("empresa_id")
def painel_leitura(empresa_id: int):
    """Leitura textual sequencial via Sonnet (Manual Cap. 3).

    Chama painel_nivel1 internamente para obter o estado atual, depois
    pede ao Sonnet para interpretar em 2-3 frases. Carregado async no
    UI para não atrasar o painel principal.
    """
    from src.api.painel_leitura import gerar_leitura_sequencial

    resp_n1 = painel_nivel1(empresa_id)
    if isinstance(resp_n1, tuple):
        return resp_n1  # propaga erro (400/403)
    n1 = resp_n1.get_json()
    leitura = gerar_leitura_sequencial(n1 or {})
    return jsonify({"empresa_id": empresa_id, "leitura": leitura})


# ── Exportar XLSX (Bloco 5 CP-3) ──────────────────────────────────────


@cliente_pode_ver_empresa("empresa_id")
def exportar_painel_xlsx(empresa_id: int):
    """Exporta painel (Visão Geral + Detalhamento) em XLSX com 2 sheets."""
    from io import BytesIO

    from flask import send_file
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    # Reusa a lógica dos 2 endpoints chamando-os internamente
    resp_n1 = painel_nivel1(empresa_id)
    if isinstance(resp_n1, tuple):
        return resp_n1
    resp_n2 = painel_nivel2(empresa_id)
    if isinstance(resp_n2, tuple):
        return resp_n2
    n1 = resp_n1.get_json()
    n2 = resp_n2.get_json()

    wb = Workbook()
    bold = Font(bold=True)
    header_fill = PatternFill("solid", fgColor="E5E7EB")

    # Sheet 1: Visão Geral
    ws1 = wb.active
    ws1.title = "Visão Geral"
    ws1.append([f"Empresa #{empresa_id} — Painel Executivo (Visão Geral)"])
    ws1["A1"].font = bold
    filtros = n1.get("filtros") or {}
    if filtros:
        ws1.append(["Filtros aplicados:", " | ".join(f"{k}={v}" for k, v in filtros.items())])
    ws1.append([f"Total verbatins: {n1.get('total_verbatins', 0)}"])
    ws1.append([])
    headers1 = [
        "Pilar",
        "Nome",
        "Total",
        "Promotor",
        "Conversível",
        "Detrator",
        "Inativo",
        "Ratio P/D",
        "Faixa",
    ]
    ws1.append(headers1)
    for cell in ws1[ws1.max_row]:
        cell.font = bold
        cell.fill = header_fill
    for p in n1.get("pilares", []):
        ws1.append(
            [
                p["pilar"],
                p["nome"],
                p["total"],
                p["promotor"],
                p["conversivel"],
                p["detrator"],
                p["inativo"],
                p.get("ratio", 0.0),
                p.get("faixa", ""),
            ]
        )
    ws1.append([])
    outros = n1.get("outros") or {}
    if outros:
        ws1.append(["Fora dos 4 pilares:"])
        ws1[ws1.max_row][0].font = bold
        ws1.append(["sem_lastro", outros.get("sem_lastro", 0)])
        ws1.append(["sem_classificação", outros.get("sem_classificacao", 0)])

    # Sheet 2: Detalhamento por Subpilar
    ws2 = wb.create_sheet("Detalhamento por Subpilar")
    ws2.append([f"Empresa #{empresa_id} — Detalhamento por Subpilar"])
    ws2["A1"].font = bold
    if filtros:
        ws2.append(["Filtros aplicados:", " | ".join(f"{k}={v}" for k, v in filtros.items())])
    ws2.append([])
    headers2 = [
        "Pilar",
        "Subpilar",
        "Nome do Subpilar",
        "Promotor",
        "Conversível",
        "Detrator",
        "Inativo",
        "Total",
        "Ratio P/D",
        "Faixa",
    ]
    ws2.append(headers2)
    for cell in ws2[ws2.max_row]:
        cell.font = bold
        cell.fill = header_fill
    for c in n2.get("matriz", []):
        ws2.append(
            [
                c["pilar"],
                c["subpilar"],
                c.get("nome", ""),
                c["promotor"],
                c["conversivel"],
                c["detrator"],
                c["inativo"],
                c["total"],
                c.get("ratio", 0.0),
                c.get("faixa", ""),
            ]
        )
    sl = n2.get("sem_lastro") or {}
    sc = n2.get("sem_classificacao") or {}
    if sl.get("total"):
        ws2.append(
            [
                "—",
                "sem_lastro",
                "(sem ancoragem)",
                "—",
                "—",
                "—",
                sl.get("inativo", 0),
                sl["total"],
                "—",
                "—",
            ]
        )
    if sc.get("total"):
        ws2.append(
            [
                "—",
                "sem classificação",
                "(falha classifier)",
                "—",
                "—",
                "—",
                "—",
                sc["total"],
                "—",
                "—",
            ]
        )

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    fname = f"painel_empresa_{empresa_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        buf,
        as_attachment=True,
        download_name=fname,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
