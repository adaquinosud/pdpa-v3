"""PROBE DESCARTÁVEL — quantos verbatins da Localiza mencionam a SITUAÇÃO que levou
a pessoa a alugar? READ-ONLY, custo US$0 (só lê corpus; NÃO chama LLM).

Mede se o CORPUS pode ser juiz do mapa de Momentos (a IA gera demais, o verbatim
decide quais sobrevivem). Mesma disciplina de medir-antes-de-desenhar que barateou
o experimento 1. Espelha a medição da declaração de permanência (deu 0,9-4,3%).

⚠️ O número por padrão conta MENÇÃO DO TERMO, não SITUAÇÃO DECLARADA — é teto
superior. "aluguei para viajar com a família" (situação) e "a família gostou do
carro" (incidental) ambos casam 'família'. Por isso a seção de EXEMPLOS: ela
calibra a precisão real. Julgar os 20 à mão é o ponto.

Uso no Render:  PYTHONPATH=. python scripts/probe_situacao_localiza.py \
                    [empresa_id=17] [fonte_filtro] [valencia_filtro] [n_exemplos=20]
  ex. célula densa RA×detrator com 40 exemplos:
      PYTHONPATH=. python scripts/probe_situacao_localiza.py 17 ra detrator 40
  (fonte_filtro casa por SUBSTRING no conector_tipo; use o rótulo visto na seção 3.)
Remover após o diagnóstico.
"""

import re
import sys

from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim as V
from src.utils.db import db_session

EMPRESA = int(sys.argv[1]) if len(sys.argv) > 1 else 17  # 0 = SCAN cross-empresa (escala)
FONTE_F = sys.argv[2].lower() if len(sys.argv) > 2 else None  # substring no conector_tipo
TIPO_F = sys.argv[3].lower() if len(sys.argv) > 3 else None  # valência exata
NEX = int(sys.argv[4]) if len(sys.argv) > 4 else 20

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
    if EMPRESA == 0:
        # SCAN cross-empresa (Q2 escala): quem tem massa RA×detrator com situação?
        print("=== SCAN cross-empresa: densidade RA x detrator com situacao ===\n")
        cons = sorted(c for (c,) in s.query(Fonte.conector_tipo).distinct() if c)
        print("conector_tipo existentes:", ", ".join(cons) or "(nenhum)")
        RA = re.compile(r"reclame|^ra$|ra_|_ra\b", re.IGNORECASE)  # confira acima qual casa
        nomes = {e.id: e.nome for e in s.query(Empresa)}
        rows = (
            s.query(V.empresa_id, V.tipo, V.texto, Fonte.conector_tipo)
            .outerjoin(Fonte, V.fonte_id == Fonte.id)
            .filter(V.tem_texto.is_(True))
            .all()
        )
        agg = {}  # empresa_id -> [ra_detr_total, ra_detr_com_termo, total_texto]
        for eid, tipo, txt, con in rows:
            d = agg.setdefault(eid, [0, 0, 0])
            d[2] += 1
            if con and RA.search(con) and (tipo or "").lower() == "detrator":
                d[0] += 1
                if ALGUM.search(txt or ""):
                    d[1] += 1
        print(f"\n{'empresa':24} {'txt':>7} {'RA_detr':>8} {'c/termo':>8} {'~situ':>6}")
        for eid in sorted(agg, key=lambda x: -agg[x][1]):
            rt, rterm, tt = agg[eid]
            est = round(rterm * 0.22)  # precisão ~20-25% da célula (item 1 do probe geral)
            print(f"{(nomes.get(eid) or '?')[:24]:24} {tt:>7} {rt:>8} {rterm:>8} {est:>6}")
        print("\n~situ = c/termo x 0.22 (precisao da celula). Se so Localiza tem massa,")
        print("a fonte RA depende de volume no ReclameAqui = limitacao de produto.")
        raise SystemExit

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

    # 2) N exemplos reais — julgar situacao declarada vs mencao incidental.
    #    Filtro opcional fonte/valencia p/ mirar a celula densa (ex. RA x detrator).
    foco = []
    if FONTE_F:
        foco.append(f"fonte~{FONTE_F}")
    if TIPO_F:
        foco.append(f"valencia={TIPO_F}")
    rotulo = (" [foco: " + ", ".join(foco) + "]") if foco else ""
    print(f"\n--- 2) {NEX} EXEMPLOS que casaram algum termo{rotulo} (julgar a mao) ---")
    vistos = 0
    for _id, txt, tipo, fonte in linhas:
        if vistos >= NEX:
            break
        if FONTE_F and FONTE_F not in (fonte or "").lower():
            continue
        if TIPO_F and TIPO_F != (tipo or "").lower():
            continue
        if ALGUM.search(txt or ""):
            quais = [k for k, rx in PAT.items() if rx.search(txt or "")]
            print(f"  [{fonte or 'sem_fonte'}/{tipo}] ({','.join(quais)}) {_short(txt)!r}")
            vistos += 1
    if foco:
        print(f"  (encontrados {vistos} na celula; precisao aqui decide o corpus-como-juiz)")

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
