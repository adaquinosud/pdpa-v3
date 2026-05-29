"""Helpers de cálculo e recálculo da Lente de Governança (Bloco LG / CP-LG-0).

A escala **Proximity** (0-100) é SEPARADA das faixas operacionais de ratio
(``src/api/painel.py:FAIXAS_RATIO``): ela mede distância da excelência
*consolidada* (ratio 9.0 = cap do sistema), não do piso da faixa "excelente".
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from src.utils.hashing import hash_payload

# Âncoras da escala Proximity (ver docs/BLOCO_LG.md):
#   ratio 0.5 (crítico)              → Proximity 0
#   ratio 9.0 (excelência/cap)       → Proximity 100
PROXIMITY_RATIO_PISO = 0.5
PROXIMITY_RATIO_TETO = 9.0

# Volume mínimo de verbatins por subpilar para Proximity ter lastro (decisão LG).
# Abaixo disso: proximity=None, faixa=None, excluído do peso e da média do pilar.
PROXIMITY_FLOOR_VERBATINS = 10

# Previsibilidade per-loja (CP-LG-2): floor por mês e piso de meses (espelha o
# eixo temporal de api/painel.calcular_previsibilidade, que usa >=3/mês e >=3 meses).
PREVISIB_FLOOR_VERBATINS_MES = 3
PREVISIB_MIN_MESES = 3


def calcular_proximity(ratio: Optional[float]) -> Optional[float]:
    """Proximity 0-100 a partir do ratio: ``(ratio-0.5)/(9.0-0.5)*100``, cap [0,100].

    ``None`` (sem dado suficiente — floor 10 verbatins) → ``None``. Calibração:
    0.5→0 · 2.0→~17.6 · 5.0→~52.9 · 9.0→100.
    """
    if ratio is None:
        return None
    span = PROXIMITY_RATIO_TETO - PROXIMITY_RATIO_PISO
    p = (ratio - PROXIMITY_RATIO_PISO) / span * 100.0
    return max(0.0, min(100.0, p))


def calcular_faixa_proximity(proximity: Optional[float]) -> Optional[str]:
    """Faixa da escala Proximity. Contrato (travado p/ a UI do LG-4):

    ``< 30`` → ``"distante"`` · ``30–60`` (>=30 e <=60) → ``"medio"`` · ``> 60`` →
    ``"proximo"``. Sem acento, casing exato. ``None`` → ``None``.
    """
    if proximity is None:
        return None
    if proximity < 30:
        return "distante"
    if proximity <= 60:
        return "medio"
    return "proximo"


def calcular_faixa_previsibilidade(previsibilidade: Optional[float]) -> Optional[str]:
    """Faixa da previsibilidade. Contrato (travado p/ a UI):

    ``< 40`` → ``"erratico"`` · ``40–70`` (>=40 e <=70) → ``"medio"`` · ``> 70`` →
    ``"estavel"``. Sem acento, casing exato. ``None`` → ``None``.
    """
    if previsibilidade is None:
        return None
    if previsibilidade < 40:
        return "erratico"
    if previsibilidade <= 70:
        return "medio"
    return "estavel"


def calcular_previsibilidade_loja(meses: Sequence[tuple]) -> Dict[str, Any]:
    """Previsibilidade (0-100) de uma loja pelo CV temporal dos ratios mensais.

    ``meses`` = sequência de ``(prom, det, total)`` por mês. Floor por mês
    (``total >= PREVISIB_FLOOR_VERBATINS_MES``) e piso de meses
    (``>= PREVISIB_MIN_MESES``); abaixo do piso → tudo ``None``.

    Régua **CV/2**, idêntica ao eixo temporal de
    ``api/painel.calcular_previsibilidade`` (evita divergência de sensibilidade
    entre as duas previsibilidades): ``previsib = (1 - min(CV/2, 1)) * 100``.

    ATENÇÃO (não é bug): com essa régua a faixa ``erratico`` (<40) só é
    alcançada com **CV > 1.2**. Alternância suave (ex.: ratios 0.3↔9.0 mês a mês)
    dá CV ≈ 1.08 → ``medio`` (~46); 2 valores alternados têm CV máximo ~1.155.
    ``erratico`` exige assimetria forte (ex.: 2 meses ~0 e 1 mês alto). Ver os
    testes-sentinela em ``tests/test_governanca.py``.
    """
    import statistics

    from src.api.painel import calcular_ratio

    ratios = [calcular_ratio(p, d) for (p, d, t) in meses if t >= PREVISIB_FLOOR_VERBATINS_MES]
    n = len(ratios)
    if n < PREVISIB_MIN_MESES:
        return {"previsibilidade": None, "faixa": None, "cv": None, "n_meses": n}
    media = statistics.mean(ratios)
    cv = statistics.stdev(ratios) / max(media, 0.01)
    score = round(max(0.0, min(100.0, (1 - min(cv / 2.0, 1.0)) * 100)), 1)
    return {
        "previsibilidade": score,
        "faixa": calcular_faixa_previsibilidade(score),
        "cv": round(cv, 4),
        "n_meses": n,
    }


def calcular_gini(distribuicao: Sequence[float]) -> Optional[float]:
    """Coeficiente de Gini formal de ``distribuicao`` (0 = distribuído, →1 = concentrado).

    ``distribuicao`` = valores não-negativos (ex.: nº de detratores por loja).
    Retorna ``None`` se vazia ou soma zero (nada a concentrar). Fórmula com
    valores ordenados crescente (1-based ``i``):
    ``G = 2·Σ(i·x_i)/(n·Σx) − (n+1)/n``.
    """
    vals = sorted(float(v) for v in distribuicao)
    n = len(vals)
    if n == 0:
        return None
    total = sum(vals)
    if total <= 0:
        return None
    cum = sum((i + 1) * v for i, v in enumerate(vals))
    gini = (2.0 * cum) / (n * total) - (n + 1.0) / n
    return max(0.0, min(1.0, gini))


# Concentração / Gini (CP-LG-3).
GINI_MIN_LOJAS = 5  # < 5 lojas medidas → Gini indisponível (igual à concentração %)
GINI_BOLSAO_SHARE = 0.5  # bolsão crítico = menor conjunto que soma ≥ 50% dos detratores


def gini_corrigido(g: Optional[float], n: Optional[int]) -> Optional[float]:
    """Correção de viés-por-n do Gini: ``G · n/(n-1)``, cap 1.0.

    O Gini bruto tem teto ``(n-1)/n`` (0.8 p/ n=5, ~0.98 p/ n=47), o que tornaria
    as faixas incomparáveis entre escopos de tamanhos diferentes. A correção
    normaliza o teto para 1.0 em qualquer ``n`` — usada SÓ para classificar a
    faixa; o ``gini`` bruto (de ``calcular_gini``) é o que fica na coluna."""
    if g is None or n is None or n < 2:
        return g
    return min(1.0, g * n / (n - 1))


def faixa_gini(gini_corr: Optional[float]) -> Optional[str]:
    """Faixa da concentração (sobre o Gini CORRIGIDO). Contrato p/ UI:
    ``< 0.4`` → ``"baixa"`` (distribuído) · ``0.4–0.6`` → ``"media"`` · ``> 0.6`` →
    ``"alta"`` (concentrado). ``None`` → ``None``."""
    if gini_corr is None:
        return None
    if gini_corr < 0.4:
        return "baixa"
    if gini_corr <= 0.6:
        return "media"
    return "alta"


def _arred(x: Optional[float]) -> Optional[float]:
    return None if x is None else round(x, 2)


def linhas_proximity_escopo(agg: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Constrói as linhas de Proximity (convenção de grão) a partir do ``agg`` de
    um escopo (saída de ``agregar_subpilares``).

    - **subpilar-level:** uma por subpilar presente. ``proximity`` só se
      ``total >= floor``, senão ``None`` (mas a linha existe — "sem dado").
    - **pilar-level:** uma por pilar com ≥1 subpilar presente. Média ponderada por
      ``total`` dos subpilares com proximity não-NULL; ``None`` se nenhum qualifica.
    - **agregada (subpilar=NULL, pilar=NULL):** ``min(proximity_pilar não-NULL)`` —
      respeita o Lastro; ``None`` se nenhum pilar qualifica.
    """
    from src.api.painel import PILAR_DE_SUBPILAR, PILARES_ORDEM, SUBPILARES_ORDEM

    linhas: List[Dict[str, Any]] = []
    pilar_presente: set = set()
    pilar_membros: Dict[str, List[tuple]] = {}  # pilar -> [(proximity, peso)]

    for sub in SUBPILARES_ORDEM:
        if sub not in agg:
            continue
        d = agg[sub]
        pil = PILAR_DE_SUBPILAR.get(sub)
        if pil:
            pilar_presente.add(pil)
        if d["total"] >= PROXIMITY_FLOOR_VERBATINS:
            p = calcular_proximity(d["ratio"])
        else:
            p = None  # floor: sem dado suficiente
        pa = _arred(p)
        linhas.append(
            {"subpilar": sub, "pilar": None, "proximity": pa, "faixa": calcular_faixa_proximity(pa)}
        )
        if p is not None and pil:
            pilar_membros.setdefault(pil, []).append((p, d["total"]))

    pilar_prox: Dict[str, Optional[float]] = {}
    for pil in PILARES_ORDEM:
        if pil not in pilar_presente:
            continue
        membros = pilar_membros.get(pil, [])
        if membros:
            peso = sum(w for _, w in membros)
            pp = sum(p * w for p, w in membros) / peso
        else:
            pp = None
        pilar_prox[pil] = pp
        ppa = _arred(pp)
        linhas.append(
            {
                "subpilar": None,
                "pilar": pil,
                "proximity": ppa,
                "faixa": calcular_faixa_proximity(ppa),
            }
        )

    validos = [pp for pp in pilar_prox.values() if pp is not None]
    agg_prox = _arred(min(validos)) if validos else None
    linhas.append(
        {
            "subpilar": None,
            "pilar": None,
            "proximity": agg_prox,
            "faixa": calcular_faixa_proximity(agg_prox),
        }
    )
    return linhas


