"""Camada de leitura da Lente de Governança (CP-LG-4).

Read-only: lê de ``proximity_calculations`` / ``previsibilidade_calculations``,
com **guarda de frescor lazy** (popula no 1º acesso se a tabela estiver vazia —
espelha a guarda de ``ratios_mensais`` em ``ui._explorar_evolucao``). Em produção
o passo 7.5 do pós-coleta mantém os dados frescos.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def garantir_governanca(empresa_id: int) -> None:
    """Popula a governança se Proximity OU Gini estiverem vazios p/ a empresa
    (recalcular_governanca pula o que já está fresco via hash)."""
    from src.governanca.metricas import recalcular_governanca
    from src.models.governanca import GiniConcentracao, ProximityCalculation
    from src.utils.db import db_session

    with db_session() as s:
        tem_prox = (
            s.query(ProximityCalculation.id)
            .filter(ProximityCalculation.empresa_id == empresa_id)
            .first()
        )
        tem_gini = (
            s.query(GiniConcentracao.id).filter(GiniConcentracao.empresa_id == empresa_id).first()
        )
    if tem_prox is None or tem_gini is None:
        recalcular_governanca(empresa_id)


def escopo_de_filtros(agrupamento_id, local_id) -> Tuple[str, Optional[int]]:
    """(escopo_tipo, escopo_id) a partir dos filtros do painel. local > ag > empresa."""
    if local_id:
        return "loja", int(local_id)
    if agrupamento_id:
        return "agrupamento", int(agrupamento_id)
    return "empresa", None


def proximity_escopo(
    s, empresa_id: int, escopo_tipo: str, escopo_id: Optional[int]
) -> Dict[str, Any]:
    """Linha agregada (subpilar e pilar NULL) de Proximity do escopo.
    ``{valor, faixa}`` — None/None se sem dado suficiente ou sem linha."""
    from src.models.governanca import ProximityCalculation as PC

    cond_id = PC.escopo_id.is_(None) if escopo_id is None else (PC.escopo_id == escopo_id)
    row = (
        s.query(PC.proximity_0_100, PC.faixa)
        .filter(
            PC.empresa_id == empresa_id,
            PC.escopo_tipo == escopo_tipo,
            cond_id,
            PC.subpilar.is_(None),
            PC.pilar.is_(None),
        )
        .first()
    )
    return {"valor": row[0], "faixa": row[1]} if row else {"valor": None, "faixa": None}


def proximity_por_loja(s, empresa_id: int) -> Dict[int, Dict[str, Any]]:
    """Proximity agregada de cada loja → ``{local_id: {valor, faixa, n_pilares}}``.

    ``n_pilares`` = nº de pilares COM lastro (pilar-level com proximity não-NULL)
    que embasam o agregado — sinaliza confiança parcial no Leaderboard
    (mono/bi-pilar). Usado pelo Leaderboard (2 queries, sem N+1)."""
    from sqlalchemy import func

    from src.models.governanca import ProximityCalculation as PC

    rows = (
        s.query(PC.escopo_id, PC.proximity_0_100, PC.faixa)
        .filter(
            PC.empresa_id == empresa_id,
            PC.escopo_tipo == "loja",
            PC.subpilar.is_(None),
            PC.pilar.is_(None),
        )
        .all()
    )
    n_pilares = dict(
        s.query(PC.escopo_id, func.count(PC.id))
        .filter(
            PC.empresa_id == empresa_id,
            PC.escopo_tipo == "loja",
            PC.pilar.isnot(None),
            PC.proximity_0_100.isnot(None),
        )
        .group_by(PC.escopo_id)
        .all()
    )
    return {
        lid: {"valor": v, "faixa": f, "n_pilares": int(n_pilares.get(lid, 0))} for lid, v, f in rows
    }


def proximity_subpilares_escopo(
    s, empresa_id: int, escopo_tipo: str, escopo_id: Optional[int]
) -> Dict[str, Dict[str, Any]]:
    """Linhas subpilar-level de Proximity do escopo → ``{subpilar: {valor, faixa}}``.
    Usado pela coluna Proximity do Confronto Visual."""
    from src.models.governanca import ProximityCalculation as PC

    cond_id = PC.escopo_id.is_(None) if escopo_id is None else (PC.escopo_id == escopo_id)
    rows = (
        s.query(PC.subpilar, PC.proximity_0_100, PC.faixa)
        .filter(
            PC.empresa_id == empresa_id,
            PC.escopo_tipo == escopo_tipo,
            cond_id,
            PC.subpilar.isnot(None),
        )
        .all()
    )
    return {sub: {"valor": v, "faixa": f} for sub, v, f in rows}


def proximity_pilares_escopo(
    s, empresa_id: int, escopo_tipo: str, escopo_id: Optional[int]
) -> Dict[str, Dict[str, Any]]:
    """Proximity por pilar (pilar-level rows) do escopo → {pilar: {valor, faixa}}.
    Usado pelo radar do Painel de Governança (CP-LG-8)."""
    from src.models.governanca import ProximityCalculation as PC

    cond = PC.escopo_id.is_(None) if escopo_id is None else (PC.escopo_id == escopo_id)
    rows = (
        s.query(PC.pilar, PC.proximity_0_100, PC.faixa)
        .filter(
            PC.empresa_id == empresa_id,
            PC.escopo_tipo == escopo_tipo,
            cond,
            PC.pilar.isnot(None),
        )
        .all()
    )
    return {p: {"valor": v, "faixa": f} for p, v, f in rows}


def cobertura_governanca(s, empresa_id: int) -> Dict[str, int]:
    """{total, com_dado}: lojas cadastradas vs lojas com Proximity agregada (lastro).
    Alimenta o aviso 'base em formação' do board."""
    from src.models.governanca import ProximityCalculation as PC
    from src.models.local import Local

    total = s.query(Local).filter_by(empresa_id=empresa_id).count()
    com_dado = (
        s.query(PC.escopo_id)
        .filter(
            PC.empresa_id == empresa_id,
            PC.escopo_tipo == "loja",
            PC.subpilar.is_(None),
            PC.pilar.is_(None),
            PC.proximity_0_100.isnot(None),
        )
        .count()
    )
    return {"total": total, "com_dado": com_dado}


def distribuicao_previsibilidade(s, empresa_id: int) -> Dict[str, int]:
    """Contagem de lojas por faixa de previsibilidade + 'sem_dado' (NULL = histórico
    curto, NÃO é faixa de qualidade — categoria à parte). CP-LG-8 Bloco 3."""
    from src.models.governanca import PrevisibilidadeCalculation as PV

    rows = (
        s.query(PV.previsibilidade_0_100, PV.faixa)
        .filter(PV.empresa_id == empresa_id, PV.escopo_tipo == "loja")
        .all()
    )
    d = {"estavel": 0, "medio": 0, "erratico": 0, "sem_dado": 0}
    for val, faixa in rows:
        if val is None or faixa is None:
            d["sem_dado"] += 1
        else:
            d[faixa] = d.get(faixa, 0) + 1
    return d


# Ordem de excelência do selo (régua fechada com o Dener — 4/3/2 subpilares >60).
_SELO_RANK = {"ouro": 3, "prata": 2, "bronze": 1, None: 0}


def ranking_lojas_governanca(s, empresa_id: int, n: int = 5) -> Dict[str, Any]:
    """Top/bottom n lojas (NOMINADAS), com selo e n_pilares ('base Np' do LG-4.1).
    Lojas sem Proximity ficam fora (não são '0'). CP-LG-8 Bloco 4.

    **Top** = régua de EXCELÊNCIA (selo): Ouro>Prata>Bronze>sem selo, proximity
    desc no desempate. Proximity 100 mono-pilar (sem selo) NÃO lidera — não tem
    base. **Bottom** = fraqueza: proximity asc; no empate (vários '0'), mais
    pilares com lastro primeiro (fraqueza ampla confirmada > fraqueza num canto)."""
    from src.models.local import Local

    prox = proximity_por_loja(s, empresa_id)
    selos = selos_por_loja(s, empresa_id)
    nomes = {x.id: x.nome for x in s.query(Local).filter_by(empresa_id=empresa_id).all()}
    com_dado = [
        {
            "local_id": lid,
            "nome": nomes.get(lid, f"loja {lid}"),
            "proximity": d["valor"],
            "n_pilares": d["n_pilares"],
            "selo": selos.get(lid),
        }
        for lid, d in prox.items()
        if d["valor"] is not None
    ]
    # Top: selo desc, depois proximity desc.
    top = sorted(com_dado, key=lambda x: (-_SELO_RANK.get(x["selo"], 0), -x["proximity"]))[:n]
    # Bottom: proximity asc, depois MAIS pilares primeiro (fraqueza ampla).
    bottom = (
        sorted(com_dado, key=lambda x: (x["proximity"], -x["n_pilares"]))[:n]
        if len(com_dado) > n
        else []
    )
    return {"top": top, "bottom": bottom, "n_com_dado": len(com_dado)}


def distribuicao_selos(s, empresa_id: int) -> Dict[str, int]:
    """Contagem de lojas por selo (CP-LG-8 Bloco 4)."""
    vals = selos_por_loja(s, empresa_id).values()
    d = {"ouro": 0, "prata": 0, "bronze": 0, "sem_selo": 0}
    for sl in vals:
        d[sl if sl else "sem_selo"] += 1
    return d


def radar_svg_data(pilares: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Geometria do radar 4 pilares (P topo · D direita · Pa baixo · A esquerda),
    SVG inline server-side. ``pilares`` = {pilar: {valor, faixa}}. Pilar NULL →
    eixo tracejado, SEM vértice (polígono pula). 0 pilares com dado → sem polígono
    (board mostra 'base em formação')."""
    cx = cy = 130
    R = 95
    dirs = [
        ("P", "Precisão", 0, -1),
        ("D", "Disponibilidade", 1, 0),
        ("Pa", "Parceria", 0, 1),
        ("A", "Aconselhamento", -1, 0),
    ]
    eixos = []
    poly = []
    for cod, nome, dx, dy in dirs:
        d = pilares.get(cod) or {}
        val = d.get("valor")
        tip = (round(cx + R * dx, 1), round(cy + R * dy, 1))
        lab = (round(cx + (R + 18) * dx, 1), round(cy + (R + 18) * dy, 1))
        if val is None:
            eixos.append(
                {
                    "pilar": cod,
                    "nome": nome,
                    "valor": None,
                    "faixa": None,
                    "tip": tip,
                    "lab": lab,
                    "vx": None,
                    "vy": None,
                    "null": True,
                }
            )
        else:
            vx = round(cx + R * (val / 100.0) * dx, 1)
            vy = round(cy + R * (val / 100.0) * dy, 1)
            eixos.append(
                {
                    "pilar": cod,
                    "nome": nome,
                    "valor": val,
                    "faixa": d.get("faixa"),
                    "tip": tip,
                    "lab": lab,
                    "vx": vx,
                    "vy": vy,
                    "null": False,
                }
            )
            poly.append(f"{vx},{vy}")
    return {
        "cx": cx,
        "cy": cy,
        "R": R,
        "size": 2 * cx,
        "rings": [round(R * f, 1) for f in (0.25, 0.5, 0.75, 1.0)],
        "eixos": eixos,
        "poligono": " ".join(poly),
        "n_dados": len(poly),
    }


