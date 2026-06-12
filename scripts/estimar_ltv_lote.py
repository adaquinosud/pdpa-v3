"""Preenche ticket/frequência (LTV) em LOTE para os locais VAZIOS de uma empresa,
usando a hierarquia do ``prefill_ltv`` (irmão preenchido → IA por agrupamento, v2).

SEGURANÇA (mesmo espírito do resolver_place_ids.py / zerar_cliente.py):
  - DRY-RUN é o DEFAULT. Só grava com ``--aplicar`` explícito + confirmação.
  - **Só toca locais com os DOIS campos vazios** (ticket_medio E frequencia NULL).
    **NUNCA sobrescreve** loja já preenchida — nem total (Aimorés) nem parcial
    (um campo setado) — parciais são listados à parte para revisão manual.
  - **Memoiza por agrupamento**: 1 estimativa por agrupamento (não por loja) →
    1 chamada Haiku por agrupamento comercial. Não-comercial (Colaboradores/
    Imprensa/ESG…) → estimativa 0/0 → ``None`` → locais pulados.
  - Hierarquia por agrupamento: (a) se ALGUM local do agrupamento já tem LTV →
    copia (origem ``agrupamento``, $0); (b) senão → IA por nome+setor (origem
    ``ia``). Local sem agrupamento → sem estimativa (manual).
  - ``--aplicar`` roda em transação atômica (rollback em erro).

Uso (no Shell do Render):
    PYTHONPATH=. python scripts/estimar_ltv_lote.py --empresa 5            # dry-run
    PYTHONPATH=. python scripts/estimar_ltv_lote.py --empresa 5 --aplicar  # grava
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _confirmar(emp_id: int, emp_nome: str, n: int) -> None:
    print(
        f"\n[lote] ⚠ Vai GRAVAR ticket/frequência em {n} locais vazios da empresa "
        f"{emp_id} ({emp_nome}). Não sobrescreve preenchidos."
    )
    try:
        resp = input(f"[lote] Digite o id da empresa ({emp_id}) ou 'SIM' para confirmar: ").strip()
    except EOFError:
        raise SystemExit("[lote] ABORTADO: sem terminal interativo para confirmar.")
    if resp != str(emp_id) and resp.upper() != "SIM":
        raise SystemExit(f"[lote] ABORTADO: confirmação {resp!r} não confere. Nada gravado.")


def _estimativa_por_agrupamento(
    s, empresa_id: int, setor: Optional[str], ag_id: Optional[int]
) -> Optional[Dict[str, Any]]:
    """1 estimativa para o agrupamento: (a) copia irmão já preenchido, senão
    (b) IA por nome+setor. ``None`` = sem estimativa (sem agrupamento, ou IA
    devolveu nada / não-comercial)."""
    from src.governanca.impacto_rs import estimar_ltv_agrupamento
    from src.models.agrupamento import Agrupamento
    from src.models.local import Local

    if ag_id is None:
        return None
    # (a) irmão com LTV completo no mesmo agrupamento → copia ($0)
    irmao = (
        s.query(Local)
        .filter(
            Local.empresa_id == empresa_id,
            Local.agrupamento_id == ag_id,
            Local.ticket_medio.isnot(None),
            Local.frequencia.isnot(None),
        )
        .first()
    )
    if irmao is not None:
        return {
            "ticket_medio": float(irmao.ticket_medio),
            "frequencia": float(irmao.frequencia),
            "origem": "agrupamento",
        }
    # (b) IA por nome do agrupamento + setor (v2)
    ag = s.get(Agrupamento, ag_id)
    if ag is None or not ag.nome:
        return None
    est = estimar_ltv_agrupamento(ag.nome, setor=setor)
    if est is None:
        return None
    return {**est, "origem": "ia"}


def main(empresa: int, aplicar: bool) -> int:
    from src.models.agrupamento import Agrupamento
    from src.models.empresa import Empresa
    from src.models.local import Local
    from src.utils.db import db_session

    with db_session() as s:
        emp = s.get(Empresa, empresa)
        if emp is None:
            raise SystemExit(f"[lote] empresa {empresa} não encontrada")
        setor = emp.setor

        locais = s.query(Local).filter(Local.empresa_id == empresa).order_by(Local.id).all()
        vazios = [x for x in locais if x.ticket_medio is None and x.frequencia is None]
        parciais = [x for x in locais if (x.ticket_medio is None) != (x.frequencia is None)]
        preenchidos = [x for x in locais if x.ticket_medio is not None and x.frequencia is not None]

        modo = "APLICAR (grava)" if aplicar else "DRY-RUN (só preview, nada gravado)"
        print("═" * 92)
        print(f"[lote] empresa={empresa} ({emp.nome}) · setor={setor!r} · modo={modo}")
        print(
            f"[lote] locais: {len(locais)} total · {len(vazios)} vazios (alvo) · "
            f"{len(preenchidos)} já preenchidos (intocados) · {len(parciais)} parciais (revisar)"
        )
        print("═" * 92)
        if not vazios:
            print("[lote] nenhum local vazio. Nada a fazer.")
            print("═" * 92)
            return 0

        # Agrupa vazios por agrupamento; 1 estimativa por agrupamento (memoizado).
        por_ag: Dict[Optional[int], List[Local]] = defaultdict(list)
        for x in vazios:
            por_ag[x.agrupamento_id].append(x)

        plano: List[tuple] = []  # (local, ticket, freq, origem)
        sem_estimativa: List[Local] = []
        print(f"\n{'agrupamento':<28} {'origem':<11} {'ticket':>9} {'freq':>6} {'locais':>7}")
        print("─" * 92)
        for ag_id, locs in por_ag.items():
            est = _estimativa_por_agrupamento(s, empresa, setor, ag_id)
            ag_nome = (
                "(sem agrupamento)" if ag_id is None else (s.get(Agrupamento, ag_id).nome or "?")
            )
            if est is None:
                sem_estimativa.extend(locs)
                motivo = "sem agrupamento" if ag_id is None else "não-comercial/IA vazia"
                print(
                    f"{ag_nome[:28]:<28} {'PULADO':<11} {'—':>9} {'—':>6} "
                    f"{len(locs):>7}  ({motivo})"
                )
                continue
            for x in locs:
                plano.append((x, est["ticket_medio"], est["frequencia"], est["origem"]))
            print(
                f"{ag_nome[:28]:<28} {est['origem']:<11} {est['ticket_medio']:>9,.0f} "
                f"{est['frequencia']:>6,.1f} {len(locs):>7}"
            )
        print("─" * 92)
        n_ia = len({a for a in por_ag if a is not None})
        print(
            f"[lote] preencheria {len(plano)} locais · pularia {len(sem_estimativa)} · "
            f"~{n_ia} chamadas Haiku (1/agrupamento, memoizado) ≈ US${n_ia * 0.0005:.3f}"
        )

        if not aplicar:
            print("\n[lote] DRY-RUN — nada gravado. Se OK, rode de novo com --aplicar.")
            print("═" * 92)
            return 0
        if not plano:
            print("\n[lote] nada a gravar (nenhuma estimativa válida).")
            print("═" * 92)
            return 0

        _confirmar(empresa, emp.nome, len(plano))
        for x, t, f, origem in plano:
            x.ticket_medio = t
            x.frequencia = f
            x.ltv_origem = origem
        s.flush()
        print(f"\n[lote] OK: {len(plano)} locais preenchidos. Commit ao sair.")
        print("═" * 92)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Preenche LTV (ticket/freq) em lote — só vazios.")
    ap.add_argument("--empresa", required=True, type=int, help="id da empresa.")
    ap.add_argument(
        "--aplicar", action="store_true", help="grava (c/ confirmação). SEM flag = dry-run."
    )
    args = ap.parse_args()
    raise SystemExit(main(args.empresa, args.aplicar))