def _hash_escopo(agg: Dict[str, Dict[str, Any]]) -> str:
    """Hash do que determina Proximity num escopo: (prom, det, total) por subpilar.
    sem_lastro/None:None ficam fora do ``agg`` — não afetam Proximity, logo não
    entram no hash (mudança neles → skip correto)."""
    return hash_payload(
        {sub: [agg[sub]["prom"], agg[sub]["det"], agg[sub]["total"]] for sub in sorted(agg)}
    )


def recalcular_previsibilidade(empresa_id: int, *, skip_unchanged: bool = True) -> Dict[str, int]:
    """Recalcula Previsibilidade per-loja (CV temporal dos ``ratios_mensais``) e
    persiste em ``previsibilidade_calculations``.

    Fonte: ``ratios_mensais`` (recomputada no passo 7, logo antes). Por loja,
    agrego os subpilares de cada mês (Σprom/Σdet/Σtotal) → série mensal → CV.
    Mesma mecânica do LG-1: delete-then-insert por loja + skip por hash da série.
    """
    from sqlalchemy import and_, func

    from src.models.anomalia import RatioMensal
    from src.models.governanca import PrevisibilidadeCalculation
    from src.models.local import Local
    from src.utils.db import db_session

    recalc = 0
    pulados = 0
    with db_session() as s:
        for loc in s.query(Local).filter_by(empresa_id=empresa_id).all():
            rows = (
                s.query(
                    RatioMensal.periodo,
                    func.sum(RatioMensal.promotor),
                    func.sum(RatioMensal.detrator),
                    func.sum(RatioMensal.total),
                )
                .filter(RatioMensal.empresa_id == empresa_id, RatioMensal.local_id == loc.id)
                .group_by(RatioMensal.periodo)
                .all()
            )
            meses = [(int(p or 0), int(d or 0), int(t or 0)) for (_per, p, d, t) in rows]
            serie = sorted(
                [(per, int(p or 0), int(d or 0), int(t or 0)) for (per, p, d, t) in rows]
            )
            h = hash_payload(serie)
            base = and_(
                PrevisibilidadeCalculation.empresa_id == empresa_id,
                PrevisibilidadeCalculation.escopo_tipo == "loja",
                PrevisibilidadeCalculation.escopo_id == loc.id,
            )
            if skip_unchanged:
                atual = s.query(PrevisibilidadeCalculation.dados_hash).filter(base).first()
                if atual and atual[0] == h:
                    pulados += 1
                    continue
            res = calcular_previsibilidade_loja(meses)
            s.query(PrevisibilidadeCalculation).filter(base).delete(synchronize_session=False)
            s.add(
                PrevisibilidadeCalculation(
                    empresa_id=empresa_id,
                    escopo_tipo="loja",
                    escopo_id=loc.id,
                    previsibilidade_0_100=res["previsibilidade"],
                    faixa=res["faixa"],
                    n_meses=res["n_meses"],
                    cv=res["cv"],
                    dados_hash=h,
                )
            )
            recalc += 1
        s.commit()
    return {"previsib_escopos": recalc, "previsib_pulados": pulados}


