"""Camada 1 — anomalia de indicador (loja × subpilar), portada do pdpa-v2.

Núcleo (validado em produção no v2): **cross-sectional z-robusto** — para
cada (subpilar, mês) calcula mediana+MAD do log(1+ratio) entre lojas da
empresa; a loja vira anômala quando está na **cauda inferior** (z negativo),
não na superior (loja boa não alerta). Calibração `(z_max−0.9)/1.5`.

Temporal: IsolationForest do **sklearn** (substitui o Merlion do v2) sobre a
série log(1+ratio) da loja — sinal secundário; cross-sectional é o primário.

``score_final = max(score_temporal, score_cross)`` em 0-100. Severidade 70/40.
Tendência editorial em 4 categorias (idêntico ao v2).

Lê de ``ratios_mensais`` (ver ``ratios.recomputar_ratios_mensais``).
"""

from __future__ import annotations

import math
import statistics
from typing import Any, Dict, List, Optional, Tuple

from src.api.painel import SUBPILARES_ORDEM

# ── Config (herdada do v2) ────────────────────────────────────────────
THRESHOLD_VERB_MES = 3
THRESHOLD_MESES = 6
SEVERIDADE_CRITICO = 70
SEVERIDADE_ATENCAO = 40
SUBPILARES = list(SUBPILARES_ORDEM)


def aplicar_transformacao(ratio: Optional[float]) -> float:
    return math.log1p(ratio) if ratio is not None else 0.0


def loja_elegivel(meses: int, total_verb: int) -> bool:
    if meses < THRESHOLD_MESES or meses == 0:
        return False
    return (total_verb / meses) >= THRESHOLD_VERB_MES


def _baselines(series_por_local: Dict[int, list]) -> Dict[Tuple[str, str], Dict[str, float]]:
    """Para cada (subpilar, periodo): mediana/MAD/media/std do log(ratio) entre
    lojas (só células com total>=3)."""
    grupos: Dict[Tuple[str, str], List[float]] = {}
    for _local_id, linhas in series_por_local.items():
        for r in linhas:
            if r["total"] < 3:
                continue
            grupos.setdefault((r["subpilar"], r["periodo"]), []).append(
                aplicar_transformacao(r["ratio"])
            )
    baselines: Dict[Tuple[str, str], Dict[str, float]] = {}
    for chave, vals in grupos.items():
        if len(vals) < 2:
            continue
        mediana = statistics.median(vals)
        mad = statistics.median(abs(v - mediana) for v in vals)
        baselines[chave] = {
            "mediana": mediana,
            "mad": mad,
            "media": statistics.fmean(vals),
            "std": statistics.pstdev(vals),
        }
    return baselines


def _score_cross_sectional(
    linhas_local: list, baselines: Dict[Tuple[str, str], Dict[str, float]]
) -> Tuple[float, Dict[str, float]]:
    """z-robusto da loja vs pares, cauda inferior. Returns (score_raw 0-1, {sp: z})."""
    z_por_sp: Dict[str, float] = {}
    for sp in SUBPILARES:
        sp_rows = sorted(
            [r for r in linhas_local if r["subpilar"] == sp and r["total"] >= 3],
            key=lambda r: r["periodo"],
        )
        if not sp_rows:
            continue
        z_recentes = []
        for r in sp_rows[-3:]:  # 3 meses recentes
            bl = baselines.get((sp, r["periodo"]))
            if not bl:
                continue
            log_val = aplicar_transformacao(r["ratio"])
            if bl["mad"] >= 0.1:
                z_signed = (log_val - bl["mediana"]) / (1.4826 * bl["mad"])
            elif bl["std"] >= 0.01:
                z_signed = (log_val - bl["media"]) / bl["std"]
            else:
                continue
            z_neg = max(0.0, -z_signed)  # só cauda inferior (loja ruim)
            z_recentes.append(min(5.0, z_neg))  # cap anti-ruído
        if z_recentes:
            z_por_sp[sp] = max(z_recentes)
    if not z_por_sp:
        return 0.0, {}
    z_max = max(z_por_sp.values())
    score_raw = max(0.0, min(1.0, (z_max - 0.9) / 1.5))
    return score_raw, z_por_sp


def _score_temporal(linhas_local: list) -> Dict[str, float]:
    """IsolationForest (sklearn) por subpilar sobre log(1+ratio).
    Returns {subpilar: score_raw 0-1 da anomalia do último ponto}."""
    import numpy as np
    from sklearn.ensemble import IsolationForest

    out: Dict[str, float] = {}
    for sp in SUBPILARES:
        sp_rows = sorted(
            [r for r in linhas_local if r["subpilar"] == sp], key=lambda r: r["periodo"]
        )
        if len(sp_rows) < 4:  # série curta → sem sinal temporal confiável
            continue
        x = np.array([[aplicar_transformacao(r["ratio"])] for r in sp_rows], dtype=float)
        try:
            clf = IsolationForest(n_estimators=64, random_state=42)
            clf.fit(x)
            # Gate: só há sinal temporal se o ÚLTIMO ponto for outlier de fato
            # (predict == -1). Sem o gate, em série curta o último mês quase
            # sempre vira "o mais anômalo" na normalização → falso positivo.
            if int(clf.predict(x)[-1]) != -1:
                continue
            raw = -clf.score_samples(x)  # maior = mais anômalo
            lo, hi = float(raw.min()), float(raw.max())
            out[sp] = (float(raw[-1]) - lo) / (hi - lo) if hi > lo else 0.0
        except Exception:  # noqa: BLE001
            continue
    return out


