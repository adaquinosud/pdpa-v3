"""Extrai LITERALMENTE o capítulo "Marcas de leitura de documento" do Manual de Operação
(as marcas do balizador) para src/avaliador/dados/marcas.json.

O capítulo é achado pelo TÍTULO, não pelo número (do v11 ao v13 é o 17; o Manual já teve
subseções numeradas como se fossem capítulo, e um capítulo novo no meio renumera os
seguintes). Termina no próximo título de capítulo ou em "Sobre a Loyall".

Como no capítulo 2, o .docx não vai para a imagem: a ferramenta lê este extrato
versionado, e tests/test_avaliador_marcas.py compara extrato e .docx sempre que o .docx
existe na máquina. Mudou o Manual → rode de novo:

    PYTHONPATH=. .venv/bin/python scripts/extrair_marcas.py

Desde o v14 (22/10), o capítulo traz, debaixo de cada subpilar, a pergunta na voz do leitor
("Pergunta do leitor: …") e, no fim de cada marca, o nome curto ("(nome curto: …)"), que é
como a marca aparece na página da frente do parecer. O nome curto NÃO faz parte do texto da
marca: o modelo lê a marca sem ele.

O "porque importa" de cada marca ainda não está no Manual (decisão de 18/10: escrito
depois de as marcas estabilizarem). O campo nasce vazio; quando o Manual o trouxer, é
este script que passa a lê-lo.
"""

import json
import re
import sys
from pathlib import Path

import docx

from src.api.painel import NOME_SUBPILAR

DOCX = Path("data/PDPA_Manual_Operacao_v14.docx")
SAIDA = Path("src/avaliador/dados/marcas.json")
TITULO = "Marcas de leitura de documento"
FORA_DOS_DOZE = "O que dá para conferir na peça"
GRUPO_FORA = "C"
EXCECOES = "Só se esperam em peça feita para um cliente com nome:"
SUBTITULOS_IGNORADOS = {"Exceções"}
PERGUNTA_LEITOR = "Pergunta do leitor: "

_CAPITULO = re.compile(r"^\d+\. \S")
_PILAR = re.compile(r"^Pilar (\d) — (.+)$")
_SUB = re.compile(r"^(P[123]|D[123]|Pa[123]|A[123]) — (.+)$")
_MARCA = re.compile(r"^((P[123]|D[123]|Pa[123]|A[123]|C)\.(\d\d)) (.+)$")
_NOME_CURTO = re.compile(r"^(.+\?) \(nome curto: ([^()]+)\)$")
_PILARES = ("P", "D", "Pa", "A")


def extrair(caminho: Path) -> dict:
    ps = [p.text.strip() for p in docx.Document(str(caminho)).paragraphs]
    titulo = next((t for t in ps if re.fullmatch(rf"\d+\. {TITULO}", t)), None)
    if titulo is None:
        raise SystemExit(f"capítulo '{TITULO}' não encontrado em {caminho.name}")
    ini = ps.index(titulo)
    fim = next(
        i for i in range(ini + 1, len(ps)) if _CAPITULO.match(ps[i]) or ps[i] == "Sobre a Loyall"
    )
    depois_do_titulo = ps[:fim][ini:]
    bloco = [t for t in depois_do_titulo[1:] if t]
    out = {
        "fonte": f"{caminho.name}, capítulo {titulo.split('.')[0]}",
        "titulo": titulo,
        "abertura": [],
        "pilares": [],
        "fora_dos_doze": None,
        "perguntas_leitor": {},
        "marcas": [],
    }
    grupo = None  # subpilar (ou C) cujas marcas estão sendo lidas
    esperando = None  # "pergunta do pilar" | "descrição do bloco C"
    excecoes = None
    for t in bloco:
        if excecoes is not None:
            raise SystemExit(f"parágrafo depois das exceções: {t!r}")
        if esperando == "pilar":
            out["pilares"][-1]["pergunta"] = t
            esperando = None
            continue
        if esperando == "fora":
            out["fora_dos_doze"]["descricao"] = t
            esperando = None
            continue
        if m := _PILAR.match(t):
            n = int(m.group(1))
            out["pilares"].append({"codigo": _PILARES[n - 1], "titulo": t, "pergunta": None})
            esperando, grupo = "pilar", None
        elif t.startswith(PERGUNTA_LEITOR):
            if grupo not in NOME_SUBPILAR or grupo in out["perguntas_leitor"]:
                raise SystemExit(f"pergunta do leitor fora de um subpilar: {t!r}")
            out["perguntas_leitor"][grupo] = t.removeprefix(PERGUNTA_LEITOR)
        elif m := _SUB.match(t):
            grupo = m.group(1)
            if NOME_SUBPILAR[grupo] != m.group(2):
                raise SystemExit(
                    f"{grupo}: o capítulo diz {m.group(2)!r}, o modelo diz {NOME_SUBPILAR[grupo]!r}"
                )
        elif t == FORA_DOS_DOZE:
            out["fora_dos_doze"] = {"titulo": t, "descricao": None}
            esperando, grupo = "fora", GRUPO_FORA
        elif m := _MARCA.match(t):
            if m.group(2) != grupo:
                raise SystemExit(f"marca {m.group(1)} fora do seu subpilar (lendo {grupo})")
            n = _NOME_CURTO.match(m.group(4))
            if n is None:
                raise SystemExit(f"marca {m.group(1)} sem nome curto: {t!r}")
            out["marcas"].append(
                {
                    "codigo": m.group(1),
                    "grupo": grupo,
                    "texto": n.group(1),
                    "nome_curto": n.group(2).strip(),
                    "so_cliente_nomeado": False,
                    "porque_importa": "",
                }
            )
        elif t.startswith(EXCECOES):
            excecoes = [c.strip() for c in t.removeprefix(EXCECOES).rstrip(".").split(",")]
        elif t in SUBTITULOS_IGNORADOS:
            continue
        elif not out["pilares"]:
            out["abertura"].append(t)
        else:
            raise SystemExit(f"parágrafo inesperado no capítulo: {t!r}")
    com_marca = dict.fromkeys(x["grupo"] for x in out["marcas"] if x["grupo"] != GRUPO_FORA)
    faltam = [g for g in com_marca if g not in out["perguntas_leitor"]]
    if faltam:
        raise SystemExit(f"subpilar sem pergunta do leitor: {faltam}")
    if excecoes is None:
        raise SystemExit(f"o capítulo não tem o parágrafo '{EXCECOES}'")
    por_codigo = {x["codigo"]: x for x in out["marcas"]}
    for c in excecoes:
        if c not in por_codigo:
            raise SystemExit(f"exceção {c} não é marca do capítulo")
        por_codigo[c]["so_cliente_nomeado"] = True
    return out


if __name__ == "__main__":
    dados = extrair(DOCX)
    SAIDA.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    n = len(dados["marcas"])
    fora = sum(1 for x in dados["marcas"] if x["grupo"] == GRUPO_FORA)
    exc = sum(1 for x in dados["marcas"] if x["so_cliente_nomeado"])
    print(
        f"{SAIDA}: {n - fora} marcas nos doze subpilares, {fora} fora, {exc} exceções",
        file=sys.stderr,
    )
