"""B4 — Diagnóstico Longitudinal (doc-ouro · evolução temporal).

Matriz 12 subpilares × 6 quarters com ratios + tendência ↑↓→ + quebras
estruturais (mudança de nível N entre quarters). 1 LLM cacheada gera
narrativa geral + 4 parágrafos por quarter mais recente. ~$0.04 fria, $0
recorrente."""

from __future__ import annotations

import hashlib
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def _escopo_hash(empresa_id: int) -> str:
    return _hash(f"emp={empresa_id}|ag=|loc=")


def _quarter(dt: datetime) -> str:
    return f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"


def _quarter_prev(q: str) -> str:
    y, qn = int(q[:4]), int(q[-1])
    return f"{y - 1}-Q4" if qn == 1 else f"{y}-Q{qn - 1}"


def _ultimos_quarters(n: int = 6, ref: Optional[datetime] = None) -> List[str]:
    """Lista os ``n`` quarters mais recentes terminando no quarter de ``ref``
    (default: agora), em ordem cronológica crescente."""
    ref = ref or datetime.utcnow()
    cur = _quarter(ref)
    out = [cur]
    for _ in range(n - 1):
        out.append(_quarter_prev(out[-1]))
    return list(reversed(out))


_NIVEL = {"critico": 1, "fraco": 2, "atencao": 2, "bom": 3, "excelente": 4}