def recalcular_gini(empresa_id: int, *, skip_unchanged: bool = True) -> Dict[str, int]:
    """Recalcula a Concentração de Detratores (Gini) por escopo (empresa + cada
    agrupamento) e persiste em ``gini_concentracao``.

    Distribuição = nº de detratores por loja MEDIDA (≥1 verbatim) no escopo,
    histórico completo. ``gini`` (coluna) = Gini bruto; ``distribuicao_json``
    guarda ``gini_bruto`` + ``gini_corrigido`` (viés-por-n) + ``faixa`` + bolsão
    (top_n a ≥50% dos detratores) + todas as lojas medidas ordenadas (p/ as
    barras). Indisponível (NULL) se < 5 lojas medidas ou 0 detratores.
    Delete-then-insert por escopo + skip por hash da distribuição.
    """
    import json as _json

    from sqlalchemy import and_, func

    from src.models.agrupamento import Agrupamento
    from src.models.governanca import GiniConcentracao
    from src.models.local import Local
    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    recalc = 0
    pulados = 0
    with db_session() as s:
        nomes = {loc.id: loc.nome for loc in s.query(Local).filter_by(empresa_id=empresa_id).all()}
        escopos = [("empresa", None, None)]
        for ag in s.query(Agrupamento).filter_by(empresa_id=empresa_id).all():
            escopos.append(("agrupamento", ag.id, ag.id))

        for escopo_tipo, escopo_id, ag_id in escopos:
            q = (
                s.query(Verbatim.local_id, Verbatim.tipo, func.count(Verbatim.id))
                .filter(Verbatim.empresa_id == empresa_id, Verbatim.local_id.isnot(None))
                .group_by(Verbatim.local_id, Verbatim.tipo)
            )
            if ag_id is not None:
                locais_ag = [
                    lid
                    for (lid,) in s.query(Local.id)
                    .filter_by(empresa_id=empresa_id, agrupamento_id=ag_id)
                    .all()
                ]
                q = q.filter(Verbatim.local_id.in_(locais_ag or [-1]))
            por_loja: Dict[int, Dict[str, int]] = {}
            for lid, tipo, n in q.all():
                d = por_loja.setdefault(lid, {"det": 0, "total": 0})
                d["total"] += int(n)
                if tipo == "detrator":
                    d["det"] += int(n)
            medidas = {lid: d for lid, d in por_loja.items() if d["total"] >= 1}
            n_lojas = len(medidas)
            total_det = sum(d["det"] for d in medidas.values())

            h = hash_payload(sorted((lid, d["det"]) for lid, d in medidas.items()))
            cond = (
                GiniConcentracao.escopo_id.is_(None)
                if escopo_id is None
                else (GiniConcentracao.escopo_id == escopo_id)
            )
            base = and_(
                GiniConcentracao.empresa_id == empresa_id,
                GiniConcentracao.escopo_tipo == escopo_tipo,
                cond,
            )
            if skip_unchanged:
                atual = s.query(GiniConcentracao.dados_hash).filter(base).first()
                if atual and atual[0] == h:
                    pulados += 1
                    continue

            g_raw = None
            top_n = None
            if n_lojas < GINI_MIN_LOJAS or total_det == 0:
                dj = {
                    "total_lojas": n_lojas,
                    "total_detratores": total_det,
                    "insuficiente": True,
                    "motivo": "poucas_lojas" if n_lojas < GINI_MIN_LOJAS else "sem_detratores",
                    "lojas": [],
                }
            else:
                g_raw = calcular_gini([d["det"] for d in medidas.values()])
                g_corr = gini_corrigido(g_raw, n_lojas)
                faixa = faixa_gini(g_corr)
                ordenadas = sorted(medidas.items(), key=lambda kv: -kv[1]["det"])
                lojas_json = [
                    {
                        "local_id": lid,
                        "nome": nomes.get(lid, f"loja {lid}"),
                        "detratores": d["det"],
                        "share": round(d["det"] / total_det, 4),
                    }
                    for lid, d in ordenadas
                ]
                acc = 0
                top_n = 0
                for _lid, d in ordenadas:
                    acc += d["det"]
                    top_n += 1
                    if acc / total_det >= GINI_BOLSAO_SHARE:
                        break
                dj = {
                    "total_lojas": n_lojas,
                    "total_detratores": total_det,
                    "top_n": top_n,
                    "share": round(acc / total_det, 4),
                    "gini_bruto": round(g_raw, 4),
                    "gini_corrigido": round(g_corr, 4),
                    "faixa": faixa,
                    "lojas": lojas_json,
                }

            s.query(GiniConcentracao).filter(base).delete(synchronize_session=False)
            s.add(
                GiniConcentracao(
                    empresa_id=empresa_id,
                    escopo_tipo=escopo_tipo,
                    escopo_id=escopo_id,
                    gini=(round(g_raw, 4) if g_raw is not None else None),
                    top_n_lojas=top_n,
                    distribuicao_json=_json.dumps(dj, ensure_ascii=False),
                    dados_hash=h,
                )
            )
            recalc += 1
        s.commit()
    return {"gini_escopos": recalc, "gini_pulados": pulados}


