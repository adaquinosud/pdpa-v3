#!/usr/bin/env python
"""Medição READ-ONLY do estágio de rotulagem de um bucket de temas.

Diagnóstico: por que tantos verbatins ficam sem tema? Esta ferramenta clusteriza
um bucket (mesmo motor do pipeline), chama o rotulador por cluster pra ver o que
ele DESCARTA (``nome=null``), e usa um juiz LLM pra separar os descartados em
COERENTES (tema real perdido) vs GENÉRICOS (elogio/queixa sem aspecto nomeável).

NÃO PERSISTE NADA. Só faz SELECT (verbatins + embeddings); clusteriza em memória;
NÃO cria/zera ``temas_cache``, NÃO cria/remove ``verbatim_temas``, NÃO altera
classificação. O único efeito externo é mandar textos ao Haiku (rotulador + juiz),
exatamente como o pipeline normal já faz na rotulagem. Custo LLM ~$0.02/bucket.

Uso (no shell do Render, a partir de /app)::

    PYTHONPATH=. python scripts/medir_rotulagem.py \
        --empresa 16 --subpilar Pa1 --tipo conversivel

Opções:
    --agrupamento N   força um agrupamento específico (default: o MAIOR bucket
                      desse subpilar:tipo).
    --amostra K       quantos textos reais mostrar por cluster (default 10).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict

import numpy as np

from src.classifier.classifier_v3 import _get_client
from src.temas.clusterer import clusterizar_bucket, pick_representativos
from src.temas.embeddings import carregar_embeddings
from src.temas.pipeline import _carregar_verbatins_empresa
from src.temas.rotulador import HAIKU_MODEL, REPS_PARA_ROTULAGEM, rotular_cluster

_JUIZ_SYS = (
    "Você recebe um conjunto de verbatins que foram agrupados por similaridade "
    "semântica, mas o rotulador não conseguiu nomear o cluster. Decida se existe "
    "UM tema/aspecto concreto recorrente (ex: atendimento, comida, preço, fila, "
    "limpeza, espera, estacionamento) — MESMO que expresso como elogio — ou se é "
    "só elogio/queixa genérica sem aspecto ('muito bom', 'excelente', 'top', "
    "'péssimo'), saudação, emoji ou texto ininteligível. Responda JSON PURO "
    '(sem markdown): {"coerente": true|false, "tema": "<2-3 palavras>"|null}.'
)


def _setor_empresa(empresa_id: int):
    from src.models.empresa import Empresa
    from src.utils.db import db_session

    with db_session() as s:  # SELECT apenas
        e = s.get(Empresa, empresa_id)
        return (e.setor if e else None), (e.nome if e else None)


def _juiz_coerencia(textos: list[str]) -> dict:
    """Juiz LLM: o cluster descartado tem tema real ou é genérico? Read-only."""
    client = _get_client()
    payload = json.dumps({"verbatins": textos[:12]}, ensure_ascii=False)
    try:
        resp = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=80,
            system=[{"type": "text", "text": _JUIZ_SYS, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": payload}],
        )
        raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        ini, fim = raw.find("{"), raw.rfind("}") + 1
        d = json.loads(raw[ini:fim])
        return {"coerente": bool(d.get("coerente")), "tema": d.get("tema")}
    except Exception as exc:  # noqa: BLE001
        return {"coerente": None, "tema": f"<juiz falhou: {type(exc).__name__}>"}


def _amostra_textos(membros, pos, k):
    step = max(1, len(pos) // k)
    return [" ".join((membros[i]["texto"] or "").split()) for i in list(pos[::step])[:k]]


def main() -> int:
    ap = argparse.ArgumentParser(description="Medição read-only da rotulagem de um bucket.")
    ap.add_argument("--empresa", type=int, required=True)
    ap.add_argument("--subpilar", required=True)
    ap.add_argument("--tipo", required=True)
    ap.add_argument("--agrupamento", type=int, default=None)
    ap.add_argument("--amostra", type=int, default=10)
    args = ap.parse_args()

    setor, nome = _setor_empresa(args.empresa)
    print(f"# READ-ONLY — não grava nada. empresa={args.empresa} {nome!r} setor={setor}")

    verbs = _carregar_verbatins_empresa(args.empresa)  # SELECT; corte=None (tudo)
    alvo = [v for v in verbs if v["subpilar"] == args.subpilar and v["tipo"] == args.tipo]
    if not alvo:
        print(f"nenhum verbatim em {args.subpilar}:{args.tipo} (com texto).")
        return 1

    por_ag = defaultdict(list)
    for v in alvo:
        por_ag[v["agrupamento_id"]].append(v)
    print(f"# {args.subpilar}:{args.tipo} — distribuição por agrupamento:")
    for ag, ms in sorted(por_ag.items(), key=lambda kv: -len(kv[1])):
        print(f"#   agrupamento={ag}: {len(ms)} verbatins")

    if args.agrupamento is not None:
        ag, membros = args.agrupamento, por_ag.get(args.agrupamento, [])
    else:
        ag, membros = max(por_ag.items(), key=lambda kv: len(kv[1]))
    if not membros:
        print(f"agrupamento {ag} vazio para esse bucket.")
        return 1

    emb = carregar_embeddings([m["id"] for m in membros])  # SELECT
    membros = [m for m in membros if m["id"] in emb]
    if not membros:
        print("nenhum membro com embedding — rode temas-embed antes.")
        return 1
    vetores = np.stack([emb[m["id"]] for m in membros]).astype(np.float32)
    print(f"\n# BUCKET escolhido: agrupamento={ag} | {len(membros)} membros com embedding")

    res = clusterizar_bucket(vetores, random_state=42)
    print(
        f"# clusterização: algoritmo={res.algoritmo} clusters={res.n_clusters} "
        f"noise={int(res.n_noise)}"
    )

    ag_nome = next((m.get("agrupamento_nome") for m in membros if m.get("agrupamento_nome")), None)
    bucket_ctx = {
        "subpilar": args.subpilar,
        "tipo": args.tipo,
        "setor": setor,
        "agrupamento": ag_nome,
    }

    rotulados, descartados = [], []
    for cid in sorted(set(int(x) for x in res.labels) - {-1}):
        pos = np.where(res.labels == cid)[0]
        rep_pos = pick_representativos(vetores, res.labels, cid, k=REPS_PARA_ROTULAGEM)
        reps = [{"texto": membros[i]["texto"], "verbatim_id": membros[i]["id"]} for i in rep_pos]
        label = rotular_cluster(bucket_ctx, reps)  # LLM, read-only
        if label is None:
            descartados.append((cid, pos))
        else:
            rotulados.append((cid, label, len(pos)))

    print("\n================ ROTULADOS ================")
    for cid, label, n in sorted(rotulados, key=lambda x: -x[2]):
        print(f"  cl{cid:>3} n={n:>3} -> {label!r}")

    print("\n================ DESCARTADOS (rotulador devolveu nome=null) ================")
    coer_vol = gen_vol = 0
    coer_n = gen_n = 0
    for cid, pos in sorted(descartados, key=lambda x: -len(x[1])):
        textos = _amostra_textos(membros, pos, args.amostra)
        veredito = _juiz_coerencia(textos)
        marca = (
            "COERENTE"
            if veredito["coerente"] is True
            else "GENÉRICO" if veredito["coerente"] is False else "INDEF"
        )
        if veredito["coerente"] is True:
            coer_vol += len(pos)
            coer_n += 1
        elif veredito["coerente"] is False:
            gen_vol += len(pos)
            gen_n += 1
        tema = f" tema≈{veredito['tema']!r}" if veredito.get("tema") else ""
        print(f"\n--- cluster {cid} | {len(pos)} membros | [{marca}]{tema} ---")
        for t in textos:
            print(f"  • {t[:170]}")

    print("\n================ RESUMO ================")
    cov = sum(n for _, _, n in rotulados)
    print(f"bucket={args.subpilar}:{args.tipo} ag={ag} membros={len(membros)}")
    print(f"  rotulados: {len(rotulados)} clusters / {cov} verbatins com tema")
    print(
        f"  descartados: {len(descartados)} clusters / {sum(len(p) for _, p in descartados)} "
        f"verbatins sem tema"
    )
    print(f"    COERENTES (tema real perdido): {coer_n} clusters / {coer_vol} verbatins")
    print(f"    GENÉRICOS (cauda sem aspecto): {gen_n} clusters / {gen_vol} verbatins")
    print(f"  ruído (-1): {int(res.n_noise)} verbatins")
    print("\n# Nada foi gravado. Medição puramente de leitura.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
