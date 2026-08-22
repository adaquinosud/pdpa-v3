"""PROBE DESCARTÁVEL — quantas LeituraDiagnostico (nível-empresa) estão STALE hoje.

READ-ONLY, custo US$0 (recomputa hashes; NÃO chama LLM). Usa a RÉGUA CANÔNICA
(``motivo_stale``) — Fatia 4 — para os três concordarem: régua, lista e probe. Quebra por
motivo, que é o que decide se regenerar é atualização ou primeira geração:
  - ``sem_hash``   → leitura pré-hash (nunca registrou base). NOVO na contagem (Fatia 4);
                     antes escapava (``elif r.dados_hash``).
  - ``divergente`` → hash do dado vivo != gravado (base mudou) OU órfã (subpilar sumiu).

Escopo NÍVEL-EMPRESA (agrupamento_id NULL, local_id NULL): o que a Q16, o Resumo Executivo,
o Diagnóstico Pontual, o Plano Executivo e o Parecer leem.

Uso no Render:  PYTHONPATH=. python scripts/probe_diagnostico_stale.py
Remover após o resultado.
"""

from src.diagnostico.leituras import _gargalo, agregar_subpilares, motivo_stale
from src.models.diagnostico import LeituraDiagnostico
from src.models.empresa import Empresa
from src.utils.db import db_session

with db_session() as s:
    nomes = {e.id: e.nome for e in s.query(Empresa)}
    rows = (
        s.query(LeituraDiagnostico)
        .filter(
            LeituraDiagnostico.agrupamento_id.is_(None),
            LeituraDiagnostico.local_id.is_(None),
        )
        .all()
    )
    if not rows:
        print("Nenhuma LeituraDiagnostico nível-empresa gravada — nada a medir.")
        raise SystemExit

    aggs = {}
    por_emp = {}  # empresa_id -> [total, stale, sem_hash, divergente]
    for r in rows:
        if r.empresa_id not in aggs:
            agg = agregar_subpilares(s, r.empresa_id)
            aggs[r.empresa_id] = (agg, _gargalo(agg))
        agg, gargalo = aggs[r.empresa_id]
        mot = motivo_stale(s, r, r.subpilar, agg.get(r.subpilar), gargalo, r.empresa_id)
        d = por_emp.setdefault(r.empresa_id, [0, 0, 0, 0])
        d[0] += 1
        if mot == "sem_hash":
            d[1] += 1
            d[2] += 1
        elif mot == "divergente":
            d[1] += 1
            d[3] += 1

    print(
        f"{'empresa':24} {'leituras':>9} {'stale':>6} {'sem_hash':>9} {'diverg':>7} {'%stale':>7}"
    )
    tot = [0, 0, 0, 0]
    for eid in sorted(por_emp, key=lambda x: -por_emp[x][1]):
        n, st, sh, dv = por_emp[eid]
        tot = [tot[0] + n, tot[1] + st, tot[2] + sh, tot[3] + dv]
        pct = (100 * st / n) if n else 0
        print(f"{(nomes.get(eid) or '?')[:24]:24} {n:>9} {st:>6} {sh:>9} {dv:>7} {pct:>6.0f}%")
    print(f"{'TOTAL':24} {tot[0]:>9} {tot[1]:>6} {tot[2]:>9} {tot[3]:>7}")
    print(
        "\nRégua canônica motivo_stale (Fatia 4). sem_hash = leitura pré-hash (só stale desde "
        "a Fatia 4). divergente = base mudou ou órfã. Regenerar = run pago; SEM backfill."
    )
