"""Gera ``data/reauditoria_50casos.xlsx`` para reauditoria do Alexandre.

Composição (50 casos — ajustada após contar IDs únicos disponíveis):
  - 24 A1 v2 → sem_lastro v3.1 (TODOS os ids únicos disponíveis;
    a 1ª amostra de 20 cobriu 16 desses 24, mas mostramos todos os 24
    aqui para o Alexandre revisar de uma vez)
  - 13 A1 v2 → outros v3.1 (proporcional: ~7 P2, ~3 Pa1, ~2 A2, ~1 D1)
  - 13 D3 v2 → outros v3.1 (proporcional: ~5 D1, ~4 sem_lastro, ~1 D2,
    ~1 P2, ~1 A1, ~1 A2)

Coluna `meu_voto` fica vazia para preenchimento manual com
'v3' / 'v2' / 'ambíguo'.

Reusa ``data/benchmark_progress.jsonl`` + ``data/auditoria_v2_marcada.xlsx``.
Sem chamadas à API.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

import pandas as pd


DATA = Path("data")
JSONL = DATA / "benchmark_progress.jsonl"
XLSX_IN = DATA / "auditoria_v2_marcada.xlsx"
XLSX_OUT = DATA / "reauditoria_50casos.xlsx"

# IDs já mostrados na primeira amostra de 20 (índices 0, 5, 10, ...) — evitar repetir
JA_VISTOS = {
    "71661",
    "75126",
    "75174",
    "75480",
    "75542",
    "75573",
    "75626",
    "75634",
    "75753",
    "83405",
    "86765",
    "86786",
    "86845",
    "86877",
    "93547",
    "93564",
}

random.seed(42)  # reprodutibilidade


def carregar_textos() -> dict[str, dict]:
    df = pd.read_excel(XLSX_IN)
    df["id"] = df["id"].astype(str)
    out: dict[str, dict] = {}
    for _, row in df.iterrows():
        rid = str(row["id"]).strip()
        if rid in out:
            continue  # primeira ocorrência basta
        out[rid] = {
            "empresa": str(row["empresa"]).strip(),
            "fonte": str(row["fonte"]).strip(),
            "texto": str(row["texto"]).strip() if pd.notna(row["texto"]) else "",
            "tipo": str(row["tipo"]).strip() if pd.notna(row["tipo"]) else "",
        }
    return out


def carregar_rows() -> list[dict]:
    with JSONL.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    textos = carregar_textos()
    rows = carregar_rows()

    # Filtro grupo CERTO sem erro runtime
    certos = [r for r in rows if r.get("revisao") == "certo" and not r.get("erro")]

    # ── Bucket A: A1 → sem_lastro (24 casos = TODOS ids únicos) ──────────
    # Há 107 casos brutos, mas só 24 ids únicos por causa de duplicatas no XLSX.
    # Removemos o filtro JA_VISTOS para apresentar todos os 24 únicos de uma vez.
    a1_sl_all = [
        r for r in certos if r["subpilar_atual_v2"] == "A1" and r["subpilar_v3"] == "sem_lastro"
    ]
    a1_sl_unique: dict[str, dict] = {}
    for r in a1_sl_all:
        if r["id"] in a1_sl_unique:
            continue
        a1_sl_unique[r["id"]] = r
    pool_a = list(a1_sl_unique.values())
    pool_a.sort(key=lambda r: r["id"])  # ordem estável para a planilha
    bucket_a = pool_a  # todos os 24
    print(f"Bucket A — A1→sem_lastro: {len(bucket_a)} ids únicos (pool {len(pool_a)})")

    # ── Bucket B: A1 → outros (10 casos, proporcional) ────────────────────
    by_dest_b: dict[str, list[dict]] = defaultdict(list)
    for r in certos:
        if r["subpilar_atual_v2"] != "A1":
            continue
        dest = r["subpilar_v3"]
        if dest in {"A1", "sem_lastro"}:
            continue  # A1 reproduzido ou A1→sem_lastro (já tem bucket A)
        by_dest_b[dest].append(r)

    # Proporção aproximada: P2 35, Pa1 16, A2 13, D1 8, A3 3 (total 75)
    # Bucket B aumentado para 13 (compensar bucket A que ficou em 24, não 30).
    quotas_b = {"P2": 7, "Pa1": 3, "A2": 2, "D1": 1}
    bucket_b: list[dict] = []
    for dest, q in quotas_b.items():
        pool = [r for r in by_dest_b.get(dest, []) if r["id"] not in JA_VISTOS]
        # dedup por id
        seen = set()
        pool_unique = []
        for r in pool:
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            pool_unique.append(r)
        random.shuffle(pool_unique)
        bucket_b.extend(pool_unique[:q])
    print(
        f"Bucket B — A1→outros: {len(bucket_b)} "
        f"(distrib: {[(r['subpilar_v3'], r['id']) for r in bucket_b]})"
    )

    # ── Bucket C: D3 → outros (10 casos, proporcional) ────────────────────
    by_dest_c: dict[str, list[dict]] = defaultdict(list)
    for r in certos:
        if r["subpilar_atual_v2"] != "D3":
            continue
        dest = r["subpilar_v3"]
        if dest == "D3":
            continue  # mantido
        by_dest_c[dest].append(r)

    # Proporção: D1 13, sem_lastro 9, D2 5, P2 2, A1 2, A2 1 (total 32)
    # Bucket C aumentado para 13 (compensar bucket A).
    quotas_c = {"D1": 5, "sem_lastro": 4, "D2": 1, "P2": 1, "A1": 1, "A2": 1}
    bucket_c: list[dict] = []
    for dest, q in quotas_c.items():
        pool = [r for r in by_dest_c.get(dest, []) if r["id"] not in JA_VISTOS]
        seen = set()
        pool_unique = []
        for r in pool:
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            pool_unique.append(r)
        random.shuffle(pool_unique)
        bucket_c.extend(pool_unique[:q])
    print(
        f"Bucket C — D3→outros: {len(bucket_c)} "
        f"(distrib: {[(r['subpilar_v3'], r['id']) for r in bucket_c]})"
    )

    # ── Monta planilha ────────────────────────────────────────────────────
    linhas = []
    for bucket_label, bucket in [
        ("A1->sem_lastro", bucket_a),
        ("A1->outros", bucket_b),
        ("D3->outros", bucket_c),
    ]:
        for r in bucket:
            rid = r["id"]
            t = textos.get(rid, {})
            linhas.append(
                {
                    "id": rid,
                    "bucket": bucket_label,
                    "empresa": t.get("empresa", ""),
                    "fonte": t.get("fonte", ""),
                    "texto": t.get("texto", ""),
                    "subpilar_v2": r["subpilar_atual_v2"],
                    "tipo_v2": r["tipo_v2"],
                    "subpilar_v3": r["subpilar_v3"],
                    "tipo_v3": r["tipo_v3"],
                    "confianca_v3": r.get("confianca_v3"),
                    "justificativa_v3": r.get("justificativa_v3", ""),
                    "meu_voto": "",  # Alexandre preenche: v3 | v2 | ambíguo
                    "comentario": "",  # campo livre
                }
            )

    df_out = pd.DataFrame(linhas)
    df_out.to_excel(XLSX_OUT, index=False)
    print()
    print(f"OK — {len(df_out)} linhas em {XLSX_OUT}")
    print("\nDistribuição final por bucket:")
    print(df_out["bucket"].value_counts().to_string())
    print("\nDistribuição por (subpilar_v2 → subpilar_v3):")
    print(df_out.groupby(["subpilar_v2", "subpilar_v3"]).size().to_string())


if __name__ == "__main__":
    main()