def recalcular_governanca(empresa_id: int, *, skip_unchanged: bool = True) -> Dict[str, int]:
    """Recalcula as métricas de governança de uma empresa (passo 7.5 do pós-coleta).

    - **Proximity** por escopo (empresa, cada agrupamento, cada loja) em
      ``proximity_calculations`` — delete-then-insert por escopo + skip por hash.
    - **Previsibilidade** per-loja em ``previsibilidade_calculations`` (CP-LG-2).
    - **Gini** (Concentração) por escopo em ``gini_concentracao`` (CP-LG-3).
    """
    from sqlalchemy import and_

    from src.diagnostico.leituras import agregar_subpilares
    from src.models.agrupamento import Agrupamento
    from src.models.governanca import ProximityCalculation
    from src.models.local import Local
    from src.utils.db import db_session

    def _cond_escopo_id(escopo_id):
        col = ProximityCalculation.escopo_id
        return col.is_(None) if escopo_id is None else (col == escopo_id)

    recalc = 0
    pulados = 0
    with db_session() as s:
        # (escopo_tipo, escopo_id, ag_id p/ agregar, local_id p/ agregar)
        escopos = [("empresa", None, None, None)]
        for ag in s.query(Agrupamento).filter_by(empresa_id=empresa_id).all():
            escopos.append(("agrupamento", ag.id, ag.id, None))
        for loc in s.query(Local).filter_by(empresa_id=empresa_id).all():
            escopos.append(("loja", loc.id, None, loc.id))

        for escopo_tipo, escopo_id, ag_id, local_id in escopos:
            agg = agregar_subpilares(s, empresa_id, ag_id, local_id)
            h = _hash_escopo(agg)
            base = and_(
                ProximityCalculation.empresa_id == empresa_id,
                ProximityCalculation.escopo_tipo == escopo_tipo,
                _cond_escopo_id(escopo_id),
            )
            if skip_unchanged:
                atual = s.query(ProximityCalculation.dados_hash).filter(base).first()
                if atual and atual[0] == h:
                    pulados += 1
                    continue
            s.query(ProximityCalculation).filter(base).delete(synchronize_session=False)
            for ln in linhas_proximity_escopo(agg):
                s.add(
                    ProximityCalculation(
                        empresa_id=empresa_id,
                        escopo_tipo=escopo_tipo,
                        escopo_id=escopo_id,
                        subpilar=ln["subpilar"],
                        pilar=ln["pilar"],
                        proximity_0_100=ln["proximity"],
                        faixa=ln["faixa"],
                        dados_hash=h,
                    )
                )
            recalc += 1
        s.commit()

    # Previsibilidade + Gini (sequenciais à Proximity — sessões não aninhadas).
    prev = recalcular_previsibilidade(empresa_id, skip_unchanged=skip_unchanged)
    gini = recalcular_gini(empresa_id, skip_unchanged=skip_unchanged)
    return {
        "proximity_escopos": recalc,
        "proximity_pulados": pulados,
        "previsib_escopos": prev["previsib_escopos"],
        "previsib_pulados": prev["previsib_pulados"],
        "gini_escopos": gini["gini_escopos"],
        "gini_pulados": gini["gini_pulados"],
    }