def heatmap_detratores(s, empresa_id: int, ag_id=None, top_n: int = 12) -> Dict[str, Any]:
    """Dados do heatmap loja×subpilar de DETRATORES (CP-LG-3.1). Leitura de
    ``Verbatim`` agregado por (local, subpilar, tipo) — contagem, sem métrica nova.
    Mostra as ``top_n`` lojas por total de detratores (legibilidade). Por célula:
    {det, total} (distingue 'medido zero' de 'sem dado')."""
    from sqlalchemy import func

    from src.api.painel import SUBPILARES_ORDEM
    from src.models.local import Local
    from src.models.verbatim import Verbatim

    q = (
        s.query(Verbatim.local_id, Verbatim.subpilar, Verbatim.tipo, func.count(Verbatim.id))
        .filter(
            Verbatim.empresa_id == empresa_id,
            Verbatim.local_id.isnot(None),
            Verbatim.subpilar.isnot(None),
        )
        .group_by(Verbatim.local_id, Verbatim.subpilar, Verbatim.tipo)
    )
    if ag_id is not None:
        locais_ag = [
            lid
            for (lid,) in s.query(Local.id).filter_by(empresa_id=empresa_id, agrupamento_id=ag_id)
        ]
        q = q.filter(Verbatim.local_id.in_(locais_ag or [-1]))
    cell: Dict = {}
    det_loja: Dict[int, int] = {}
    for lid, sub, tipo, n in q.all():
        c = cell.setdefault((lid, sub), {"det": 0, "total": 0})
        c["total"] += int(n)
        if tipo == "detrator":
            c["det"] += int(n)
            det_loja[lid] = det_loja.get(lid, 0) + int(n)
    total_det = sum(det_loja.values())
    top = sorted(det_loja, key=lambda lid: -det_loja[lid])[:top_n]
    nomes = {x.id: x.nome for x in s.query(Local).filter(Local.id.in_(top)).all()} if top else {}
    cob = sum(det_loja[lid] for lid in top)
    return {
        "subpilares": list(SUBPILARES_ORDEM),
        "lojas": [
            {"local_id": lid, "nome": nomes.get(lid, f"loja {lid}"), "det_total": det_loja[lid]}
            for lid in top
        ],
        "cells": {f"{lid}|{sub}": c for (lid, sub), c in cell.items() if lid in top},
        "total_det": total_det,
        "cobertura_pct": round(100 * cob / total_det) if total_det else 0,
        "n_lojas_com_detrator": len(det_loja),
        "n_omitidas": max(0, len(det_loja) - len(top)),
        "top_n": top_n,
    }


