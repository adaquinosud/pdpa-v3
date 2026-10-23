"""Extrai a biblioteca de frases do parecer (o "por que custa", escrita pelo Alexandre em
11/10, podada e ligada às marcas em 23/10) para src/avaliador/dados/biblioteca_frases.json.

A fonte é um .md fora do repositório (~/Documents/PDPA-pareceres/biblioteca-podada.md). Cada
frase é um título em negrito com código, estado e, quando vale no Word, a quais marcas serve,
e o texto na linha seguinte:

    **P1.1 · WORD · serve a: como e em que prazo**
    Enquanto não está escrito, o prazo que vale é o que o cliente imaginou, ...

Estados: WORD (vai ao Word), SÓ NA TELA (pressupõe que a peça diga algo: nunca vai ao Word),
CLIENTE NOMEADO (vai ao Word só em peça com cliente nomeado) e CORTADA (não entra no arquivo
de dados, como pede a própria biblioteca). As marcas do "serve a" são os nomes curtos do
Manual; ``src/avaliador/biblioteca.py`` confere contra marcas.json ao carregar.

    PYTHONPATH=. .venv/bin/python scripts/extrair_biblioteca.py [caminho do .md]
"""

import json
import re
import sys
from pathlib import Path

FONTE = Path.home() / "Documents/PDPA-pareceres/biblioteca-podada.md"
SAIDA = Path("src/avaliador/dados/biblioteca_frases.json")
ESTADOS = {
    "WORD": "word",
    "SÓ NA TELA": "tela",
    "CLIENTE NOMEADO": "cliente_nomeado",
    "CORTADA": "cortada",
}
QUALQUER = "qualquer"
TITULO = re.compile(
    r"^\*\*(?P<codigo>(?P<sub>P|D|Pa|A)\d)\.(?P<n>\d+) · (?P<estado>[^·*]+?)"
    r"(?: · serve a: (?P<serve>[^*]+))?\*\*"
)


def extrair(texto: str) -> list:
    linhas = texto.splitlines()
    frases, erros = [], []
    for i, linha in enumerate(linhas):
        m = TITULO.match(linha)
        if not m:
            continue
        cod = f"{m['codigo']}.{m['n']}"
        estado = ESTADOS.get(m["estado"].strip())
        if estado is None:
            erros.append(f"{cod}: estado desconhecido {m['estado']!r}")
            continue
        corpo = []
        for seguinte in linhas[i + 1 :]:  # noqa: E203
            if not seguinte.strip():
                break
            if not seguinte.startswith("*"):  # nota em itálico: o porquê, não a frase
                corpo.append(seguinte.strip())
        if len(corpo) != 1:
            erros.append(f"{cod}: esperava uma linha de texto, achei {len(corpo)}")
            continue
        serve = (m["serve"] or "").strip()
        if estado in ("word", "cliente_nomeado") and not serve:
            erros.append(f"{cod}: vai ao Word e não diz a quais marcas serve")
        if estado == "cortada":
            continue
        frases.append(
            {
                "codigo": cod,
                "subpilar": m["codigo"],
                "estado": estado,
                "serve_a": (
                    None
                    if serve in ("", QUALQUER)
                    else [x.strip() for x in serve.split(",") if x.strip()]
                ),
                "texto": corpo[0],
            }
        )
    if erros:
        sys.exit("PARE:\n  " + "\n  ".join(erros))
    return frases


def main():
    fonte = Path(sys.argv[1]) if len(sys.argv) > 1 else FONTE
    frases = extrair(fonte.read_text(encoding="utf-8"))
    SAIDA.write_text(
        json.dumps(
            {"fonte": f"{fonte.name}, podada e ligada às marcas em 23/10/2026", "frases": frases},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    por = {}
    for f in frases:
        por[f["estado"]] = por.get(f["estado"], 0) + 1
    print(f"{len(frases)} frases em {SAIDA}: {por}")


if __name__ == "__main__":
    main()
