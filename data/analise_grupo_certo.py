"""Análise focada — só grupo CERTO do benchmark v3.1."""

from __future__ import annotations

import json
from collections import Counter, defaultdict

ROWS_PATH = "data/benchmark_progress.jsonl"

with open(ROWS_PATH) as f:
    rows = [json.loads(line) for line in f if line.strip()]

certos = [r for r in rows if r.get("revisao") == "certo"]
total = len(certos)
print(f"Total grupo CERTO: {total}")

com_erro = [r for r in certos if r.get("erro")]
classificados = [r for r in certos if not r.get("erro")]
print(f"  Com erro runtime: {len(com_erro)}")
print(f"  Classificados (válidos): {len(classificados)}")
print()

ac_sub = sum(1 for r in classificados if r["subpilar_v3"] == r["subpilar_atual_v2"])
ac_tipo = sum(1 for r in classificados if r["tipo_v3"] == r["tipo_v2"])
ac_ambos = sum(
    1
    for r in classificados
    if r["subpilar_v3"] == r["subpilar_atual_v2"] and r["tipo_v3"] == r["tipo_v2"]
)


def pct(n: int) -> str:
    return f"{n}/{total} ({n * 100 / total:.1f}%)"


print("=" * 64)
print("ACERTO NO GRUPO CERTO (denominador = 468, inclui 3 erros runtime)")
print("=" * 64)
print(f"1. Subpilar apenas (v3 == v2):  {pct(ac_sub)}")
print(f"2. Tipo apenas (v3 == v2):      {pct(ac_tipo)}")
print(f"3. Subpilar E tipo:             {pct(ac_ambos)}")
print()

print("=" * 64)
print("4. DISTRIBUIÇÃO DOS 468 CASOS CERTOS POR SUBPILAR v2")
print("=" * 64)
dist_v2 = Counter(r["subpilar_atual_v2"] for r in certos)
print(f"{'subpilar v2':<12} {'qtd':>6} {'%':>6}")
print("-" * 28)
for sp, n in dist_v2.most_common():
    print(f"{sp:<12} {n:>6} {n * 100 / total:>5.1f}%")
print()

print("=" * 64)
print("5. TAXA DE REPRODUÇÃO (v3 manteve subpilar v2) — SP com 10+ casos")
print("=" * 64)
reprod = defaultdict(lambda: {"total": 0, "ok_sub": 0, "ok_tipo": 0, "ok_ambos": 0})
for r in certos:
    sp = r["subpilar_atual_v2"]
    reprod[sp]["total"] += 1
    if r.get("erro"):
        continue
    if r["subpilar_v3"] == sp:
        reprod[sp]["ok_sub"] += 1
    if r["tipo_v3"] == r["tipo_v2"]:
        reprod[sp]["ok_tipo"] += 1
    if r["subpilar_v3"] == sp and r["tipo_v3"] == r["tipo_v2"]:
        reprod[sp]["ok_ambos"] += 1

hdr = f"{'sp v2':<6} {'total':>6} {'sub':>5} {'%sub':>6} {'tipo':>5} {'%tipo':>6} {'ambos':>6} {'%ambos':>7}"  # noqa: E501
print(hdr)
print("-" * len(hdr))
for sp, n in dist_v2.most_common():
    d = reprod[sp]
    if d["total"] < 10:
        continue
    print(
        f"{sp:<6} {d['total']:>6} "
        f"{d['ok_sub']:>5} {d['ok_sub'] * 100 / d['total']:>5.1f}% "
        f"{d['ok_tipo']:>5} {d['ok_tipo'] * 100 / d['total']:>5.1f}% "
        f"{d['ok_ambos']:>6} {d['ok_ambos'] * 100 / d['total']:>6.1f}%"
    )

menores = sorted(sp for sp, n in dist_v2.items() if n < 10)
if menores:
    print()
    print(f"Subpilares com <10 casos (omitidos da tabela acima): {menores}")
    for sp in menores:
        d = reprod[sp]
        print(
            f"  {sp}: total={d['total']}, sub_OK={d['ok_sub']}, "
            f"tipo_OK={d['ok_tipo']}, ambos_OK={d['ok_ambos']}"
        )

print()
print("=" * 64)
print("6. MATRIZ COMPLETA (subpilar v2 → subpilar v3)")
print("=" * 64)
matriz: Counter = Counter()
for r in certos:
    if r.get("erro"):
        matriz[(r["subpilar_atual_v2"], "ERR")] += 1
    else:
        matriz[(r["subpilar_atual_v2"], r["subpilar_v3"])] += 1

sps_v2 = sorted({k[0] for k in matriz})
sps_v3 = sorted({k[1] for k in matriz})

header_label = "v2->v3"
print(f"{header_label:<8}", end="")
for sp3 in sps_v3:
    print(f"{sp3:>6}", end="")
print(f"{'TOTAL':>7}")
print("-" * (8 + 6 * len(sps_v3) + 7))

for sp2 in sps_v2:
    total_linha = sum(matriz.get((sp2, sp3), 0) for sp3 in sps_v3)
    print(f"{sp2:<8}", end="")
    for sp3 in sps_v3:
        v = matriz.get((sp2, sp3), 0)
        if v == 0:
            print(f"{'.':>6}", end="")
        elif sp2 == sp3:
            print(f"{f'[{v}]':>6}", end="")
        else:
            print(f"{v:>6}", end="")
    print(f"{total_linha:>7}")

diag = sum(matriz.get((sp, sp), 0) for sp in sps_v2 if sp in sps_v3)
print()
print(f"Diagonal (v3 == v2): {diag}/{total} = {diag * 100 / total:.1f}%")
print(f"Erros runtime: {sum(matriz.get((sp, 'ERR'), 0) for sp in sps_v2)}")