def heatmap_render(dados: Dict[str, Any], modo: str = "abs") -> Dict[str, Any]:
    """Matriz pronta p/ SVG: por célula state (sem_dado|zero|det) + fill + opacity.
    Escala SQRT (não-linear) p/ o outlier não achatar o meio. ``modo``: 'abs'
    (detratores) ou 'pct' (% dos detratores da loja). Função pura."""
    import math

    det_loja = {lj["local_id"]: lj["det_total"] for lj in dados["lojas"]}
    cells = dados["cells"]

    def _base(lid, det):
        if modo == "pct" and det_loja.get(lid):
            return det / det_loja[lid]
        return det

    vals = [_base(int(k.split("|")[0]), c["det"]) for k, c in cells.items() if c["det"] > 0]
    scale_max = max(vals) if vals else 1.0

    matriz = []
    for loja in dados["lojas"]:
        lid = loja["local_id"]
        row = []
        for sub in dados["subpilares"]:
            c = cells.get(f"{lid}|{sub}")
            if c is None or c["total"] == 0:
                row.append(
                    {
                        "state": "sem_dado",
                        "fill": "#C9C2B6",
                        "opacity": 1.0,
                        "det": None,
                        "total": 0,
                        "share": None,
                    }
                )
            elif c["det"] == 0:
                row.append(
                    {
                        "state": "zero",
                        "fill": "#FBF9F5",
                        "opacity": 1.0,
                        "det": 0,
                        "total": c["total"],
                        "share": 0,
                    }
                )
            else:
                inten = math.sqrt(_base(lid, c["det"]) / scale_max) if scale_max > 0 else 0.0
                row.append(
                    {
                        "state": "det",
                        "fill": "#b3261e",
                        "opacity": round(0.12 + 0.88 * inten, 3),
                        "det": c["det"],
                        "total": c["total"],
                        "share": round(100 * c["det"] / det_loja[lid]) if det_loja.get(lid) else 0,
                    }
                )
        matriz.append({"loja": loja, "cells": row})
    return {"matriz": matriz, "modo": modo}


