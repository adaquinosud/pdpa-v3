"""Probe read-only do Índice de Propagação (raio × aceleração) por tema.

RAIO (0-7) = soma dos pesos das camadas em que o tema propaga:
  - Diagnóstico (peso 1): detrator DOMINANTE nos verbatins do tema (detr > prom).
  - RA (peso 2): o tema tem verbatim de fonte reclame_aqui com tipo=detrator.
  - IA (peso 4): o SUBPILAR do tema tem detrator dominante em sonda_ia_avaliacoes
    (projeção: o tema não existe na IA, mas o subpilar dele sim).
ACELERAÇÃO = a anomalia de tema já gravada (reusa _mapa_tendencia_tema p/ o glifo):
  fator ↑↑=1.0, ↑=0.7, (→/sem-anomalia)=0.4, ↓=0.1, ↓↓=0.
URGÊNCIA = raio × fator. Ranqueia desc, top 15 por empresa.

Read-only, db_session. Uso:
    PYTHONPATH=. python3 scripts/probe_indice_propagacao.py
    PYTHONPATH=. python3 scripts/probe_indice_propagacao.py 16 17
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import and_, func  # noqa: E402

from src.models.anomalia import AnomaliaDetectada  # noqa: E402
from src.models.empresa import Empresa  # noqa: E402
from src.models.fonte import Fonte  # noqa: E402
from src.models.sonda_ia import SondaIAAvaliacao  # noqa: E402
from src.models.temas import Tema, VerbatimTema  # noqa: E402
from src.models.verbatim import Verbatim  # noqa: E402
from src.ui import _mapa_tendencia_tema  # noqa: E402
from src.utils.db import db_session  # noqa: E402

IDS_DEFAULT = [16, 17]
PESO_DIAG, PESO_RA, PESO_IA = 1, 2, 3  # raio máx 6 (IA de 4→3: não dominar o volume)
FATOR = {"↑↑": 1.0, "↑": 0.7, "↓": 0.1, "↓↓": 0.0}  # sem glifo → 0.4

# ── Quadrantes (raio × aceleração) — limiares CALIBRÁVEIS ──
RAIO_ALTO = 4  # raio >= isto = "alto/propagado"
_ACELERANDO = {"↑", "↑↑"}
_ALIVIANDO = {"↓", "↓↓"}
_QUADRANTE_MSG = {
    "Crítico": "dor intensa, pública e em alta — prioridade máxima.",
    "Acelerando": "dor subindo rápido, ainda não propagada — "
    "janela para agir antes que se espalhe.",
    "Crônico": "dor madura e consolidada — já propagada mas estável. Reconstrução, não contenção.",
    "Latente": "dor contida e parada — monitorar.",
    "Em recuperação": "dor aliviando — acompanhar, fora do alerta de urgência.",
}


def _quadrante(raio: int, glifo: str) -> str:
    if glifo in _ALIVIANDO:
        return "Em recuperação"
    alto = raio >= RAIO_ALTO
    acel = glifo in _ACELERANDO  # → (sem anomalia) conta como estável
    if acel:
        return "Crítico" if alto else "Acelerando"
    return "Crônico" if alto else "Latente"


def _por_empresa(s, eid: int) -> None:
    emp = s.get(Empresa, eid)
    print(f"\n===== {emp.nome if emp else '(não encontrada)'} (id {eid}) =====")
    if emp is None:
        return

    # (a) verbatins por (tema, subpilar, tipo, é-RA) — base do raio diag/RA + subpilar
    rows = (
        s.query(
            Tema.id,
            Tema.nome,
            Verbatim.subpilar,
            Verbatim.tipo,
            (Fonte.conector_tipo == "reclame_aqui").label("eh_ra"),
            func.count(func.distinct(Verbatim.id)),
        )
        .select_from(VerbatimTema)
        .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
        .join(Tema, and_(Tema.id == VerbatimTema.tema_id, Tema.ativo.is_(True)))
        .join(Fonte, Fonte.id == Verbatim.fonte_id)
        .filter(
            Verbatim.empresa_id == eid,
            Verbatim.tem_texto.is_(True),
            Verbatim.subpilar.isnot(None),
        )
        .group_by(Tema.id, Tema.nome, Verbatim.subpilar, Verbatim.tipo, "eh_ra")
        .all()
    )

    temas: dict = {}
    for tid, nome, sub, tipo, eh_ra, n in rows:
        n = int(n or 0)
        t = temas.setdefault(
            tid, {"nome": nome, "total": 0, "detr": 0, "prom": 0, "ra_detr": 0, "sub_vol": {}}
        )
        t["total"] += n
        t["sub_vol"][sub] = t["sub_vol"].get(sub, 0) + n
        if tipo == "detrator":
            t["detr"] += n
            if eh_ra:
                t["ra_detr"] += n
        elif tipo == "promotor":
            t["prom"] += n

    # (b) IA: detrator dominante por subpilar em sonda_ia_avaliacoes
    ia: dict = {}
    for sub, tipo, n in (
        s.query(SondaIAAvaliacao.subpilar, SondaIAAvaliacao.tipo, func.count())
        .filter(SondaIAAvaliacao.empresa_id == eid)
        .group_by(SondaIAAvaliacao.subpilar, SondaIAAvaliacao.tipo)
    ):
        d = ia.setdefault(sub, {"detr": 0, "prom": 0})
        if tipo == "detrator":
            d["detr"] += int(n or 0)
        elif tipo == "promotor":
            d["prom"] += int(n or 0)
    ia_detr_dominante = {sub for sub, d in ia.items() if d["detr"] > d["prom"]}

    # (c) aceleração: reusa o map da UI (mesmo glifo do template)
    anoms = (
        s.query(
            AnomaliaDetectada.tipo,
            AnomaliaDetectada.tema_id,
            AnomaliaDetectada.chave,
            AnomaliaDetectada.tendencia,
            AnomaliaDetectada.direcao,
            AnomaliaDetectada.magnitude,
            AnomaliaDetectada.severidade,
        )
        .filter(AnomaliaDetectada.empresa_id == eid)
        .all()
    )
    mapa = _mapa_tendencia_tema(anoms, ag_filtro=None)

    linhas = []
    n_promotor = 0
    for tid, t in temas.items():
        # RAIO só conta pra tema DETRATOR (detr > prom). Tema promotor não é dor se
        # propagando — sai da lista de urgência ("onde já encanta", não urgência).
        if t["detr"] <= t["prom"]:
            n_promotor += 1
            continue
        sub_dom = max(t["sub_vol"], key=t["sub_vol"].get) if t["sub_vol"] else None
        camadas = ["diag"]  # detrator dominante → camada diagnóstico passa (peso 1)
        raio = PESO_DIAG
        if t["ra_detr"] > 0:
            raio += PESO_RA
            camadas.append("RA")
        if sub_dom in ia_detr_dominante:
            raio += PESO_IA
            camadas.append("IA")
        sig = mapa.get(tid)
        glifo = sig["glifo"] if sig else "→"
        fator = FATOR.get(glifo, 0.4)
        logv = math.log1p(t["total"])  # log(1+vol): quantidade pesa sem dominar
        urg = round(raio * fator * logv, 2)
        quad = _quadrante(raio, glifo)
        linhas.append(
            {
                "nome": t["nome"],
                "sub": sub_dom,
                "vol": t["total"],
                "raio": raio,
                "camadas": camadas,
                "glifo": glifo,
                "urg": urg,
                "quad": quad,
            }
        )

    linhas.sort(key=lambda x: (-x["urg"], -x["raio"], -x["vol"]))
    print(
        f"temas ativos: {len(temas)} | detratores (na lista): {len(linhas)} | "
        f"promotores/neutros fora: {n_promotor}"
    )
    print(
        f"urgência = raio × aceleração × log(1+vol) · raio máx {PESO_DIAG + PESO_RA + PESO_IA} "
        f"(diag {PESO_DIAG}/RA {PESO_RA}/IA {PESO_IA}) · alto ≥ {RAIO_ALTO} · top 15:\n"
    )
    for i, x in enumerate(linhas[:15], 1):
        print(
            f"{i:>2}. {x['nome']:30.30} {x['sub'] or '-':4} vol {x['vol']:>4} "
            f"raio {x['raio']} [{','.join(x['camadas'])}] {x['glifo']:3} urg {x['urg']:>6} "
            f"· [{x['quad']}]"
        )
        print(
            f"    → {x['nome']}: {_QUADRANTE_MSG[x['quad']]} "
            f"(raio {x['raio']}/{PESO_DIAG + PESO_RA + PESO_IA} · vol {x['vol']} · {x['glifo']})"
        )


def main(ids: list[int]) -> None:
    with db_session() as s:
        for eid in ids:
            _por_empresa(s, eid)


if __name__ == "__main__":
    args = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else IDS_DEFAULT
    main(args)
