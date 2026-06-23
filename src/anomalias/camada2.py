"""Camada 2 — anomalia em temas/cruzamentos (Monitoramento ML CP-4).

Genuinamente nova no v3 (o v2 não tinha temas). Três sinais:

1. **Trend de tema** (≥3 meses): volume do mês N vs média(N-1, N-2). Dispara
   se |variação| > 50% OU |Δ absoluto| > 5 menções. Trend desligada se < 3 meses.
2. **Emergência / sumiço** (diff de snapshots): tema com slug novo vs o snapshot
   anterior → emergência; slug que sumiu (tinha volume) → resolução provável.
3. **Cruzamento** novo ou com Δpeso relevante (diff de snapshots de cruzamento).

Anti-relabeling (o maior risco): a identidade é o **slug**; quando o slug é novo,
faz fallback **fuzzy por cosine de centróides ≥ 0.85** contra os temas do snapshot
anterior — só é "novo" se slug E cosine falharem (senão é re-rotulagem do LLM).

Snapshots (``temas_snapshot``/``cruzamentos_snapshot``) são gravados a cada
rodada (período = mês da última coleta). Emergência/sumiço só ativam com ≥2
snapshots; o trend já funciona com o histórico de datas dos verbatins.
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional

import numpy as np

FUZZY_COSINE = 0.85
TREND_MIN_MESES = 3
TREND_VAR_PCT = 0.5  # 50%
TREND_MIN_VOL_DEFAULT = 3  # piso de menções no mês corrente (env PDPA_TREND_MIN_VOL)
TREND_MIN_DELTA_DEFAULT = 5  # Δ absoluto mínimo p/ disparar (env PDPA_TREND_MIN_DELTA)


def _min_vol() -> int:
    """Piso de volume mensal p/ o trend disparar — filtra micro-temas (1-2
    menções). Lido em runtime p/ permitir override por ambiente/teste."""
    return int(os.getenv("PDPA_TREND_MIN_VOL", str(TREND_MIN_VOL_DEFAULT)))


def _min_delta() -> int:
    return int(os.getenv("PDPA_TREND_MIN_DELTA", str(TREND_MIN_DELTA_DEFAULT)))


def _score_trend(delta: float, var: float) -> float:
    """Score 0-100 que reflete a magnitude (Δ absoluto, raiz p/ espalhar a
    cauda) + um bônus de variação proporcional. Não satura todo mundo em 100:
    o grande movimento domina, os pequenos ficam baixos."""
    mag = min(80.0, 9.0 * math.sqrt(abs(delta)))  # Δ=80→80, Δ=5→20, Δ=2→12.7
    var_bonus = min(20.0, 10.0 * abs(var))  # var=2.0→20, var=0.5→5
    return round(mag + var_bonus, 1)


def periodo_atual(empresa_id: int, s=None) -> str:
    """'YYYY-MM' da última coleta da empresa (fallback: mês corrente)."""
    from datetime import datetime

    from sqlalchemy import func

    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    def _calc(sess) -> str:
        ultima = (
            sess.query(func.max(Verbatim.data_coleta))
            .filter(Verbatim.empresa_id == empresa_id)
            .scalar()
        )
        d = ultima or datetime.utcnow()
        return d.strftime("%Y-%m")

    if s is not None:
        return _calc(s)
    with db_session() as sess:
        return _calc(sess)


def _slug_agregado(empresa_id: int, s) -> Dict[str, Dict[str, Any]]:
    """Estado atual por slug: label, volume total, split por tipo, por agrupamento."""
    from sqlalchemy import func

    from src.temas.cobertura import temas_volume_live_subq
    from src.temas.slug import slugify

    # Régua live (= telas): a subquery já filtra tema ATIVO e dá tema_label.
    _tc = temas_volume_live_subq(s)
    rows = (
        s.query(
            _tc.c.tema_label,
            _tc.c.agrupamento_id,
            _tc.c.tipo,
            func.sum(_tc.c.volume),
        )
        .filter(_tc.c.empresa_id == empresa_id)
        .group_by(_tc.c.tema_label, _tc.c.agrupamento_id, _tc.c.tipo)
        .all()
    )
    out: Dict[str, Dict[str, Any]] = {}
    for nome, ag_id, tipo, vol in rows:
        slug = slugify(nome)
        e = out.setdefault(
            slug,
            {
                "label": nome,
                "total": 0,
                "promotor": 0,
                "conversivel": 0,
                "detrator": 0,
                "por_ag": {},
            },
        )
        v = int(vol or 0)
        e["total"] += v
        if tipo in ("promotor", "conversivel", "detrator"):
            e[tipo] += v
        e["por_ag"][ag_id] = e["por_ag"].get(ag_id, 0) + v
    return out


def snapshot_temas(empresa_id: int, periodo: Optional[str] = None) -> int:
    """Grava a foto atual dos temas (idempotente por período). Linha company-wide
    (agrupamento NULL) carrega o centróide; linhas por agrupamento, só volume."""
    from src.models.anomalia import TemaSnapshot
    from src.temas.cruzamento import _carregar_temas_centroides
    from src.temas.slug import slugify
    from src.utils.db import db_session

    centroides_por_slug: Dict[str, bytes] = {}
    info = _carregar_temas_centroides(empresa_id)
    for tid, e in info.items():
        if "centroide" in e:
            centroides_por_slug[slugify(e["nome"])] = np.asarray(
                e["centroide"], dtype=np.float32
            ).tobytes()

    with db_session() as s:
        per = periodo or periodo_atual(empresa_id, s)
        agg = _slug_agregado(empresa_id, s)
        s.query(TemaSnapshot).filter(
            TemaSnapshot.empresa_id == empresa_id, TemaSnapshot.periodo == per
        ).delete(synchronize_session=False)
        n = 0
        for slug, e in agg.items():
            s.add(
                TemaSnapshot(
                    empresa_id=empresa_id,
                    periodo=per,
                    tema_slug=slug,
                    tema_label=e["label"],
                    agrupamento_id=None,
                    volume=e["total"],
                    promotor=e["promotor"],
                    conversivel=e["conversivel"],
                    detrator=e["detrator"],
                    centroide=centroides_por_slug.get(slug),
                )
            )
            n += 1
            for ag_id, vol in e["por_ag"].items():
                if ag_id is None:
                    continue
                s.add(
                    TemaSnapshot(
                        empresa_id=empresa_id,
                        periodo=per,
                        tema_slug=slug,
                        tema_label=e["label"],
                        agrupamento_id=ag_id,
                        volume=vol,
                    )
                )
                n += 1
    return n


def snapshot_cruzamentos(empresa_id: int, periodo: Optional[str] = None) -> int:
    from src.models.anomalia import CruzamentoSnapshot
    from src.models.temas import TemaCruzamento
    from src.temas.slug import slugify
    from src.utils.db import db_session

    with db_session() as s:
        per = periodo or periodo_atual(empresa_id, s)
        s.query(CruzamentoSnapshot).filter(
            CruzamentoSnapshot.empresa_id == empresa_id, CruzamentoSnapshot.periodo == per
        ).delete(synchronize_session=False)
        n = 0
        for cr in s.query(TemaCruzamento).filter(TemaCruzamento.empresa_id == empresa_id).all():
            s.add(
                CruzamentoSnapshot(
                    empresa_id=empresa_id,
                    periodo=per,
                    tema_label=cr.tema_label,
                    tema_slug=slugify(cr.tema_label),
                    membros_json=cr.membros_json,
                    buckets_envolvidos_json=cr.buckets_envolvidos_json,
                    tipos_envolvidos_json=cr.tipos_envolvidos_json,
                    n_subpilares_distintos=cr.n_subpilares_distintos,
                    peso=cr.peso,
                    eh_semantico=bool(cr.membros_json),
                )
            )
            n += 1
    return n


def _periodo_anterior(empresa_id: int, atual: str, s) -> Optional[str]:
    from src.models.anomalia import TemaSnapshot

    pers = [
        p[0]
        for p in s.query(TemaSnapshot.periodo)
        .filter(TemaSnapshot.empresa_id == empresa_id, TemaSnapshot.periodo < atual)
        .distinct()
        .all()
    ]
    return max(pers) if pers else None


def _fuzzy_relabel(centroide_novo: Optional[bytes], anteriores: List[bytes]) -> bool:
    """True se o tema 'novo' casa por cosine ≥ 0.85 com algum anterior (= re-rotulagem)."""
    if not centroide_novo or not anteriores:
        return False
    v = np.frombuffer(centroide_novo, dtype=np.float32)
    nv = np.linalg.norm(v)
    if nv == 0:
        return False
    v = v / nv
    for b in anteriores:
        u = np.frombuffer(b, dtype=np.float32)
        nu = np.linalg.norm(u)
        if nu == 0 or u.shape != v.shape:
            continue
        if float(v @ (u / nu)) >= FUZZY_COSINE:
            return True
    return False


def _detectar_trend(empresa_id: int, s) -> List[Dict[str, Any]]:
    """Volume mês a mês por tema; dispara no mês mais recente vs média dos 2
    anteriores. Direção pela predominância detrator do tema."""
    from sqlalchemy import func

    from src.models.temas import Tema, VerbatimTema
    from src.models.verbatim import Verbatim
    from src.utils.sql import fmt_ano_mes

    mes_col = fmt_ano_mes(Verbatim.data_criacao_original)
    rows = (
        s.query(
            Tema.id,
            Tema.nome,
            mes_col,
            Verbatim.tipo,
            func.count(VerbatimTema.id),
        )
        .join(VerbatimTema, VerbatimTema.tema_id == Tema.id)
        .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
        .filter(
            Tema.empresa_id == empresa_id,
            Tema.ativo.is_(True),
            VerbatimTema.bucket_chave.isnot(None),
            Verbatim.data_criacao_original.isnot(None),
        )
        .group_by(Tema.id, mes_col, Verbatim.tipo)
        .all()
    )
    por_tema: Dict[int, Dict[str, Any]] = {}
    for tid, nome, mes, tipo, n in rows:
        e = por_tema.setdefault(tid, {"nome": nome, "meses": {}, "detr": 0, "prom": 0})
        e["meses"][mes] = e["meses"].get(mes, 0) + int(n)
        if tipo == "detrator":
            e["detr"] += int(n)
        elif tipo == "promotor":
            e["prom"] += int(n)

    min_vol, min_delta = _min_vol(), _min_delta()
    anomalias: List[Dict[str, Any]] = []
    for tid, e in por_tema.items():
        meses_ord = sorted(e["meses"])
        if len(meses_ord) < TREND_MIN_MESES:
            continue
        n_atual = e["meses"][meses_ord[-1]]
        if n_atual < min_vol:  # micro-tema (1-2 menções) é ruído, não sinal
            continue
        base = [e["meses"][m] for m in meses_ord[-3:-1]]
        media = sum(base) / len(base) if base else 0.0
        delta = n_atual - media
        var = (delta / media) if media > 0 else (1.0 if delta > 0 else 0.0)
        if abs(var) < TREND_VAR_PCT and abs(delta) < min_delta:
            continue
        detrator_heavy = e["detr"] >= e["prom"]
        # problema = tema detrator crescendo; resolução = detrator encolhendo.
        # crítico exige magnitude grande (Δ ≥ 2×piso) ou alta+significativa.
        if delta > 0 and detrator_heavy:
            critico = abs(delta) >= 2 * min_delta or (var >= 1.0 and abs(delta) >= min_delta)
            direcao, sev = "negativa", ("critico" if critico else "atencao")
        elif delta < 0 and detrator_heavy:
            direcao, sev = "positiva", "atencao"  # resolução em curso
        elif delta > 0 and not detrator_heavy:
            direcao, sev = "positiva", "atencao"  # tema bom crescendo
        else:
            continue
        anomalias.append(
            {
                "tipo": "tema",
                "tema_id": tid,
                "agrupamento_id": None,
                "subpilar": None,
                "chave": f"tema: {e['nome']}",
                "score_final": _score_trend(delta, var),
                "magnitude": round(float(delta), 1),
                "direcao": direcao,
                "severidade": sev,
                "tendencia": (
                    "Tema em alta" if direcao == "negativa" else "Em recuperação/crescimento"
                ),
                "periodo": meses_ord[-1],
            }
        )
    return anomalias


def _detectar_diff(empresa_id: int, atual: str, anterior: str, s) -> List[Dict[str, Any]]:
    """Emergência/sumiço de tema (slug + anti-relabel cosine) entre 2 snapshots."""
    from src.models.anomalia import TemaSnapshot

    def _company(per):
        return {
            r.tema_slug: r
            for r in s.query(TemaSnapshot)
            .filter(
                TemaSnapshot.empresa_id == empresa_id,
                TemaSnapshot.periodo == per,
                TemaSnapshot.agrupamento_id.is_(None),
            )
            .all()
        }

    cur = _company(atual)
    prev = _company(anterior)
    if not prev:
        return []
    prev_centroides = [r.centroide for r in prev.values() if r.centroide]

    anomalias: List[Dict[str, Any]] = []
    # emergência: slug novo + não é re-rotulagem (cosine < 0.85)
    for slug, r in cur.items():
        if slug in prev:
            continue
        if _fuzzy_relabel(r.centroide, prev_centroides):
            continue  # re-rotulagem, não é tema novo
        detrator_heavy = r.detrator >= r.promotor
        anomalias.append(
            {
                "tipo": "tema",
                "tema_id": None,
                "agrupamento_id": None,
                "subpilar": None,
                "chave": f"tema novo: {r.tema_label}",
                "score_final": float(min(100, r.volume * 5)),
                "magnitude": float(r.volume),
                "direcao": "negativa" if detrator_heavy else "positiva",
                "severidade": "atencao",
                "tendencia": "Tema emergente",
                "periodo": atual,
            }
        )
    # sumiço: slug sumiu com volume material (>=5) → resolução provável
    for slug, r in prev.items():
        if slug in cur or r.volume < 5:
            continue
        anomalias.append(
            {
                "tipo": "tema",
                "tema_id": None,
                "agrupamento_id": None,
                "subpilar": None,
                "chave": f"tema sumiu: {r.tema_label}",
                "score_final": float(min(100, r.volume * 5)),
                "magnitude": float(-r.volume),
                "direcao": "positiva",
                "severidade": "atencao",
                "tendencia": "Resolução provável",
                "periodo": atual,
            }
        )
    return anomalias


def _detectar_diff_cruzamentos(
    empresa_id: int, atual: str, anterior: str, s
) -> List[Dict[str, Any]]:
    from src.models.anomalia import CruzamentoSnapshot

    def _by_slug(per):
        return {
            r.tema_slug: r
            for r in s.query(CruzamentoSnapshot)
            .filter(CruzamentoSnapshot.empresa_id == empresa_id, CruzamentoSnapshot.periodo == per)
            .all()
        }

    cur = _by_slug(atual)
    prev = _by_slug(anterior)
    if not prev:
        return []
    anomalias: List[Dict[str, Any]] = []
    for slug, r in cur.items():
        ant = prev.get(slug)
        if ant is None:
            anomalias.append(
                {
                    "tipo": "cruzamento",
                    "tema_id": None,
                    "cruzamento_id": None,
                    "agrupamento_id": None,
                    "subpilar": None,
                    "chave": f"cruzamento novo: {r.tema_label}",
                    "score_final": float(min(100, r.peso * 3)),
                    "magnitude": round(r.peso, 1),
                    "direcao": "negativa",
                    "severidade": "atencao",
                    "tendencia": "Cruzamento emergente (causa raiz nascendo)",
                    "periodo": atual,
                }
            )
        elif ant.peso > 0 and abs(r.peso - ant.peso) / ant.peso >= 0.5:
            subiu = r.peso > ant.peso
            anomalias.append(
                {
                    "tipo": "cruzamento",
                    "tema_id": None,
                    "cruzamento_id": None,
                    "agrupamento_id": None,
                    "subpilar": None,
                    "chave": f"cruzamento {'agravou' if subiu else 'aliviou'}: {r.tema_label}",
                    "score_final": float(min(100, r.peso * 3)),
                    "magnitude": round(r.peso - ant.peso, 1),
                    "direcao": "negativa" if subiu else "positiva",
                    "severidade": "atencao",
                    "tendencia": "Cruzamento em agravamento" if subiu else "Cruzamento aliviando",
                    "periodo": atual,
                }
            )
    return anomalias


def detectar_temas(empresa_id: int, *, gravar_snapshot: bool = True) -> List[Dict[str, Any]]:
    """Camada 2 completa: grava snapshot do período atual, roda trend (sempre) +
    diff vs período anterior (se existir). Não persiste anomalias (CP-5 combina)."""
    from src.utils.db import db_session

    if gravar_snapshot:
        snapshot_temas(empresa_id)
        snapshot_cruzamentos(empresa_id)

    with db_session() as s:
        atual = periodo_atual(empresa_id, s)
        anterior = _periodo_anterior(empresa_id, atual, s)
        anomalias = _detectar_trend(empresa_id, s)
        if anterior:
            anomalias += _detectar_diff(empresa_id, atual, anterior, s)
            anomalias += _detectar_diff_cruzamentos(empresa_id, atual, anterior, s)
    anomalias.sort(key=lambda a: -a["score_final"])
    return anomalias
