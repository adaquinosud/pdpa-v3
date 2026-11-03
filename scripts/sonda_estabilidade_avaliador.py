"""Probe SÓ-LEITURA: quadro da repetibilidade do Avaliador pelas leituras gravadas (03/nov).

Uso (Shell do Render):  IDS=24,25,26 PYTHONPATH=. python scripts/sonda_estabilidade_avaliador.py

$0: nenhuma chamada LLM, nenhuma escrita. Não imprime trecho da peça, só código de marca e estado.

Remonta a medição de 19/10 (§6 do Contexto-Mestre) com o mesmo critério do script de então:
o estado da tela de cada marca (está / sem conferência / não está, ``_estado_marca``) igual em
todas as leituras. As marcas saem do que está GRAVADO em cada leitura (régua v25, 87 marcas), não
da régua de hoje (v27, 79): régua mudou depois, a leitura não.

``INTERPRETATIVAS`` e ``EXCECOES`` são as listas de 19/10 copiadas do script de medição (a lista de
interpretativas não vive no código do app, §6). A Pa3.03 entrou na lista depois (21/10, 12
marcas); aqui fica fora de propósito, porque a medição de 19/10 contou com 11.

O braço de controle de 21/10 (cinco leituras, 96,1% na média dos trios) NÃO sai daqui: rodou com a
régua em memória e não gravou nada no banco.
"""

import itertools
import json
import os

from src.avaliador.servico import _estado_marca
from src.models.avaliador import AvaliadorAnalise
from src.utils.db import db_session
from src.utils.fmt import virg

IDS = [int(x) for x in os.environ.get("IDS", "24,25,26").split(",") if x.strip()]
INTERPRETATIVAS = {
    "D3.04", "Pa1.01", "Pa1.03", "Pa1.04", "A2.01", "A2.02", "A2.03", "A2.04",
    "A3.01", "A3.02", "A3.04",
}  # fmt: skip
EXCECOES = {"Pa1.05", "Pa1.07", "Pa2.03", "Pa2.04", "Pa2.09"}  # só com cliente nomeado
CURTO = {"esta": "está", "sem_conferencia": "sem conf.", "nao_esta": "não está"}


def _pct(a, b):
    return f"{virg(100 * a / b, 1)}%" if b else "—"


with db_session() as s:
    ls = [s.get(AvaliadorAnalise, i) for i in IDS]
    if any(a is None for a in ls):
        raise SystemExit(f"leitura inexistente entre {IDS}")
    print("== LEITURAS")
    estado = {}
    for a in ls:
        print(
            f"  #{a.id} {a.criado_em:%d/%m/%Y %H:%M} UTC | {a.status} | {a.prompt_versao} |",
            f"régua {a.regua_versao} | peça {a.conteudo_hash[:12]} | {a.n_paginas} págs |",
            f"cliente_nomeado={a.cliente_nomeado} | US$ {virg(a.custo_usd, 4)}",
        )
        for m in json.loads(a.itens_json or "{}").get("marcas", []):
            estado.setdefault(m["codigo"], {})[a.id] = _estado_marca(m)
    pecas = {a.conteudo_hash for a in ls}
    reguas = {a.regua_versao for a in ls}
    print(f"  peças distintas: {len(pecas)}; réguas distintas: {len(reguas)}")

    codigos = sorted(estado)
    incompletas = [c for c in codigos if len(estado[c]) != len(ls)]
    print("")
    print("== QUADRO (critério: mesmo estado da tela em todas as leituras)")
    print(
        f"marcas gravadas: {len(codigos)}; ausentes em alguma leitura: {incompletas or 'nenhuma'}"
    )
    grupos = {
        "não interpretativas": [c for c in codigos if c not in INTERPRETATIVAS],
        "interpretativas": [c for c in codigos if c in INTERPRETATIVAS],
    }
    for nome, cs in grupos.items():
        mudaram = [c for c in cs if len(set(estado[c].values())) > 1]
        iguais = len(cs) - len(mudaram)
        print(
            f"  {nome}: {len(cs)} | iguais {iguais} = {_pct(iguais, len(cs))} |",
            f"mudaram {len(mudaram)}",
        )
    print(f"  das não interpretativas, exceções (só com cliente nomeado): {sorted(EXCECOES)}")

    if len(ls) > 3:  # mesma conta do braço de controle: média dos trios
        gerais = grupos["não interpretativas"]
        trios = list(itertools.combinations([a.id for a in ls], 3))
        media = sum(
            sum(1 for c in gerais if len({estado[c][i] for i in t}) == 1) / len(gerais)
            for t in trios
        ) / len(trios)
        print(f"  média dos {len(trios)} trios (não interpretativas): {virg(100 * media, 1)}%")

    print("")
    print("== ONDE CAIU CADA MUDANÇA")
    for c in codigos:
        if len(set(estado[c].values())) > 1:
            grupo = "interpretativa" if c in INTERPRETATIVAS else "não interpretativa"
            seq = [CURTO.get(estado[c].get(a.id), "—") for a in ls]
            extra = ", exceção" if c in EXCECOES else ""
            print(f"  {c} ({grupo}{extra}): {seq}")
