"""Extrai LITERALMENTE o capítulo 2 do Manual de Operação (os 4 pilares e 12 subpilares)
para src/avaliador/dados/manual_cap2.json — a régua do Avaliador.

O .docx não está no git nem na imagem Docker (data/ é excluída), então a ferramenta lê
este extrato versionado. tests/test_avaliador_regua.py compara o extrato com o .docx
sempre que ele existir na máquina e FALHA se divergirem. Mudou o Manual → rode de novo:

    PYTHONPATH=. .venv/bin/python scripts/extrair_manual_cap2.py
"""

import json
import re
import sys
from pathlib import Path

import docx

DOCX = Path("data/PDPA_Manual_Operacao_v12.docx")
SAIDA = Path("src/avaliador/dados/manual_cap2.json")
_SUB = re.compile(r"^(P[123]|D[123]|Pa[123]|A[123]) — ([^:]+): (.+)$")
_PILAR = re.compile(r"^Pilar \d — (.+)$")


def extrair(caminho: Path) -> dict:
    ps = [p.text.strip() for p in docx.Document(str(caminho)).paragraphs]
    ini = ps.index("2. Os 4 pilares e 12 subpilares")
    fim = ps.index("3. O Lastro como jornada relacional")
    bloco = [t for t in ps[ini:fim] if t][1:]  # sem o título do capítulo
    out = {"fonte": f"{caminho.name}, capítulo 2", "abertura": bloco[0], "pilares": []}
    atual = None
    for t in bloco[1:]:
        m = _PILAR.match(t)
        if m:
            atual = {"titulo": t, "nome": m.group(1), "descricao": None, "subpilares": []}
            out["pilares"].append(atual)
            continue
        s = _SUB.match(t)
        if s:
            atual["subpilares"].append(
                {"codigo": s.group(1), "nome": s.group(2), "pergunta": s.group(3), "texto": t}
            )
        elif atual is not None and atual["descricao"] is None:
            atual["descricao"] = t
        else:
            raise SystemExit(f"parágrafo inesperado no capítulo 2: {t!r}")
    return out


if __name__ == "__main__":
    dados = extrair(DOCX)
    SAIDA.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    n = sum(len(p["subpilares"]) for p in dados["pilares"])
    print(f"{SAIDA}: {len(dados['pilares'])} pilares, {n} subpilares", file=sys.stderr)
