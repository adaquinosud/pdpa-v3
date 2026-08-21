"""PROBE DESCARTÁVEL — quantas LeituraDiagnostico (nível-empresa) estão STALE hoje.

READ-ONLY, custo US$0 (recomputa hashes; NÃO chama LLM). Stale = hash do dado VIVO
(hash_payload(montar_payload_subpilar recomputado)) != dados_hash gravado na leitura —
exatamente o cálculo do selo da aba Diagnóstico (ui/__init__.py:4834-4840), aplicado à
base inteira. Mede o buraco do §7 (texto de LLM cacheado sobrevive à mudança de base).

Escopo NÍVEL-EMPRESA (agrupamento_id NULL, local_id NULL): é o que a Q16, o Resumo
Executivo e o Diagnóstico Pontual leem — os consumidores que importam para a decisão de
run pago. Rows órfãs (subpilar sumiu do agg) contam como stale.

Uso no Render:  PYTHONPATH=. python scripts/probe_diagnostico_stale.py
Remover após o resultado.
"""

from src.diagnostico.leituras import _gargalo, agregar_subpilares, montar_payload_subpilar
from src.models.diagnostico import LeituraDiagnostico
from src.models.empresa import Empresa
from src.utils.db import db_session
from src.utils.hashing import hash_payload

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
    por_emp = {}  # empresa_id -> [total, stale, orfas]
    for r in rows:
        if r.empresa_id not in aggs:
            agg = agregar_subpilares(s, r.empresa_id)
            aggs[r.empresa_id] = (agg, _gargalo(agg))
        agg, gargalo = aggs[r.empresa_id]
        d = por_emp.setdefault(r.empresa_id, [0, 0, 0])
        d[0] += 1
        if r.subpilar not in agg:
            d[1] += 1
            d[2] += 1  # órfã: o subpilar não existe mais no agg → leitura sem lastro
        elif r.dados_hash:
            payload = montar_payload_subpilar(
                s, r.empresa_id, None, r.subpilar, agg[r.subpilar], gargalo
            )
            if hash_payload(payload) != r.dados_hash:
                d[1] += 1

    print(f"{'empresa':24} {'leituras':>9} {'stale':>6} {'órfãs':>6} {'%stale':>7}")
    tot = [0, 0, 0]
    for eid in sorted(por_emp, key=lambda x: -por_emp[x][1]):
        n, st, orf = por_emp[eid]
        tot = [tot[0] + n, tot[1] + st, tot[2] + orf]
        pct = (100 * st / n) if n else 0
        print(f"{(nomes.get(eid) or '?')[:24]:24} {n:>9} {st:>6} {orf:>6} {pct:>6.0f}%")
    print(f"{'TOTAL':24} {tot[0]:>9} {tot[1]:>6} {tot[2]:>6}")
    print(
        "\nStale = dados_hash gravado != hash do dado vivo (mesmo cálculo do selo do "
        "Diagnóstico)."
    )
    print(
        "Nível-empresa = o escopo que Q16, Resumo Executivo e Diagnóstico Pontual leem. "
        "Regenerar é run pago (flask diagnostico-gerar)."
    )
