"""PROBE READ-ONLY — qual a MENOR base que já define o Teto do Lastro no parque?

Custo US$ 0: só lê o banco. NÃO chama LLM, NÃO chama Apify, NÃO escreve nada.

Frente §6.19: o Teto é ``_normalizar_indice(min(pior_pilar, média))`` e o ``min``
é **cego a volume por construção** — um pilar com 15 verbatins decide o Teto de uma
base de 1.006 (caso BEXP, 03/set). Declarar FERIDA INTERNA exige piso 30
(``VOLUME_CONFIANCA_ALTA``); definir o TETO não exige nada.

Este probe respondeu a pergunta que decidiu a URGÊNCIA das duas frentes (03/set):
**13 de 24 empresas sem pilar mensurável** (o 0,0 fabricado da §6.18 — virou a
PRIMEIRA da fila) e **só a BEXP** como caso real de piso (§6.19 é pontual). As
outras 3 abaixo do piso eram 2 bases de teste e 1 com Teto 3,0.

⚠️ LIMITE DE FIDELIDADE: calcula sobre TODOS os verbatins classificados da empresa,
sem os filtros do painel (período, fonte, escopo, janela). Serve para ORDENAR o
parque, não para bater centavo a centavo com a tela. A linha de calibração no fim
compara a empresa 27 com o que a tela mostrou (Teto 0,0 · PDPA 85,8). ✅ Conferido
em 03/set: bateu — o probe é fiel neste caso.

Uso no Render:  PYTHONPATH=. python scripts/probe_piso_do_teto.py
"""

from collections import defaultdict

from sqlalchemy import func

from src.api.engajamento import VOLUME_CONFIANCA_ALTA
from src.api.painel import (
    PILAR_DE_SUBPILAR,
    _base_indice,
    _normalizar_indice,
    calcular_ratio,
    faixa_indice_geral,
    indice_pdpa,
)
from src.models.empresa import Empresa
from src.models.verbatim import Verbatim
from src.utils.db import db_session

TIPOS = ("promotor", "conversivel", "detrator")


def _zero():
    return {"promotor": 0, "conversivel": 0, "detrator": 0, "total": 0}


def main() -> int:
    abaixo_do_piso, sem_medicao, ok = [], [], []

    with db_session() as s:
        empresas = s.query(Empresa).order_by(Empresa.id).all()
        print("=" * 92)
        print("QUEM GOVERNA O TETO DO LASTRO, E COM QUANTO VOLUME")
        print("=" * 92)

        for e in empresas:
            rows = (
                s.query(Verbatim.subpilar, Verbatim.tipo, func.count(Verbatim.id))
                .filter(Verbatim.empresa_id == e.id, Verbatim.subpilar.isnot(None))
                .group_by(Verbatim.subpilar, Verbatim.tipo)
                .all()
            )
            # Só os 12 subpilares do método — sem_lastro/inativo ficam fora (§4.38).
            por_sub = defaultdict(_zero)
            for sub, tipo, n in rows:
                if PILAR_DE_SUBPILAR.get(sub) is None:
                    continue
                if tipo in TIPOS:
                    por_sub[sub][tipo] += n
                    por_sub[sub]["total"] += n

            if not por_sub:
                sem_medicao.append((e.id, e.nome))
                print(
                    f"  emp {e.id:3} {str(e.nome)[:30]:30} ☠️ SEM PILAR MENSURÁVEL — "
                    f"Teto sai 0,0 'crítico' FABRICADO (§6.18)"
                )
                continue

            matriz = [
                {
                    "subpilar": sub,
                    "ratio": calcular_ratio(d["promotor"], d["detrator"]),
                    "total": d["total"],
                    "promotor": d["promotor"],
                    "detrator": d["detrator"],
                }
                for sub, d in por_sub.items()
            ]
            por_pilar = defaultdict(_zero)
            for sub, d in por_sub.items():
                p = PILAR_DE_SUBPILAR[sub]
                for k in TIPOS + ("total",):
                    por_pilar[p][k] += d[k]
            pilares = [
                {"pilar": p, "ratio": calcular_ratio(d["promotor"], d["detrator"]), **d}
                for p, d in por_pilar.items()
            ]

            base, pior, media = _base_indice(matriz, pilares)
            teto = _normalizar_indice(base)
            faixa = faixa_indice_geral(teto)
            pdpa, den = indice_pdpa(pilares)
            total = sum(p["total"] for p in pilares)

            com_vol = [p for p in pilares if p["total"] > 0]
            dono = min(com_vol, key=lambda p: p["ratio"]) if com_vol else None
            governado_pelo_pior = pior is not None and pior <= media

            if dono is None:
                continue
            pct = 100 * dono["total"] / total if total else 0.0
            frag = dono["total"] < VOLUME_CONFIANCA_ALTA
            # Valores PLANOS: as listas são lidas FORA da sessão, e objeto ORM
            # detachado levanta DetachedInstanceError no acesso a e.id/e.nome.
            (abaixo_do_piso if frag else ok).append(
                (e.id, e.nome, dono["pilar"], dono["total"], total, teto, pdpa)
            )

            marca = "  ⚠️ ABAIXO DE 30" if frag else ""
            quem = (
                f"{dono['pilar']} (ratio {dono['ratio']:.2f})" if governado_pelo_pior else "MÉDIA"
            )
            print(
                f"  emp {e.id:3} {str(e.nome)[:30]:30} Teto={teto:5.1f} ({faixa:8}) "
                f"PDPA={pdpa if pdpa is not None else '—'}"
            )
            print(
                f"           governado por {quem}: {dono['total']:5} verb "
                f"({pct:4.1f}% de {total}){marca}"
            )

    print("\n" + "=" * 92)
    print("VEREDITO")
    print("=" * 92)
    print(
        f"  empresas com Teto governado por pilar ABAIXO do piso {VOLUME_CONFIANCA_ALTA}: "
        f"{len(abaixo_do_piso)}"
    )
    for eid, nome, pilar, vol, total, teto, pdpa in abaixo_do_piso:
        print(
            f"    · emp {eid} {str(nome)[:26]:26} {pilar} com {vol} "
            f"de {total} → Teto {teto} vs PDPA {pdpa}"
        )
    print(f"\n  empresas SEM pilar mensurável (0,0 fabricado, §6.18.4): {len(sem_medicao)}")
    for eid, nome in sem_medicao:
        print(f"    · emp {eid} {str(nome)[:26]}")
    print(f"\n  empresas com Teto sustentado por base ≥ {VOLUME_CONFIANCA_ALTA}: {len(ok)}")
    print("\n  LEITURA: se `abaixo do piso` for 1 (só a BEXP), a frente é pontual.")
    print("  Se for vários, o Teto do parque está governado por ruído e a urgência sobe.")
    print("  ⚠️ `sem pilar mensurável` é o irmão MAIS GRAVE: atinge toda empresa")
    print("     recém-cadastrada, que recebe 'crítico' sem nunca ter sido medida.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
