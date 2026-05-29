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


def recalcular_governanca(empresa_id: int, *, skip_unchanged: bool = True) -> Dict[str, int]:
    """Recalcula Proximity por escopo (empresa, cada agrupamento, cada loja) e
    persiste em ``proximity_calculations``.

    Estratégia: **delete-then-insert por escopo** com **skip por hash de escopo**.
    Se o mix de verbatins do escopo não mudou (mesmo ``dados_hash``), o escopo é
    pulado sem reescrita. Gini segue no-op até o CP-LG-3.
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
    return {"proximity_escopos": recalc, "proximity_pulados": pulados, "gini": 0}