def gini_escopo(
    s, empresa_id: int, escopo_tipo: str, escopo_id: Optional[int]
) -> Optional[Dict[str, Any]]:
    """Lê a linha de ``gini_concentracao`` do escopo → dict pronto p/ a UI
    (gini bruto + corrigido + faixa + bolsão + lojas). None se não há linha."""
    import json

    from src.models.governanca import GiniConcentracao as GC

    cond = GC.escopo_id.is_(None) if escopo_id is None else (GC.escopo_id == escopo_id)
    row = (
        s.query(GC.gini, GC.top_n_lojas, GC.distribuicao_json)
        .filter(GC.empresa_id == empresa_id, GC.escopo_tipo == escopo_tipo, cond)
        .first()
    )
    if row is None:
        return None
    dj = json.loads(row[2]) if row[2] else {}
    return {
        "gini_bruto": row[0],
        "gini_corrigido": dj.get("gini_corrigido"),
        "faixa": dj.get("faixa"),
        "top_n": dj.get("top_n"),
        "share": dj.get("share"),
        "total_lojas": dj.get("total_lojas"),
        "total_detratores": dj.get("total_detratores"),
        "lojas": dj.get("lojas", []),
        "insuficiente": dj.get("insuficiente", False),
        "motivo": dj.get("motivo"),
    }


