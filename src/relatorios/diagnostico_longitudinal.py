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

from src.api.engajamento import VOLUME_CONFIANCA_ALTA
from src.utils.fmt import acento


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

# Piso de volume para uma quebra virar PRÓXIMO PASSO impresso: o menor dos dois trimestres tem
# de ter ao menos isto (decisão de 12/11). Célula de trimestre é fatia, não leitura acumulada:
# com o piso 30 de pouca base (selo, tela, gargalo, regra dos prompts), o longitudinal da Carbel
# só falaria do Pa1, que vive no teto. Constante própria de propósito — não é a do engajamento,
# para ninguém mexer numa achando que mexe na outra. O PDF declara este piso ao lado do 30.
PISO_PASSO_TRIMESTRE = 10


def _no_teto(ratio: Optional[float]) -> bool:
    """Ratio no teto da régua (caminho A, sem detrator, ou B, divisão cortada)."""
    from src.api.painel import RATIO_CAP_SUPERIOR

    return ratio is not None and ratio >= RATIO_CAP_SUPERIOR


def _teto_do_lado(c) -> str:
    return "sem detrator" if c.det == 0 else "acima do teto da régua"


def _celula_payload(c) -> Dict[str, Any]:
    """Célula como vai ao modelo: contagens junto do ratio; no teto, o ratio não vai (o modelo
    não pode comparar 9,99 com um ratio real) e vai o fato no lugar."""
    d = {
        "q": c.quarter,
        "ratio": c.ratio,
        "faixa": c.faixa,
        "prom": c.prom,
        "conv": c.conv,
        "det": c.det,
        "total": c.total,
    }
    if _no_teto(c.ratio):
        d["ratio"] = None
        d["teto"] = _teto_do_lado(c)
    return d


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
    from src.utils.sql import fmt_ano, fmt_mes
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
                fmt_ano(Verbatim.data_criacao_original).label("ano"),
                fmt_mes(Verbatim.data_criacao_original).label("mes"),
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
        # Trend: último vs penúltimo válido. Com um dos dois no teto não há variação a medir
        # (9,99 é corte, não medida): trend e delta ficam None, e o PDF e o pacote dizem isso.
        validos = [r for r in ratios if r is not None]
        trend = "→"
        delta_pct = None
        if len(validos) >= 2:
            if _no_teto(validos[-1]) or _no_teto(validos[-2]):
                trend = None
            else:
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
                celula_atual=[c for c in celulas if not c.vazio][-1],
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
                        # contagens dos dois lados, só p/ exibição ("sem detrator", "pouca base")
                        prom_anterior=a.prom,
                        det_anterior=a.det,
                        total_anterior=a.total,
                        prom_novo=b.prom,
                        det_novo=b.det,
                        total_novo=b.total,
                    )
                )
    quebras.sort(key=lambda x: (x.direcao, x.de), reverse=True)

    # Volume por quarter (capa). Não há "índice médio": a média simples de ratios com teto saiu
    # de circulação (item 17, 12/11) — da capa, da lista da capa e do pacote da narrativa.
    volume_por_quarter = []
    for q in quarters:
        n_verb = sum(
            (c.total for linha in matriz for c in linha.celulas if c.quarter == q and not c.vazio)
        )
        volume_por_quarter.append(SimpleNamespace(quarter=q, n_verbatins=n_verb))

    # ── LLM: narrativa geral + por quarter (4 mais recentes) ───────────────
    payload = {
        "empresa": empresa_nome,
        "quarters": quarters,
        "volume_por_quarter": [
            {"quarter": x.quarter, "n_verbatins": x.n_verbatins} for x in volume_por_quarter
        ],
        "matriz_evolucao": [
            {
                "subpilar": linha.subpilar,
                "nome": linha.nome,
                "trend": linha.trend,
                "delta_pct": linha.delta_pct,
                **(
                    {"variacao": "sem variação a medir: um dos dois trimestres está no teto"}
                    if linha.trend is None
                    else {}
                ),
                "ratio_atual": (None if _no_teto(linha.ratio_atual) else linha.ratio_atual),
                **(
                    {"teto_atual": _teto_do_lado(linha.celula_atual)}
                    if _no_teto(linha.ratio_atual)
                    else {}
                ),
                "faixa_atual": linha.faixa_atual,
                "celulas": [_celula_payload(c) for c in linha.celulas if not c.vazio],
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
                "anterior": {
                    "prom": q.prom_anterior,
                    "det": q.det_anterior,
                    "total": q.total_anterior,
                },
                "novo": {"prom": q.prom_novo, "det": q.det_novo, "total": q.total_novo},
                **(
                    {"lado_no_teto": True}
                    if _no_teto(q.ratio_anterior) or _no_teto(q.ratio_novo)
                    else {}
                ),
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
    # Só vira passo a quebra com base nos DOIS trimestres (piso antes do corte de 5, senão o
    # piso só esvazia a lista). O texto diz as contagens, não o ratio: um lado pode estar no teto.
    proximos_passos = []
    elegiveis = [q for q in quebras if min(q.total_anterior, q.total_novo) >= PISO_PASSO_TRIMESTRE]
    for q in elegiveis[:5]:
        if q.direcao == "piora":
            proximos_passos.append(
                f"Investigar a piora de {q.subpilar} ({q.nome}) em {q.de}: "
                f"caiu de {acento(q.nivel_anterior).lower()} para {acento(q.nivel_novo).lower()} "
                f"(de {q.total_anterior} relatos com {q.det_anterior} críticas "
                f"para {q.total_novo} com {q.det_novo}). "
                f"O que mudou na operação nesse quarter?"
            )
    if not proximos_passos and any(q.direcao == "piora" for q in quebras):
        proximos_passos.append(
            f"Nenhuma piora com ao menos {PISO_PASSO_TRIMESTRE} relatos nos dois trimestres: "
            "as quebras ficam na tabela acima, sem virar investigação."
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
    capa_manchete = (
        f"{len(matriz)} subpilares com histórico longitudinal sobre {len(quarters)} quarters"
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
        "volume_por_quarter": volume_por_quarter,
        "piso_passo": PISO_PASSO_TRIMESTRE,
        "piso_pouca_base": VOLUME_CONFIANCA_ALTA,
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
