"""Smoke pós-reauditoria — confirma que D3 digital/automatizada agora classifica.

Os 3 casos abaixo falharam no benchmark anterior (v3.1 disse D1, gabarito v2
diz D3 — e a reauditoria confirmou v2 está certo). Após o reforço do
caso-limite 12 + nota D1 vs D3 no prompt, devem voltar a ser D3.

Custo: 3 chamadas Haiku ~$0.01.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.classifier.classifier_v3 import classificar  # noqa: E402


CASOS = [
    {
        "id": "D3-digital-1",
        "texto": "Laboratório organizado, app mostra resultado no mesmo dia",
        "setor": "saude",
        "fonte": "google",
        "esperado": "D3",
    },
    {
        "id": "D3-digital-2",
        "texto": "Ótimo serviço retira e entrega digital!",
        "setor": "locadora",
        "fonte": "google",
        "esperado": "D3",
    },
    {
        "id": "D3-digital-3",
        "texto": "Ressonância às 22:30, nem sabia que funcionava esse horário",
        "setor": "saude",
        "fonte": "google",
        "esperado": "D3",
    },
]


def main() -> None:
    print("=" * 72)
    print("SMOKE pós-reauditoria — D3 digital/automatizada")
    print("=" * 72)
    acertos = 0
    for caso in CASOS:
        print(f"\n── {caso['id']} ──")
        print(f"  texto: {caso['texto']}")
        print(f"  setor: {caso['setor']} | fonte: {caso['fonte']}")
        try:
            res = classificar(
                caso["texto"],
                empresa_setor=caso["setor"],
                fonte_tipo=caso["fonte"],
            )
        except Exception as exc:
            print(f"  ❌ ERRO: {exc!r}")
            continue
        ok = res.subpilar == caso["esperado"]
        if ok:
            acertos += 1
        flag = "✅ ACERTOU" if ok else "❌ ERROU"
        print(f"  → {res.subpilar}/{res.tipo} conf={res.confianca:.2f} modelo={res.modelo}")
        print(f"  esperado: {caso['esperado']}")
        print(f"  just: {res.justificativa}")
        print(f"  {flag}")

    print()
    print("=" * 72)
    print(f"SCORE: {acertos}/{len(CASOS)} acertos")
    print("=" * 72)


if __name__ == "__main__":
    main()
