"""Probe read-only do sinal de tendência da aba Temas, com DADO REAL.

Reusa o ``_mapa_tendencia_tema`` da UI (mesmo glifo/cor/escolha que o template) —
sem reimplementar. Imprime, por empresa (ids 16/17 default + argv), cada tema com
sinal como vai aparecer: "<label> <glifo> <tendencia>". Mostra também quantos temas
ativos existem vs quantos têm sinal (os sem sinal saem limpos, sem glifo).

Uso:
    PYTHONPATH=. python3 scripts/probe_tendencia_temas.py
    PYTHONPATH=. python3 scripts/probe_tendencia_temas.py 16 17
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import distinct, func  # noqa: E402

from src.models.anomalia import AnomaliaDetectada  # noqa: E402
from src.models.empresa import Empresa  # noqa: E402
from src.models.temas import Tema, VerbatimTema  # noqa: E402
from src.anomalias.propagacao import _mapa_tendencia_tema  # noqa: E402
from src.utils.db import db_session  # noqa: E402

IDS_DEFAULT = [16, 17]


def _por_empresa(s, eid: int) -> None:
    emp = s.get(Empresa, eid)
    print(f"\n===== {emp.nome if emp else '(não encontrada)'} (id {eid}) =====")
    if emp is None:
        return

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

    n_temas = (
        s.query(func.count(distinct(Tema.id)))
        .join(VerbatimTema, VerbatimTema.tema_id == Tema.id)
        .filter(Tema.empresa_id == eid, Tema.ativo.is_(True))
        .scalar()
    ) or 0
    print(
        f"temas ativos: {n_temas} | com sinal de tendência: {len(mapa)} "
        f"| limpos (sem glifo): {max(n_temas - len(mapa), 0)}"
    )

    if not mapa:
        print("  (nenhum tema com sinal — todos saem limpos)")
        return
    nomes = dict(s.query(Tema.id, Tema.nome).filter(Tema.id.in_(list(mapa))).all())
    for tid, sig in sorted(mapa.items(), key=lambda kv: kv[1]["severidade"] != "critico"):
        nome = nomes.get(tid, f"tema#{tid}")
        print(
            f"  {nome} {sig['glifo']} {sig['tendencia']} "
            f"(dir={sig['direcao']} mag={sig['magnitude']} sev={sig['severidade']})"
        )


def main(ids: list[int]) -> None:
    with db_session() as s:
        for eid in ids:
            _por_empresa(s, eid)


if __name__ == "__main__":
    args = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else IDS_DEFAULT
    main(args)