def leitura_concentracao(d: Optional[Dict[str, Any]]) -> str:
    """Leitura editorial determinística ($0 LLM) da concentração."""
    if d is None or d.get("insuficiente"):
        if d and d.get("motivo") == "sem_detratores":
            return "Sem detratores registrados neste escopo — nada a concentrar."
        return "Concentração indisponível — menos de 5 lojas medidas neste escopo."
    share_pct = round((d.get("share") or 0) * 100)
    base_pct = round(100 * d["top_n"] / d["total_lojas"]) if d.get("total_lojas") else 0
    nome = {"baixa": "baixa (distribuída)", "media": "média", "alta": "alta (concentrada)"}.get(
        d.get("faixa"), d.get("faixa")
    )
    return (
        f"{share_pct}% dos detratores concentram-se em {d['top_n']} de "
        f"{d['total_lojas']} lojas ({base_pct}% da base) → concentração {nome}."
    )


def _n_sub_acima(s, empresa_id, escopo_id=None):
    """{local_id: nº subpilares com Proximity > corte} (escopo loja)."""
    from sqlalchemy import func

    from src.governanca.metricas import SELO_PROXIMITY_CORTE
    from src.models.governanca import ProximityCalculation as PC

    q = s.query(PC.escopo_id, func.count(PC.id)).filter(
        PC.empresa_id == empresa_id,
        PC.escopo_tipo == "loja",
        PC.subpilar.isnot(None),
        PC.proximity_0_100.isnot(None),
        PC.proximity_0_100 > SELO_PROXIMITY_CORTE,
    )
    if escopo_id is not None:
        q = q.filter(PC.escopo_id == escopo_id)
    return dict(q.group_by(PC.escopo_id).all())


def selos_por_loja(s, empresa_id: int) -> Dict[int, Optional[str]]:
    """{local_id: selo} para todas as lojas medidas (selo None = sem selo).
    On-the-fly (2 queries): subpilares >60 por loja + previsibilidade LG-2."""
    from src.governanca.metricas import selo_loja
    from src.models.governanca import PrevisibilidadeCalculation as PV
    from src.models.governanca import ProximityCalculation as PC

    n_sub = _n_sub_acima(s, empresa_id)
    prev = {
        r[0]: r[1]
        for r in s.query(PV.escopo_id, PV.previsibilidade_0_100).filter(
            PV.empresa_id == empresa_id, PV.escopo_tipo == "loja"
        )
    }
    # universo = lojas com linha agregada de proximity (toda loja medida tem uma)
    universo = [
        r[0]
        for r in s.query(PC.escopo_id).filter(
            PC.empresa_id == empresa_id,
            PC.escopo_tipo == "loja",
            PC.subpilar.is_(None),
            PC.pilar.is_(None),
        )
    ]
    return {lid: selo_loja(n_sub.get(lid, 0), prev.get(lid)) for lid in universo}