def _normalizar_temporal(score_raw: float) -> int:
    """0-1 relativo → 0-100. Só conta quando o último ponto destoa (>0.6)."""
    if score_raw < 0.6:
        return 0
    return min(100, int(40 + (score_raw - 0.6) * 150))


def _normalizar_cross(score_raw: float) -> int:
    return min(100, max(0, int(score_raw * 100)))


def _severidade(score: int) -> str:
    if score >= SEVERIDADE_CRITICO:
        return "critico"
    if score >= SEVERIDADE_ATENCAO:
        return "atencao"
    return "normal"


def _tendencia_editorial(score_temp: int, score_cross: int) -> str:
    temp = score_temp >= SEVERIDADE_ATENCAO
    cross = score_cross >= SEVERIDADE_ATENCAO
    # Rótulos em linguagem de negócio (sem jargão estatístico — alimentam a
    # leitura editorial, que proíbe termos como "outlier"/"eixos").
    if temp and cross:
        return "Crítico e em piora recente"
    if cross and not temp:
        return "Baixo persistente vs. lojas comparáveis"
    if temp and not cross:
        return "Em deterioração recente"
    return "Estável"


def detectar_indicadores(empresa_id: int) -> List[Dict[str, Any]]:
    """Detecta anomalias de indicador (loja×subpilar). Não persiste — devolve
    lista de dicts (severidade != normal). Persistência fica no combinador (CP-5).
    """
    from sqlalchemy import func

    from src.models.anomalia import RatioMensal
    from src.utils.db import db_session

    with db_session() as s:
        rows = (
            s.query(
                RatioMensal.local_id,
                RatioMensal.agrupamento_id,
                RatioMensal.subpilar,
                RatioMensal.periodo,
                RatioMensal.ratio,
                RatioMensal.total,
            )
            .filter(RatioMensal.empresa_id == empresa_id, RatioMensal.local_id.isnot(None))
            .all()
        )
        elegibilidade = (
            s.query(
                RatioMensal.local_id,
                func.count(func.distinct(RatioMensal.periodo)),
                func.sum(RatioMensal.total),
            )
            .filter(RatioMensal.empresa_id == empresa_id, RatioMensal.local_id.isnot(None))
            .group_by(RatioMensal.local_id)
            .all()
        )

    series_por_local: Dict[int, list] = {}
    ag_por_local: Dict[int, Optional[int]] = {}
    for local_id, ag_id, sub, periodo, ratio, total in rows:
        series_por_local.setdefault(local_id, []).append(
            {"subpilar": sub, "periodo": periodo, "ratio": ratio, "total": total}
        )
        ag_por_local[local_id] = ag_id

    elegiveis = {
        local_id
        for local_id, meses, verb in elegibilidade
        if loja_elegivel(int(meses or 0), int(verb or 0))
    }
    baselines = _baselines({lid: series_por_local[lid] for lid in elegiveis})

    anomalias: List[Dict[str, Any]] = []
    for local_id in elegiveis:
        linhas = series_por_local[local_id]
        cross_raw, z_por_sp = _score_cross_sectional(linhas, baselines)
        temp_por_sp = _score_temporal(linhas)
        score_cross = _normalizar_cross(cross_raw)
        score_temp = _normalizar_temporal(max(temp_por_sp.values()) if temp_por_sp else 0.0)
        score_final = max(score_cross, score_temp)
        sev = _severidade(score_final)
        # Calibração v3 (série mensal curta): o temporal (IForest) é sinal fraco
        # isolado. Crítico exige o cross-sectional (estrutural, validado no v2)
        # OU corroboração — temporal sozinho (cross < ATENCAO) cai p/ "atencao".
        # A Camada 2 (temas) poderá re-elevar via corroboração no combinador.
        if sev == "critico" and score_cross < SEVERIDADE_ATENCAO:
            sev = "atencao"
        if sev == "normal":
            continue
        pior_sp = max(z_por_sp, key=z_por_sp.get) if z_por_sp else None
        periodo_recente = max((r["periodo"] for r in linhas), default=None)
        anomalias.append(
            {
                "tipo": "indicador",
                "local_id": local_id,
                "agrupamento_id": ag_por_local.get(local_id),
                "subpilar": pior_sp,
                "score_temporal": float(score_temp),
                "score_cross_sectional": float(score_cross),
                "score_final": float(score_final),
                "magnitude": round(z_por_sp.get(pior_sp, 0.0), 3) if pior_sp else None,
                "direcao": "negativa",
                "severidade": sev,
                "tendencia": _tendencia_editorial(score_temp, score_cross),
                "periodo": periodo_recente,
                "chave": f"loja {local_id} · {pior_sp}" if pior_sp else f"loja {local_id}",
            }
        )
    anomalias.sort(key=lambda a: -a["score_final"])
    return anomalias
