"""Probe read-only do Índice de Propagação — WRAPPER FINO do motor
``src.anomalias.propagacao.analisar_propagacao`` (garante que o validado é o que
roda na tela; sem lógica duplicada).

Uso:
    PYTHONPATH=. python3 scripts/probe_indice_propagacao.py
    PYTHONPATH=. python3 scripts/probe_indice_propagacao.py 16 17
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.anomalias.propagacao import PROPAGACAO_CONFIG, analisar_propagacao  # noqa: E402
from src.models.empresa import Empresa  # noqa: E402
from src.utils.db import db_session  # noqa: E402

IDS_DEFAULT = [16, 17]


def _por_empresa(eid: int) -> None:
    with db_session() as s:
        emp = s.get(Empresa, eid)
        nome = emp.nome if emp else "(não encontrada)"
    print(f"\n===== {nome} (id {eid}) =====")
    if nome == "(não encontrada)":
        return
    linhas = analisar_propagacao(eid)
    raio_max = sum(PROPAGACAO_CONFIG["pesos"].values())
    print(
        f"detratores (na lista): {len(linhas)} · urgência = raio × aceleração × log(1+vol) "
        f"· raio máx {raio_max} · alto ≥ {PROPAGACAO_CONFIG['raio_alto']} · top 15:\n"
    )
    for i, x in enumerate(linhas[:15], 1):
        print(
            f"{i:>2}. {x['nome']:30.30} {x['subpilar'] or '-':4} vol {x['volume']:>4} "
            f"raio {x['raio']} [{','.join(x['camadas'])}] {x['glifo']:3} urg {x['urgencia']:>6} "
            f"· [{x['quadrante']}]"
        )
        print(
            f"    → {x['nome']}: {x['mensagem']} "
            f"(raio {x['raio']}/{raio_max} · vol {x['volume']} · {x['glifo']})"
        )


def main(ids: list[int]) -> None:
    for eid in ids:
        _por_empresa(eid)


if __name__ == "__main__":
    args = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else IDS_DEFAULT
    main(args)