def anexar_impacto_acoes(s, empresa_id, itens):
    """Anexa ``it.projecao`` (CP-LG-5) + ``it.projecao_loja`` a cada item com
    ``subpilar``. Cache de agg/previsibilidade por escopo (sem N+1). Mutação
    in-place. **Mesma função na tela e nos PDFs** → números idênticos por
    construção. Itens sem ``prioridade`` (ex.: ações de subpilar do B2') derivam-na
    da faixa via ``_FAIXA_PRIORIDADE``. (Nome ``projecao`` evita colidir com o
    campo ``impacto`` textual já existente nas ações do B2'.)"""
    from src.diagnostico.leituras import agregar_subpilares
    from src.governanca.impacto_rs import rs_fluxo_recuperados, taxas_empresa
    from src.governanca.metricas import TAXA_SUCESSO_PRIORIDADE, simular_impacto_acao
    from src.models.empresa import Empresa
    from src.planos.consolidar import _FAIXA_PRIORIDADE

    # Taxas POR EMPRESA (CP-impacto-rs); fallback na constante se a empresa sumiu.
    _emp = s.get(Empresa, empresa_id)
    taxas = taxas_empresa(_emp) if _emp is not None else None

    agg_cache = {}
    prev_cache = {}
    fluxo_cache: dict = {}  # (agid, lid, sub, rate) → {valor,n_ltv,n_total}
    for it in itens:
        sub = getattr(it, "subpilar", None)
        if not sub:
            it.projecao = None
            it.projecao_loja = False
            continue
        lid = getattr(it, "local_id", None)
        agid = getattr(it, "agrupamento_id", None)
        key = (agid, lid)
        if key not in agg_cache:
            agg_cache[key] = agregar_subpilares(s, empresa_id, agid, lid)
        prev = None
        if lid is not None:
            if lid not in prev_cache:
                prev_cache[lid] = previsibilidade_loja(s, empresa_id, lid)["valor"]
            prev = prev_cache[lid]
        prioridade = getattr(it, "prioridade", None) or _FAIXA_PRIORIDADE.get(
            getattr(it, "faixa", None), "medio"
        )
        # Fluxo R$ AGREGADO (CP-fluxo-agregado): Σ_loja recuperados_loja × LTV_loja
        # nas lojas afetadas pelo escopo da ação (empresa/agrupamento/loja) — mesmo
        # grão e cobertura "N de M lojas" do Estoque. Substitui o "1 loja ou nada".
        rate = (taxas or TAXA_SUCESSO_PRIORIDADE).get(prioridade, TAXA_SUCESSO_PRIORIDADE["medio"])
        fk = (agid, lid, sub, rate)
        if fk not in fluxo_cache:
            fluxo_cache[fk] = rs_fluxo_recuperados(
                s, empresa_id, sub, rate, ag_id=agid, local_id=lid
            )
        it.projecao = simular_impacto_acao(
            agg_cache[key], sub, prioridade, prev, taxas=taxas, fluxo_rs=fluxo_cache[fk]
        )
        it.projecao_loja = lid is not None


def selo_de_loja(s, empresa_id: int, local_id: int) -> Optional[str]:
    """Selo de UMA loja (escopo loja) — para o cabeçalho do Painel de Loja."""
    from src.governanca.metricas import selo_loja
    from src.models.governanca import PrevisibilidadeCalculation as PV

    n = _n_sub_acima(s, empresa_id, local_id).get(local_id, 0)
    p = (
        s.query(PV.previsibilidade_0_100)
        .filter(PV.empresa_id == empresa_id, PV.escopo_tipo == "loja", PV.escopo_id == local_id)
        .scalar()
    )
    return selo_loja(n, p)


def previsibilidade_loja(s, empresa_id: int, local_id: int) -> Dict[str, Any]:
    """Previsibilidade LG-2 (CV temporal puro) de uma loja.
    ``{valor, faixa, n_meses, cv}`` — None se sem linha/dado."""
    from src.models.governanca import PrevisibilidadeCalculation as PV

    row = (
        s.query(PV.previsibilidade_0_100, PV.faixa, PV.n_meses, PV.cv)
        .filter(PV.empresa_id == empresa_id, PV.escopo_tipo == "loja", PV.escopo_id == local_id)
        .first()
    )
    if row is None:
        return {"valor": None, "faixa": None, "n_meses": None, "cv": None}
    return {"valor": row[0], "faixa": row[1], "n_meses": row[2], "cv": row[3]}
