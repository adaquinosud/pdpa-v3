"""PROBE DESCARTÁVEL — quantos verbatins da Localiza mencionam a SITUAÇÃO que levou
a pessoa a alugar? READ-ONLY, custo US$0 (só lê corpus; NÃO chama LLM).

Mede se o CORPUS pode ser juiz do mapa de Momentos (a IA gera demais, o verbatim
decide quais sobrevivem). Mesma disciplina de medir-antes-de-desenhar que barateou
o experimento 1. Espelha a medição da declaração de permanência (deu 0,9-4,3%).

⚠️ O número por padrão conta MENÇÃO DO TERMO, não SITUAÇÃO DECLARADA — é teto
superior. "aluguei para viajar com a família" (situação) e "a família gostou do
carro" (incidental) ambos casam 'família'. Por isso a seção de EXEMPLOS: ela
calibra a precisão real. Julgar os 20 à mão é o ponto.

Uso no Render:  PYTHONPATH=. python scripts/probe_situacao_localiza.py [empresa_id=17]
Remover após o diagnóstico.
"""

import re
import sys

from src.models.fonte import Fonte
from src.models.verbatim import Verbatim as V
from src.utils.db import db_session

EMPRESA = int(sys.argv[1]) if len(sys.argv) > 1 else 17

# Padrões de SITUAÇÃO (o que levou a alugar). Sugeridos + espaço p/ o corpus revelar
# outros (ver EXEMPLOS não casados no fim). Regex case-insensitive, com acento e sem.
PADROES = {
    "viagem/viajar": r"viag|viaj",
    "trabalho/negócio": r"trabalh|neg[óo]cio|reuni[ãa]o|servi[çc]o\b|a trabalho",
    "família/filhos": r"fam[íi]lia|filho|esposa|marido|crian[çc]a",
    "férias/passeio": r"f[ée]rias|passei|turismo|lazer",
    "oficina/conserto": r"oficina|conserto|quebr|revis[ãa]o|meu carro",
    "aeroporto/avião": r"aeroporto|avi[ãa]o|desembar|voo\b|chegu[eé]i de",
    "mudança": r"mudan[çc]a|mudei|me mud",
    "evento/casamento": r"casamento|evento|festa|formatura",
    "fim de semana": r"fim de semana|final de semana|fds\b",
    "feriado": r"feriad",
}
PAT = {k: re.compile(v, re.IGNORECASE) for k, v in PADROES.items()}
ALGUM = re.compile("|".join(f"(?:{v})" for v in PADROES.values()), re.IGNORECASE)


def _short(t):
    return " ".join((t or "").split())[:170]


with db_session() as s:
    linhas = (
        s.query(V.id, V.texto, V.tipo, Fonte.conector_tipo)
        .outerjoin(Fonte, V.fonte_id == Fonte.id)
        .filter(V.empresa_id == EMPRESA, V.tem_texto.is_(True))
        .all()
    )
    n = len(linhas)
    print(f"=== empresa {EMPRESA}: {n} verbatins com texto ===\n")
    if not n:
        print("Sem verbatins com texto — empresa errada ou corpus vazio.")
        raise SystemExit

    # 1) por padrão (MENÇÃO do termo — teto superior)
    print("--- 1) menciona o TERMO (teto superior, nao = situacao declarada) ---")
    cont = {k: 0 for k in PADROES}
    algum = 0
    for _id, txt, tipo, fonte in linhas:
        t = txt or ""
        if ALGUM.search(t):
            algum += 1
        for k, rx in PAT.items():
            if rx.search(t):
                cont[k] += 1
    for k in sorted(cont, key=lambda x: -cont[x]):
        print(f"  {k:20} {cont[k]:>5}  {100*cont[k]/n:>5.1f}%")
    print(f"  {'>> ALGUM termo':20} {algum:>5}  {100*algum/n:>5.1f}%  (teto do corpus)")

    # 2) 20 exemplos reais — julgar situacao declarada vs mencao incidental
    print("\n--- 2) 20 EXEMPLOS que casaram algum termo (julgar a mao) ---")
    vistos = 0
    for _id, txt, tipo, fonte in linhas:
        if vistos >= 20:
            break
        if ALGUM.search(txt or ""):
            quais = [k for k, rx in PAT.items() if rx.search(txt or "")]
            print(f"  [{fonte or 'sem_fonte'}/{tipo}] ({','.join(quais)}) {_short(txt)!r}")
            vistos += 1

    # 3) varia por FONTE? (RA contextualiza mais que Google review curto?)
    print("\n--- 3) por FONTE (conector_tipo): menciona algum termo / total ---")
    porf = {}
    for _id, txt, tipo, fonte in linhas:
        f = fonte or "sem_fonte"
        d = porf.setdefault(f, [0, 0])
        d[1] += 1
        if ALGUM.search(txt or ""):
            d[0] += 1
    for f in sorted(porf, key=lambda x: -porf[x][1]):
        m, tt = porf[f]
        print(f"  {f:16} {m:>5}/{tt:<5} {100*m/tt:>5.1f}%")

    # 4) varia por VALENCIA? (quem reclama conta mais historia?)
    print("\n--- 4) por VALENCIA (tipo): menciona algum termo / total ---")
    porv = {}
    for _id, txt, tipo, fonte in linhas:
        d = porv.setdefault(tipo or "sem_tipo", [0, 0])
        d[1] += 1
        if ALGUM.search(txt or ""):
            d[0] += 1
    for v in sorted(porv, key=lambda x: -porv[x][1]):
        m, tt = porv[v]
        print(f"  {v:14} {m:>5}/{tt:<5} {100*m/tt:>5.1f}%")

    print("\nLeitura: '>> ALGUM' e o TETO. Os 20 exemplos dizem que fracao e situacao real.")
    print("Se fonte RA >> Google e a precisao dos exemplos for boa => RA e a fonte do mapa.")
