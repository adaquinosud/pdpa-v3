"""Probe SÓ-LEITURA: base dos Temas do impresso, níveis N1–N4 no texto de modelo em cache, e
quebras do Longitudinal com cinco faixas em vez de quatro níveis (31/out, frente da legenda).

Uso (Shell do Render):  PULA=4 PYTHONPATH=. python scripts/sonda_niveis.py
                        E=29 PULA=4 PYTHONPATH=. python scripts/sonda_niveis.py

$0: nenhuma chamada LLM, nenhuma escrita. ``PULA`` = empresas fora da contagem (4 = BH Airport,
veto). ``E`` = empresa da parte A (default 29).

A. Temas × base: o impresso conta vínculos verbatim↔tema sem filtro de data; o motor só vincula
   a janela de temas (180 dias antes da última coleta), só com texto. Mostra quantos dos
   detratores da base do relatório entram, e o número que cada tema de promotor recebe.
B. Texto de modelo em cache que cita nível: leituras, sugestões e relatorio_cache, três padrões
   separados ("faixa" pega também usos que não são de nível — é teto, não contagem).
   Custo exato só para relatorio_cache (guarda tokens); leituras e sugestões não guardam.
C. Longitudinal: quebras de hoje (``_NIVEL``, fraco e atenção = N2) × quebras se a régua fosse a
   faixa (cinco). Usa ``montar_dados`` de verdade com a narrativa trocada por um stub que não
   chama o modelo nem grava. A diferença são as mudanças fraco↔atenção.
"""

import json
import os
import sys
import re
from collections import defaultdict

from sqlalchemy import func

from src.diagnostico.leituras import agregar_subpilares
from src.models.diagnostico import LeituraDiagnostico as L
from src.models.relatorio_cache import RelatorioCache as RC
from src.models.sugestao_estrutural import SugestaoEstrutural as S
from src.models.temas import Tema, VerbatimTema
from src.models.verbatim import Verbatim as V
from src.temas.janela import data_corte, filtro_janela, get_janela_dias
from src.utils.db import db_session