def montar_dados(
    empresa_id: int,
    *,
    gerar_narrativa_fn: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Pacote doc-ouro do Longitudinal: matriz 12×6 + quebras + narrativa LLM."""
    from sqlalchemy import func

    from src.api.painel import (
        NOME_PILAR,
        NOME_SUBPILAR,
        PILAR_DE_SUBPILAR,
        SUBPILARES_ORDEM,
        calcular_ratio,
        faixa_ratio,
    )
    from src.diagnostico.leituras import _gargalo, agregar_subpilares
    from src.models.empresa import Empresa
    from src.models.verbatim import Verbatim
    from src.relatorios.llm_secoes import gerar_narrativa_longitudinal
    from src.utils.db import db_session

    quarters = _ultimos_quarters(6)
    escopo_h = _escopo_hash(empresa_id)

    with db_session() as s:
        empresa = s.get(Empresa, empresa_id)
        empresa_nome = empresa.nome if empresa else f"empresa #{empresa_id}"

        # Agregado por (subpilar, quarter) — usa data_criacao_original.
        # SQLite não tem QUARTER nativo; calculo com year + month via string.
        rows = (
            s.query(
                Verbatim.subpilar,
                func.strftime("%Y", Verbatim.data_criacao_original).label("ano"),
                func.strftime("%m", Verbatim.data_criacao_original).label("mes"),
                Verbatim.tipo,
                func.count(Verbatim.id).label("n"),
            )
            .filter(
                Verbatim.empresa_id == empresa_id,
                Verbatim.subpilar.isnot(None),
                Verbatim.data_criacao_original.isnot(None),
            )
            .group_by(Verbatim.subpilar, "ano", "mes", Verbatim.tipo)
            .all()
        )

        # Empresa-wide atual (gargalo persistente, comparação cap-stone)
        agg = agregar_subpilares(s, empresa_id, None)
        gargalo = _gargalo(agg)
        gargalo_nome = NOME_PILAR.get(gargalo, gargalo) if gargalo else None

    # Reduz para celula[(sub,quarter)] = {prom, conv, det}
    # (Verbatim.tipo vem como 'promotor'/'conversivel'/'detrator'/'inativo'.)
    _TIPO_KEY = {"promotor": "prom", "conversivel": "conv", "detrator": "det"}
    celula: Dict[tuple, Dict[str, int]] = {}
    for sub, ano, mes, tipo, n in rows:
        try:
            qn = (int(mes) - 1) // 3 + 1
            q = f"{ano}-Q{qn}"
        except (TypeError, ValueError):
            continue
        if q not in quarters:
            continue
        chave = _TIPO_KEY.get(tipo)
        if chave is None:
            continue
        d = celula.setdefault((sub, q), {"prom": 0, "conv": 0, "det": 0})
        d[chave] += int(n or 0)

    # Matriz por subpilar (linha): celula por quarter + trend
    matriz = []
    for sub in SUBPILARES_ORDEM:
        celulas = []
        ratios = []
        for q in quarters:
            d = celula.get((sub, q))
            if not d or (d["prom"] + d["det"]) == 0:
                celulas.append(
                    SimpleNamespace(
                        quarter=q,
                        vazio=True,
                        ratio=None,
                        faixa=None,
                        prom=0,
                        conv=0,
                        det=0,
                        total=0,
                    )
                )
                ratios.append(None)
            else:
                r = calcular_ratio(d["prom"], d["det"])
                fx = faixa_ratio(r)
                total = d["prom"] + d["conv"] + d["det"]
                celulas.append(
                    SimpleNamespace(
                        quarter=q,
                        vazio=False,
                        ratio=r,
                        faixa=fx,
                        prom=d["prom"],
                        conv=d["conv"],
                        det=d["det"],
                        total=total,
                    )
                )
                ratios.append(r)
        # Trend: último vs penúltimo válido
        validos = [r for r in ratios if r is not None]
        trend = "→"
        delta_pct = None
        if len(validos) >= 2:
            d_pct = (validos[-1] - validos[-2]) / max(validos[-2], 0.01) * 100
            delta_pct = d_pct
            trend = "↑" if d_pct > 5 else ("↓" if d_pct < -5 else "→")
        if not validos:
            continue
        matriz.append(
            SimpleNamespace(
                subpilar=sub,
                nome=NOME_SUBPILAR.get(sub, sub),
                pilar=PILAR_DE_SUBPILAR.get(sub),
                celulas=celulas,
                trend=trend,
                delta_pct=delta_pct,
                ratio_atual=validos[-1],
                faixa_atual=faixa_ratio(validos[-1]),
            )
        )

    # ── Quebras estruturais (mudança de nível N entre quarters consecutivos)
    quebras = []
    for linha in matriz:
        for i in range(1, len(linha.celulas)):
            a, b = linha.celulas[i - 1], linha.celulas[i]
            if a.vazio or b.vazio:
                continue
            na, nb = _NIVEL.get(a.faixa, 0), _NIVEL.get(b.faixa, 0)
            if na and nb and na != nb:
                quebras.append(
                    SimpleNamespace(
                        subpilar=linha.subpilar,
                        nome=linha.nome,
                        pilar=linha.pilar,
                        de=b.quarter,
                        q_anterior=a.quarter,
                        nivel_anterior=a.faixa,
                        nivel_novo=b.faixa,
                        direcao=("piora" if nb < na else "melhora"),
                        ratio_anterior=a.ratio,
                        ratio_novo=b.ratio,
                    )
                )
    quebras.sort(key=lambda x: (x.direcao, x.de), reverse=True)

    # Índice geral por quarter (para CAPA + análise)
    indice_por_quarter = []
    for q in quarters:
        rs = [c.ratio for linha in matriz for c in linha.celulas if c.quarter == q and not c.vazio]
        media = round(sum(rs) / len(rs), 2) if rs else None
        n_verb = sum(
            (c.total for linha in matriz for c in linha.celulas if c.quarter == q and not c.vazio)
        )
        indice_por_quarter.append(SimpleNamespace(quarter=q, ratio_medio=media, n_verbatins=n_verb))

    # ── LLM: narrativa geral + por quarter (4 mais recentes) ───────────────
    payload = {
        "empresa": empresa_nome,
        "quarters": quarters,
        "indice_por_quarter": [
            {"quarter": x.quarter, "ratio_medio": x.ratio_medio, "n_verbatins": x.n_verbatins}
            for x in indice_por_quarter
        ],
        "matriz_evolucao": [
            {
                "subpilar": linha.subpilar,
                "nome": linha.nome,
                "trend": linha.trend,
                "delta_pct": linha.delta_pct,
                "ratio_atual": linha.ratio_atual,
                "faixa_atual": linha.faixa_atual,
                "celulas": [
                    {"q": c.quarter, "ratio": c.ratio, "faixa": c.faixa}
                    for c in linha.celulas
                    if not c.vazio
                ],
            }
            for linha in matriz
        ],
        "quebras_estruturais": [
            {
                "subpilar": q.subpilar,
                "nome": q.nome,
                "quarter": q.de,
                "de": q.nivel_anterior,
                "para": q.nivel_novo,
                "direcao": q.direcao,
            }
            for q in quebras[:10]
        ],
        "gargalo_atual": {"codigo": gargalo, "nome": gargalo_nome},
    }
    try:
        narrativa = gerar_narrativa_longitudinal(
            empresa_id, escopo_h, payload, gerar_fn=gerar_narrativa_fn
        )
    except Exception:
        narrativa = {
            "narrativa_geral": "Narrativa não disponível.",
            "por_quarter": [],
            "cached": False,
            "tokens_in": 0,
            "tokens_out": 0,
        }

    # ── Próximos Passos (assemblativos) ────────────────────────────────────
    proximos_passos = []
    for q in quebras[:5]:
        if q.direcao == "piora":
            proximos_passos.append(
                f"Investigar a piora de {q.subpilar} ({q.nome}) em {q.de}: "
                f"caiu de {q.nivel_anterior} para {q.nivel_novo} "
                f"(ratio {q.ratio_anterior:.2f} → {q.ratio_novo:.2f}). "
                f"O que mudou na operação nesse quarter?"
            )
    if gargalo_nome:
        proximos_passos.append(
            f"Sustentar plano para o pilar gargalo {gargalo} {gargalo_nome} — "
            f"persistente na maioria dos quarters analisados."
        )
    if not proximos_passos:
        proximos_passos.append(
            "Sem quebras estruturais ou pilar gargalo identificado — manter "
            "monitoramento dos próximos 2 quarters para detectar mudanças."
        )

    # ── CAPA · tese sobre evolução (assemblativa) ──────────────────────────
    ind_validos = [x for x in indice_por_quarter if x.ratio_medio is not None]
    if len(ind_validos) >= 2:
        delta_geral = ind_validos[-1].ratio_medio - ind_validos[0].ratio_medio
        direcao_geral = (
            "avançou" if delta_geral > 0.2 else "retrocedeu" if delta_geral < -0.2 else "estagnou"
        )
        capa_manchete = (
            f"Em {len(ind_validos)} quarters de observação, o índice médio "
            f"{direcao_geral} de {ind_validos[0].ratio_medio:.2f} "
            f"para {ind_validos[-1].ratio_medio:.2f}"
        )
    else:
        capa_manchete = (
            f"{len(matriz)} subpilares com histórico longitudinal sobre "
            f"{len(quarters)} quarters"
        )
    capa_soco = (
        f"{len(quebras)} quebras estruturais detectadas · "
        f"pilar gargalo persistente: {gargalo or '—'} "
        f"{gargalo_nome or ''}".strip()
    )

    return {
        "empresa_nome": empresa_nome,
        "gerado_em": datetime.utcnow(),
        "quarters": quarters,
        "matriz": matriz,
        "quebras": quebras,
        "indice_por_quarter": indice_por_quarter,
        "gargalo": gargalo,
        "gargalo_nome": gargalo_nome,
        "narrativa_geral": narrativa["narrativa_geral"],
        "por_quarter": narrativa["por_quarter"],
        "narrativa_cached": narrativa["cached"],
        "proximos_passos": proximos_passos,
        "capa_manchete": capa_manchete,
        "capa_soco": capa_soco,
        "tokens_in": narrativa["tokens_in"],
        "tokens_out": narrativa["tokens_out"],
        "custo_llm": round(
            narrativa["tokens_in"] / 1e6 * 3.0 + narrativa["tokens_out"] / 1e6 * 15.0, 4
        ),
    }
