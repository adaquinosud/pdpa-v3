"""Gate do 5a (O5a-1): valida o classificador-cliente na voz INVERTIDA do
colaborador. Roda classificar() numa amostra representativa e imprime
subpilar/valência por caso, com a expectativa, para revisão humana.

Uso: set -a; source .env; set +a; python scripts/validar_voz_colaborador.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.classifier.classifier_v3 import classificar  # noqa: E402

# (comentário do colaborador, categoria de risco, expectativa de direção)
AMOSTRA = [
    (
        "A gente sempre resolve rápido o problema do cliente já no primeiro contato.",
        "auto-elogio",
        "D2 / promotor",
    ),
    (
        "Nosso time atende com muita atenção e paciência cada pessoa.",
        "auto-elogio",
        "Pa1 / promotor",
    ),
    (
        "Orientamos cada cliente com precisão técnica antes de fechar a compra.",
        "auto-elogio",
        "A2 / promotor",
    ),
    (
        "Demoramos demais para retornar os chamados, isso precisa melhorar.",
        "auto-crítica",
        "D2 / detrator",
    ),
    ("Cada loja faz de um jeito, não temos um padrão único.", "auto-crítica", "P3 / detrator"),
    ("A gente faz o que pode com os recursos que temos.", "defensivo/neutro", "ambíguo (RISCO)"),
    (
        "Falta gente no time e o sistema interno é lento pra nós.",
        "queixa interna",
        "não é exp. do cliente (RISCO)",
    ),
    (
        "O cliente reclama do prazo, mas a gente cumpre o que foi combinado.",
        "defensivo invertido",
        "RISCO de inversão",
    ),
]


def main() -> int:
    print(f"{'categoria':<22} {'esperado':<28} {'→ classificado':<22} conf")
    print("-" * 82)
    for texto, categoria, esperado in AMOSTRA:
        try:
            r = classificar(texto)
            got = f"{r.subpilar} / {r.tipo}"
            conf = f"{r.confianca:.2f}"
        except Exception as exc:  # noqa: BLE001
            got, conf = f"ERRO: {exc}", "—"
        print(f"{categoria:<22} {esperado:<28} {got:<22} {conf}")
        print(f"    «{texto}»")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