E = int(os.environ.get("E", "29"))
PULA = {int(x) for x in os.environ.get("PULA", "").split(",") if x}
with db_session() as s:
    agg = agregar_subpilares(s, E, None)
    print("== A. TEMAS x BASE, empresa", E)
    print("detratores no agg (base do relatorio):", sum(a["det"] for a in agg.values()))
    corte = data_corte(E, s)
    print("janela temas:", get_janela_dias(), "dias | corte:", corte)
    dq = s.query(func.count(V.id)).filter(V.empresa_id == E, V.tipo == "detrator")
    print("detratores na empresa, todos:", dq.scalar())
    cl = filtro_janela(corte)
    if cl is not None:
        print("  dentro da janela:", dq.filter(cl).scalar())
        print("  dentro da janela com texto:", dq.filter(cl, V.tem_texto.is_(True)).scalar())
    lig = (
        s.query(func.count(func.distinct(V.id)))
        .join(VerbatimTema, VerbatimTema.verbatim_id == V.id)
        .join(Tema, Tema.id == VerbatimTema.tema_id)
        .filter(V.empresa_id == E, V.tipo == "detrator", Tema.ativo.is_(True))
    )
    print("detratores ligados a tema ativo:", lig.scalar())
    if cl is not None:
        print("  desses, dentro da janela:", lig.filter(cl).scalar())
    print(
        "temas ativos:",
        s.query(func.count(Tema.id)).filter(Tema.empresa_id == E, Tema.ativo.is_(True)).scalar(),
    )
    rows = (
        s.query(Tema.id, Tema.nome, V.tipo, func.count(func.distinct(V.id)))
        .join(VerbatimTema, VerbatimTema.tema_id == Tema.id)
        .join(V, V.id == VerbatimTema.verbatim_id)
        .filter(
            Tema.empresa_id == E,
            Tema.ativo.is_(True),
            V.tipo.in_(("detrator", "conversivel", "promotor")),
        )
        .group_by(Tema.id, Tema.nome, V.tipo)
        .order_by(func.count(func.distinct(V.id)).desc())
        .all()
    )
    dom = {}
    for tid, nm, tipo, n in rows:
        if n > dom.get(tid, (None, 0))[1]:
            dom[tid] = (tipo, n)
    imp = defaultdict(list)
    for tid, nm, tipo, n in rows:
        if dom[tid][0] == tipo and len(imp[tipo]) < 5:
            imp[tipo].append((nm, n))
    print("como o impresso monta (top 5 por tipo dominante):")
    for t in ("detrator", "conversivel", "promotor"):
        print(" ", t, [f"{nm!r}={n!r}" for nm, n in imp[t]])

    print("")
    print("== B. TEXTO DE MODELO EM CACHE QUE CITA NIVEL (todas as empresas)")
    PAD = {
        "N1-N5": re.compile(r"\bN[1-5]\b"),
        "nivel": re.compile(r"\bn[ií]ve(?:l|is)\b", re.I),
        "faixa": re.compile(r"\bfaixa", re.I),
    }

    def bate(txt):
        return [k for k, rx in PAD.items() if txt and rx.search(txt)]

    def rc_txt(c):
        try:
            return json.dumps(json.loads(c), ensure_ascii=False)
        except Exception:
            return c or ""

    fontes = [
        (
            "leituras",
            s.query(L.empresa_id, L.agrupamento_id, L.local_id, L.leitura, L.acao).all(),
            None,
        ),
        (
            "sugestoes",
            s.query(S.empresa_id, S.agrupamento_id, S.local_id, S.acao, S.justificativa).all(),
            None,
        ),
    ]
    for nome, linhas, _ in fontes:
        por = defaultdict(lambda: defaultdict(int))
        esc = defaultdict(set)
        for emp, ag, loc, a, b in linhas:
            if emp in PULA:
                continue
            for k in bate((a or "") + "\n" + (b or "")):
                por[k][emp] += 1
                esc[k].add((emp, ag, loc))
        print(nome, "linhas:", len(linhas))
        for k in PAD:
            print(
                f"  {k}: {sum(por[k].values())} linhas, {len(por[k])} empresas,",
                f"{len(esc[k])} escopos",
                dict(por[k]),
            )
    tot_in = defaultdict(int)
    tot_out = defaultdict(int)
    por = defaultdict(lambda: defaultdict(int))
    rcs = s.query(RC.empresa_id, RC.secao, RC.conteudo_json, RC.tokens_in, RC.tokens_out).all()
    print("relatorio_cache linhas:", len(rcs))
    for emp, sec, c, ti, to in rcs:
        if emp in PULA:
            continue
        ks = bate(rc_txt(c))
        for k in ks:
            por[k][sec] += 1
        if ks:
            tot_in[emp] += ti or 0
            tot_out[emp] += to or 0
    for k in PAD:
        print(f"  {k}: por secao", dict(por[k]))
    usd = sum(tot_in.values()) / 1e6 * 3 + sum(tot_out.values()) / 1e6 * 15
    print(
        f"  relatorio_cache que cita algo: {len(tot_in)} empresas,",
        f"tokens in={sum(tot_in.values())} out={sum(tot_out.values())},",
        f"US$ {usd:.2f} = R$ {usd * 5.8:.2f} (Sonnet 3/15, cambio 5,80)",
    )

print("")
print("== C. LONGITUDINAL: quebras com 4 niveis (hoje) x 5 faixas")
import src.relatorios.llm_secoes as _ls  # noqa: E402
from src.models.empresa import Empresa  # noqa: E402
from src.relatorios import diagnostico_longitudinal as _lg  # noqa: E402

_ls.gerar_narrativa_longitudinal = lambda *a, **k: {  # stub: sem modelo, sem cache
    "narrativa_geral": "",
    "por_quarter": [],
    "cached": False,
    "tokens_in": 0,
    "tokens_out": 0,
}
with db_session() as s:
    emps = [i for (i,) in s.query(Empresa.id).order_by(Empresa.id).all() if i not in PULA]
tot4 = tot5 = 0
for emp in emps:
    d = _lg.montar_dados(emp)
    n4 = len(d["quebras"])
    n5 = 0
    pequenas = 0
    fa_at = 0
    for linha in d["matriz"]:
        for a, b in zip(linha.celulas, linha.celulas[1:]):
            if a.vazio or b.vazio or a.faixa == b.faixa:
                continue
            n5 += 1
            if {a.faixa, b.faixa} == {"fraco", "atencao"}:
                fa_at += 1
            if min(a.total, b.total) < 30:
                pequenas += 1
    if n4 or n5:
        print(
            f"  empresa {emp}: hoje {n4} | cinco faixas {n5} (+{n5 - n4};",
            f"fraco<->atencao {fa_at}) | celula < 30 em {pequenas} das {n5}",
        )
    tot4 += n4
    tot5 += n5
print(f"  TOTAL: hoje {tot4} | cinco faixas {tot5} (+{tot5 - tot4}) em {len(emps)} empresas")
sys.stdout.flush()
