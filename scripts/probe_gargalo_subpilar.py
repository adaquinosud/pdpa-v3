"""Probe SÓ-LEITURA: gargalo de cada empresa — regra ATUAL × regra B (subpilar crítico
elege o pilar), para cada piso de volume candidato.

Uso (Shell do Render):  PYTHONPATH=. python scripts/probe_gargalo_subpilar.py      (todas)
                        PYTHONPATH=. python scripts/probe_gargalo_subpilar.py 29   (uma)

$0: nenhuma chamada LLM, nenhuma escrita. Mesmo agg dos impressos
(``agregar_subpilares(s, eid, None)``, all-time, escopo empresa).

Régua usada (a do código, não reescrita): crítico = ``ratio < 0,5`` (FAIXAS_RATIO);
volume do subpilar = ``total`` (o mesmo campo do piso da ferida interna,
src/api/painel.py:572). Subpilar sem sinal P/D (prom+det=0) não conta.

Duas leituras da regra B, porque divergem num caso raro:
  B   = proposta literal: 1º pilar na ordem com subpilar crítico ≥ piso; se nenhum,
        a regra atual inteira (pilar crítico pela soma, depois fraco).
  B'  = unificada: "pilar com quebra crítica" = soma < 0,5 OU subpilar crítico ≥ piso;
        1º na ordem; se nenhum, 1º pilar fraco pela soma.
  Só difere quando um pilar ANTERIOR é crítico pela soma sem ter subpilar ≥ piso
  e um pilar POSTERIOR tem subpilar crítico ≥ piso. A coluna ``B≠B'`` marca.
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


def regra_b(agg, piso):
    pil = {PILAR_DE_SUBPILAR[s] for s in subs_criticos(agg, piso)}
    for p in PILARES_ORDEM:
        if p in pil:
            return p
    return gargalo_sequencial(agg)


def regra_b_unificada(agg, piso):
    rp = ratios_por_pilar(agg)
    pil = {PILAR_DE_SUBPILAR[s] for s in subs_criticos(agg, piso)}
    for p in PILARES_ORDEM:
        if p in pil or (p in rp and rp[p] < 0.5):
            return p
    fracos = [p for p in PILARES_ORDEM if p in rp and rp[p] < 1.0]
    return fracos[0] if fracos else None


def fmt(x):
    return x or "—"


def main():
    so = int(sys.argv[1]) if len(sys.argv) > 1 else None
    with db_session() as s:
        q = s.query(Empresa.id, Empresa.nome).order_by(Empresa.id)
        if so:
            q = q.filter(Empresa.id == so)
        empresas = q.all()
        cab = ["emp", "atual"] + [f"B{p}" for p in PISOS] + ["B≠B'", "nome"]
        print("\t".join(cab))
        mudam = {p: 0 for p in PISOS}
        detalhe = []
        for eid, nome in empresas:
            agg = agregar_subpilares(s, eid, None)
            if not agg:
                continue
            atual = gargalo_sequencial(agg)
            bs = {p: regra_b(agg, p) for p in PISOS}
            div = [str(p) for p in PISOS if bs[p] != regra_b_unificada(agg, p)]
            for p in PISOS:
                mudam[p] += bs[p] != atual
            linha = [str(eid), fmt(atual)] + [fmt(bs[p]) for p in PISOS]
            linha += [",".join(div) or "", (nome or "")[:40]]
            print("\t".join(linha))
            crit = subs_criticos(agg, 1)
            if crit and (so or any(bs[p] != atual for p in PISOS)):
                rp = ratios_por_pilar(agg)
                detalhe.append((eid, rp, [(c, agg[c]) for c in crit]))
        print()
        print(f"empresas consultadas: {len(empresas)} (sem agg ficam fora da tabela)")
        for p in PISOS:
            print(f"piso {p:>2}: gargalo muda em {mudam[p]} empresa(s)")
        print()
        print("detalhe (subpilares crítico, ratio < 0,5, de quem muda em algum piso):")
        for eid, rp, crit in detalhe:
            pil = " ".join(f"{p}={rp[p]:.2f}".replace(".", ",") for p in PILARES_ORDEM if p in rp)
            print(f"  emp {eid}  pilares: {pil}")
            for c, d in crit:
                print(
                    f"    {c}: ratio {d['ratio']:.2f}".replace(".", ",")
                    + f"  prom {d['prom']}  det {d['det']}  total {d['total']}"
                )


if __name__ == "__main__":
    main()
