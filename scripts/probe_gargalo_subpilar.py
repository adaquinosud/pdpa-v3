"""Probe SÓ-LEITURA: gargalo de cada empresa — regra ATUAL × regra SEQUENCIAL nova
(subpilar crítico com volume ≥ piso também quebra o pilar), para cada piso candidato.

Uso (Shell do Render):  PYTHONPATH=. python scripts/probe_gargalo_subpilar.py      (todas)
                        PYTHONPATH=. python scripts/probe_gargalo_subpilar.py 29   (uma)

$0: nenhuma chamada LLM, nenhuma escrita. Mesmo agg dos impressos
(``agregar_subpilares(s, eid, None)``, all-time, escopo empresa).

Régua usada (a do código, não reescrita): crítico = ``ratio < 0,5`` (FAIXAS_RATIO);
volume do subpilar = ``total`` (prom+conv+det — o mesmo campo do piso da ferida interna,
src/api/painel.py:572). Subpilar sem sinal P/D (prom+det=0) não conta.

Regra SEQUENCIAL (decidida): pilar com QUEBRA CRÍTICA = soma < 0,5 OU subpilar crítico
com total ≥ piso; ganha o 1º na ordem P → D → Pa → A. Senão, 1º pilar FRACO pela soma.
Senão, None.

A coluna ``lit≠`` marca, só como referência, onde a redação literal (subpilar crítico ≥
piso passa na frente de pilar anterior crítico pela soma) daria outro pilar.
"""

import sys

from src.api.painel import (
    PILAR_DE_SUBPILAR,
    PILARES_ORDEM,
    SUBPILARES_ORDEM,
    gargalo_sequencial,
    ratios_por_pilar,
)
from src.diagnostico.leituras import agregar_subpilares
from src.models.empresa import Empresa
from src.utils.db import db_session

PISOS = (1, 10, 30)  # 1 = sem piso (qualquer volume com sinal); 10/30 = selo médio/alto


def subs_criticos(agg, piso):
    return [
        sub
        for sub in SUBPILARES_ORDEM
        if sub in agg
        and (agg[sub]["prom"] + agg[sub]["det"]) > 0
        and agg[sub]["ratio"] < 0.5
        and agg[sub]["total"] >= piso
    ]


def regra_sequencial(agg, piso):
    rp = ratios_por_pilar(agg)
    pil = {PILAR_DE_SUBPILAR[s] for s in subs_criticos(agg, piso)}
    for p in PILARES_ORDEM:
        if p in pil or (p in rp and rp[p] < 0.5):
            return p
    fracos = [p for p in PILARES_ORDEM if p in rp and rp[p] < 1.0]
    return fracos[0] if fracos else None


def regra_literal(agg, piso):
    pil = {PILAR_DE_SUBPILAR[s] for s in subs_criticos(agg, piso)}
    for p in PILARES_ORDEM:
        if p in pil:
            return p
    return gargalo_sequencial(agg)


def fmt(x):
    return x or "—"


def main():
    so = int(sys.argv[1]) if len(sys.argv) > 1 else None
    with db_session() as s:
        q = s.query(Empresa.id, Empresa.nome).order_by(Empresa.id)
        if so:
            q = q.filter(Empresa.id == so)
        empresas = q.all()
        cab = ["emp", "atual"] + [f"piso{p}" for p in PISOS] + ["lit≠", "nome"]
        print("\t".join(cab))
        com_agg = 0
        mudam = {p: [] for p in PISOS}
        detalhe = []
        for eid, nome in empresas:
            agg = agregar_subpilares(s, eid, None)
            if not agg:
                continue
            com_agg += 1
            atual = gargalo_sequencial(agg)
            novos = {p: regra_sequencial(agg, p) for p in PISOS}
            lit = [str(p) for p in PISOS if novos[p] != regra_literal(agg, p)]
            for p in PISOS:
                if novos[p] != atual:
                    mudam[p].append(eid)
            linha = [str(eid), fmt(atual)] + [fmt(novos[p]) for p in PISOS]
            linha += [",".join(lit), (nome or "")[:40]]
            print("\t".join(linha))
            crit = subs_criticos(agg, 1)
            if crit and (so or any(novos[p] != atual for p in PISOS)):
                detalhe.append((eid, ratios_por_pilar(agg), [(c, agg[c]) for c in crit]))
        print()
        print(f"empresas consultadas: {len(empresas)}; com agg (na tabela): {com_agg}")
        for p in PISOS:
            ids = ",".join(map(str, mudam[p])) or "—"
            print(f"piso {p:>2}: gargalo muda em {len(mudam[p])} de {com_agg}  [emp {ids}]")
        print()
        print("detalhe (subpilares críticos, ratio < 0,5, sem piso — de quem muda em algum piso):")
        for eid, rp, crit in detalhe:
            pil = " ".join(f"{p}={rp[p]:.2f}".replace(".", ",") for p in PILARES_ORDEM if p in rp)
            print(f"  emp {eid}  pilares: {pil}")
            for c, d in crit:
                print(
                    f"    {c}: ratio {d['ratio']:.2f}".replace(".", ",")
                    + f"  prom {d['prom']}  conv {d['conv']}  det {d['det']}  total {d['total']}"
                )


if __name__ == "__main__":
    main()
