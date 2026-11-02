"""Probe SÓ-LEITURA: participação de cada subpilar num recorte de uma empresa (02/nov, slide).

Uso (Shell do Render), todos os filtros opcionais menos EMPRESA:
  EMPRESA=<id> LOCAIS=1,2 AG=<agrupamento_id> FONTES=<fonte_id>,<fonte_id> \
  DESDE=2026-01-01 ATE=2026-06-30 PYTHONPATH=. python scripts/sonda_recorte_subpilares.py

Sem filtro nenhum = empresa inteira, período inteiro (o mesmo escopo do Explorar → Diagnóstico).
$0: nenhuma chamada LLM, nenhuma escrita.

Por subpilar (os 12, inclusive os zerados): detratores, conversíveis, promotores, total, ratio
(``calcular_ratio``), faixa (``faixa_ratio``) e o total como % do total do recorte. Ordem:
maior participação primeiro.

Critérios, declarados porque mudam o denominador:
- o % é sobre os verbatins COM subpilar no recorte; os sem subpilar saem do denominador e o
  número deles é impresso no fim;
- com DESDE/ATE, verbatim sem ``data_criacao_original`` NÃO entra (um recorte de período não sabe
  onde ele cai); quantos ficaram fora por isso também é impresso;
- LOCAIS tem precedência sobre AG, como no ``agregar_subpilares``;
- ratio 9,99 com 0 detratores é o teto do ``calcular_ratio``, não medição: sai marcado.
"""

import os
from datetime import datetime, timedelta

from sqlalchemy import func

from src.api.painel import NOME_SUBPILAR, SUBPILARES_ORDEM, calcular_ratio, faixa_ratio
from src.models.empresa import Empresa
from src.models.local import Local
from src.models.verbatim import Verbatim as V
from src.utils.db import db_session
from src.utils.fmt import virg


def _ids(nome):
    return [int(x) for x in os.environ.get(nome, "").split(",") if x.strip()]


def _data(nome):
    v = os.environ.get(nome, "").strip()
    return datetime.strptime(v, "%Y-%m-%d") if v else None


EMPRESA = int(os.environ["EMPRESA"])
LOCAIS, FONTES = _ids("LOCAIS"), _ids("FONTES")
AG = int(os.environ["AG"]) if os.environ.get("AG") else None
DESDE, ATE = _data("DESDE"), _data("ATE")

with db_session() as s:
    emp = s.get(Empresa, EMPRESA)
    base = s.query(V).filter(V.empresa_id == EMPRESA)
    if LOCAIS:
        base = base.filter(V.local_id.in_(LOCAIS))
    elif AG is not None:
        ag_locais = [
            i for (i,) in s.query(Local.id).filter_by(empresa_id=EMPRESA, agrupamento_id=AG)
        ]
        base = base.filter(V.local_id.in_(ag_locais or [-1]))
    if FONTES:
        base = base.filter(V.fonte_id.in_(FONTES))
    sem_data = 0
    if DESDE or ATE:
        sem_data = base.filter(V.data_criacao_original.is_(None)).count()
        base = base.filter(V.data_criacao_original.isnot(None))
    if DESDE:
        base = base.filter(V.data_criacao_original >= DESDE)
    if ATE:  # ATE inclusivo: o dia inteiro
        base = base.filter(V.data_criacao_original < ATE + timedelta(days=1))

    sem_sub = base.filter(V.subpilar.is_(None)).count()
    linhas = (
        base.filter(V.subpilar.isnot(None))
        .with_entities(V.subpilar, V.tipo, func.count(V.id))
        .group_by(V.subpilar, V.tipo)
        .all()
    )
    mix = {sub: {"promotor": 0, "conversivel": 0, "detrator": 0} for sub in SUBPILARES_ORDEM}
    fora_dos_12 = 0
    for sub, tipo, n in linhas:
        if sub not in mix:
            fora_dos_12 += n
            continue
        if tipo in mix[sub]:
            mix[sub][tipo] += n
    tot = sum(sum(d.values()) for d in mix.values())

    print(f"empresa {EMPRESA} {emp.nome if emp else '?'!r}")
    print(
        f"recorte: locais={LOCAIS or '—'} ag={AG or '—'} fontes={FONTES or '—'}",
        f"desde={DESDE.date() if DESDE else '—'} ate={ATE.date() if ATE else '—'}",
    )
    print(f"total com subpilar: {tot}")
    print("")
    print("subpilar | nome | det | conv | prom | total | ratio | faixa | % do recorte")
    for sub in sorted(SUBPILARES_ORDEM, key=lambda x: -sum(mix[x].values())):
        d = mix[sub]
        t = sum(d.values())
        det, conv, prom = d["detrator"], d["conversivel"], d["promotor"]
        if t:
            r = calcular_ratio(prom, det)
            ratio = virg(r) + (" (teto, 0 det)" if det == 0 else "")
            faixa = faixa_ratio(r)
        else:
            ratio = faixa = "—"
        pct = f"{virg(100 * t / tot, 1)}%" if tot else "—"
        print(
            f"  {sub} | {NOME_SUBPILAR.get(sub, sub)} | {det} | {conv} | {prom} | {t} |",
            f"{ratio} | {faixa} | {pct}",
        )
    print("")
    print(
        f"fora do denominador: {sem_sub} sem subpilar; {fora_dos_12} com subpilar fora dos 12",
        end="",
    )
    print(f"; {sem_data} sem data (excluídos pelo período)" if (DESDE or ATE) else "")
