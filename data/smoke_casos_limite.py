"""Smoke test dos 3 verbatins de auditoria que casam com casos-limite (Frente 2).

Roda Haiku 4.5 com o prompt v3 + dicionário + casos-limite injetados e
reporta acerto vs esperado.

Custo: 3 chamadas ~$0.002 (negligível).
"""

from __future__ import annotations

from src.classifier.classifier_v3 import classificar


CASOS = [
    {
        "id": "A",
        "padrao_alvo": "Caso-limite 1 (cobrou/aprovou e depois revogou)",
        "texto": (
            "Atendimento pessimo, na central falaram que aprovou o cadastro e "
            "depois que PAGAMOS, foi negado, um absurdo, andamos 60km, PESSIMO, "
            "NAO RECOMENDO PRA NINGUEM"
        ),
        "empresa_nome": "N-Localiza",
        "empresa_setor": "locadora",
        "fonte_tipo": "google",
        "esperado_subpilar": "Pa2",
        "esperado_tipo": "detrator",
    },
    {
        "id": "B",
        "padrao_alvo": "Caso-limite 7 (elogio à qualidade intrínseca)",
        "texto": (
            "Lugar sensacional, com uma qualidade incomparável e preço super "
            "justo. Além disso, conta com happy hour diário, que torna o "
            "ambiente ainda mais atrativo. Vale muito a experiência!"
        ),
        "empresa_nome": "N-CamaraCamarao",
        "empresa_setor": "restaurante",
        "fonte_tipo": "google",
        "esperado_subpilar": "P2",
        "esperado_tipo": "promotor",
    },
    {
        "id": "C",
        "padrao_alvo": "Caso-limite 11 (celebridade nomeada)",
        "texto": "Lendaaaaa Gilberto Gil😍",
        "empresa_nome": "N-Mantiqueira",
        "empresa_setor": "alimentos",
        "fonte_tipo": "instagram",
        "esperado_subpilar": "sem_lastro",
        "esperado_tipo": "inativo",
    },
]


def main() -> None:
    print("=" * 72)
    print("SMOKE — Frente 2 — Casos-limite (3 verbatins reais da auditoria)")
    print("=" * 72)

    acertos = 0
    for caso in CASOS:
        print(f"\n── Caso {caso['id']} | {caso['padrao_alvo']} ──")
        print(f"Verbatim: {caso['texto'][:120]}{'...' if len(caso['texto']) > 120 else ''}")
        print(
            f"Empresa: {caso['empresa_nome']} | "
            f"Setor: {caso['empresa_setor']} | "
            f"Fonte: {caso['fonte_tipo']}"
        )

        try:
            res = classificar(
                caso["texto"],
                empresa_nome=caso["empresa_nome"],
                empresa_setor=caso["empresa_setor"],
                fonte_tipo=caso["fonte_tipo"],
            )
        except Exception as exc:
            print(f"  ❌ ERRO: {exc!r}")
            continue

        ok_sub = res.subpilar == caso["esperado_subpilar"]
        ok_tipo = res.tipo == caso["esperado_tipo"]
        ok = ok_sub and ok_tipo
        if ok:
            acertos += 1

        flag = "✅ ACERTOU" if ok else "❌ ERROU"
        print(f"  Retornado: {res.subpilar}/{res.tipo} (confianca={res.confianca:.2f})")
        print(f"  Esperado : {caso['esperado_subpilar']}/{caso['esperado_tipo']}")
        print(f"  Justificativa: {res.justificativa}")
        print(f"  Resultado: {flag}")

    print("\n" + "=" * 72)
    print(f"SCORE: {acertos}/{len(CASOS)} acertos")
    print("=" * 72)


if __name__ == "__main__":
    main()
