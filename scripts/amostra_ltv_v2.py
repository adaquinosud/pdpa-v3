"""Amostra read-only da estimativa de LTV v2 (calibrada por setor + agrupamento).

Roda a estimativa IA (``estimar_ltv_agrupamento``, prompt v2) para os agrupamentos
de UMA empresa e imprime ticket/frequência sugeridos — para validar À MÃO se os
números batem com a realidade ANTES de qualquer lote.

**NÃO escreve nada no banco.** Cada agrupamento = 1 chamada Haiku (~US$0,0005).
Categoria não-comercial (Colaboradores/Imprensa/ESG…) → o prompt devolve 0/0 →
estimativa ``None`` → impresso como "PULADO (não-comercial)".

Uso:
    PYTHONPATH=. python scripts/amostra_ltv_v2.py --empresa 5            # todos os agrupamentos
    PYTHONPATH=. python scripts/amostra_ltv_v2.py --empresa 4 --limite 4 # primeiros 4
    PYTHONPATH=. python scripts/amostra_ltv_v2.py --empresa 5 --agrupamentos "Seminovos" "UseCar"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _carregar(empresa_id: int, nomes: Optional[List[str]], limite: int):
    """Lê (setor, [agrupamentos]). NÃO escreve. Filtra por nomes se passados."""
    from sqlalchemy import text

    from src.utils.db import db_session

    with db_session() as s:
        row = s.execute(
            text("SELECT nome, setor FROM empresas WHERE id = :e"), {"e": empresa_id}
        ).first()
        if row is None:
            raise SystemExit(f"[amostra] empresa {empresa_id} não encontrada")
        nome_emp, setor = row[0], row[1]
        q = "SELECT nome FROM agrupamentos WHERE empresa_id = :e ORDER BY id"
        ags = [r[0] for r in s.execute(text(q), {"e": empresa_id}).all()]
    if nomes:
        alvo = {n.lower() for n in nomes}
        ags = [a for a in ags if a.lower() in alvo]
    elif limite:
        ags = ags[:limite]
    return nome_emp, setor, ags


def main() -> int:
    ap = argparse.ArgumentParser(description="Amostra read-only da estimativa LTV v2.")
    ap.add_argument("--empresa", required=True, type=int, help="id da empresa.")
    ap.add_argument("--limite", type=int, default=0, help="máx. agrupamentos (0 = todos).")
    ap.add_argument("--agrupamentos", nargs="+", help="nomes específicos (sobrepõe --limite).")
    args = ap.parse_args()

    nome_emp, setor, ags = _carregar(args.empresa, args.agrupamentos, args.limite)
    if not ags:
        print(f"[amostra] nenhum agrupamento para empresa {args.empresa}.")
        return 0

    from src.governanca.impacto_rs import estimar_ltv_agrupamento

    print("═" * 84)
    print(
        f"[amostra] empresa={args.empresa} ({nome_emp}) · setor={setor!r} · {len(ags)} agrupamentos"
    )
    print("[amostra] estimativa v2 (read-only, não grava). 1 chamada Haiku por agrupamento.")
    print("═" * 84)
    print(f"{'agrupamento':<34} {'ticket (R$)':>12} {'freq/ano':>10} {'LTV 2f':>12}")
    print("─" * 84)
    for nome in ags:
        est = estimar_ltv_agrupamento(nome, setor=setor)
        if est is None:
            print(f"{nome[:34]:<34} {'—':>12} {'—':>10}   PULADO (não-comercial/sem estimativa)")
            continue
        t, f = est["ticket_medio"], est["frequencia"]
        ltv = t * f
        print(f"{nome[:34]:<34} {t:>12,.0f} {f:>10,.1f} {ltv:>12,.0f}")
    print("─" * 84)
    print("Confira: concessionária=ticket alto/freq baixa · lab=ticket de exame · café=ticket")
    print("baixo/freq alta · internos PULADOS. Se bater, seguimos pro lote (com seu OK).")
    print("═" * 84)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
