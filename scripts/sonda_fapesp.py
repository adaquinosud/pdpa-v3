"""Probe SÓ-LEITURA: números agregados para a submissão à FAPESP (03/nov).

Uso (Shell do Render):  PULA=4 TESTE=15,18,20 PYTHONPATH=. python scripts/sonda_fapesp.py

$0: nenhuma chamada LLM, nenhuma escrita. Não imprime nome de empresa, razão social, e-mail,
variável de ambiente nem credencial: só setor, contagem e escala. Setor com uma organização só
sai marcado "(1 org: identificável)", porque o setor sozinho já nomeia o cliente.

``PULA`` = empresas fora por veto (4 = BH Airport). ``TESTE`` = contas de teste, fora também.
As duas listas saem impressas no topo, para a contagem ter o critério junto.

Seções (o número do pedido entre colchetes):
  A [1]  organizações, unidades e manifestações por setor; manifestações por fonte; primeira data.
  B [1]  "pareceres entregues": o sistema NÃO registra entrega; o que existe é seção de relatório
         gerada por LLM (``relatorio_cache``) e parecer do Avaliador. Sai por setor e ano, com o
         nome do que foi contado.
  C [3]  volume e custo por mês, últimos 6 meses: coleta (``coletas_execucoes``), classificação
         (``classifier_metrics``), seções de relatório (tokens), sonda IA, Avaliador.
  D [4]  tamanho do banco e das maiores tabelas (``pg_stat_user_tables``, estimativa do Postgres).
  E [5]  dupla classificação: textos com mais de uma chamada no ``classifier_metrics`` (mesmo
         ``texto_hash``) e concordância; reclassificações manuais; distribuição dos 12 subpilares
         na base inteira e por setor.
  F [2.4] usuários por papel e ativo (só contagem).
"""

import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from sqlalchemy import case, extract, func, literal_column, text

from src.api.painel import SUBPILARES_ORDEM
from src.models.avaliador import AvaliadorAnalise
from src.models.classifier_metric import ClassifierMetric as CM
from src.models.coleta_execucao import ColetaExecucao as CE
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.local import Local
from src.models.relatorio_cache import RelatorioCache as RC
from src.models.sonda_ia import SondaIAExecucao
from src.models.usuario import Usuario
from src.models.verbatim import Verbatim as V
from src.models.verbatim_reclassificacao import VerbatimReclassificacao as VR
from src.utils.db import db_session
from src.utils.fmt import virg

CAMBIO = 5.80  # R$/US$, fixo


def _ids(nome):
    return {int(x) for x in os.environ.get(nome, "").split(",") if x.strip()}


FORA = _ids("PULA") | _ids("TESTE")


def _pct(a, b):
    return f"{virg(100 * a / b, 1)}%" if b else "—"


def _secao(titulo):
    print("")
    print(f"== {titulo}")


with db_session() as s:
    emps = {e.id: (e.setor or "(sem setor)") for e in s.query(Empresa) if e.id not in FORA}
    ids = list(emps)
    por_setor = defaultdict(list)
    for eid, setor in emps.items():
        por_setor[setor].append(eid)

    def _rotulo(setor):
        n = len(por_setor[setor])
        return f"{setor} ({n} org{': identificável' if n == 1 else 's'})"

    print(f"fora da contagem: veto={sorted(_ids('PULA'))} teste={sorted(_ids('TESTE'))}")
    print(f"organizações na contagem: {len(ids)}")

    # ── A ────────────────────────────────────────────────────────────────────────
    _secao("A [1] organizações, unidades e manifestações por setor")
    locs = Counter(
        dict(
            s.query(Local.empresa_id, func.count(Local.id))
            .filter(Local.empresa_id.in_(ids))
            .group_by(Local.empresa_id)
            .all()
        )
    )
    vb = {
        eid: (int(t), int(c))
        for eid, t, c in s.query(V.empresa_id, func.count(V.id), func.count(V.subpilar))
        .filter(V.empresa_id.in_(ids))
        .group_by(V.empresa_id)
        .all()
    }
    print("setor | organizações | unidades | manifestações | classificadas (com subpilar)")
    tl = tv = tc = 0
    for setor in sorted(por_setor):
        es = por_setor[setor]
        nl = sum(locs[e] for e in es)
        nv = sum(vb.get(e, (0, 0))[0] for e in es)
        nc = sum(vb.get(e, (0, 0))[1] for e in es)
        tl, tv, tc = tl + nl, tv + nv, tc + nc
        print(f"  {_rotulo(setor)} | {len(es)} | {nl} | {nv} | {nc}")
    print(f"  TOTAL | {len(ids)} | {tl} | {tv} | {tc}")
    print("organizações com pelo menos 1 manifestação:", sum(1 for e in ids if vb.get(e)))
    print("")
    print("distribuição por organização, da maior para a menor (sem nome; setor ao lado):")
    print("posição | setor | manifestações | classificadas")
    ordem_v = sorted((e for e in ids if vb.get(e)), key=lambda e: -vb[e][0])
    for i, e in enumerate(ordem_v, 1):
        print(f"  {i} | {_rotulo(emps[e])} | {vb[e][0]} | {vb[e][1]}")

    print("")
    print("manifestações por fonte (conector) | total | classificadas")
    for tipo, t, c in (
        s.query(Fonte.conector_tipo, func.count(V.id), func.count(V.subpilar))
        .join(Fonte, Fonte.id == V.fonte_id)
        .filter(V.empresa_id.in_(ids))
        .group_by(Fonte.conector_tipo)
        .order_by(func.count(V.id).desc())
        .all()
    ):
        print(f"  {tipo} | {t} ({_pct(t, tv)}) | {c}")

    prim_coleta, prim_orig = (
        s.query(func.min(V.data_coleta), func.min(V.data_criacao_original))
        .filter(V.empresa_id.in_(ids))
        .one()
    )
    prim_rel = s.query(func.min(RC.gerado_em)).filter(RC.empresa_id.in_(ids)).scalar()
    print("")
    print(f"primeira coleta registrada (data_coleta): {prim_coleta}")
    print(f"manifestação mais antiga (data de publicação na fonte): {prim_orig}")
    print(f"primeira seção de relatório gerada (relatorio_cache): {prim_rel}")

    # ── B ────────────────────────────────────────────────────────────────────────
    _secao("B [1] relatórios gerados por setor e ano (o sistema não registra ENTREGA)")
    print("relatorio_cache = seção de relatório escrita por LLM; conta (empresa, ano) com ao menos")
    print("uma seção, e o número de seções. Regerar a mesma seção não soma linha: a linha é")
    print("sobrescrita, então o ano é o da ÚLTIMA geração.")
    rel = (
        s.query(RC.empresa_id, extract("year", RC.gerado_em), func.count(RC.id))
        .filter(RC.empresa_id.in_(ids))
        .group_by(RC.empresa_id, extract("year", RC.gerado_em))
        .all()
    )
    agg = defaultdict(lambda: [0, 0])
    for eid, ano, n in rel:
        k = (emps[eid], int(ano))
        agg[k][0] += 1
        agg[k][1] += int(n)
    print("setor | ano | organizações com relatório | seções")
    for (setor, ano), (no, ns) in sorted(agg.items()):
        print(f"  {_rotulo(setor)} | {ano} | {no} | {ns}")
    print(f"organizações com ao menos uma seção, qualquer ano: {len({e for e, _, _ in rel})}")
    print("")
    print("Avaliador de documentos (avaliador_analises) por setor e ano:")
    try:
        av = (
            s.query(AvaliadorAnalise.empresa_id, extract("year", AvaliadorAnalise.criado_em))
            .filter(AvaliadorAnalise.empresa_id.in_(ids))
            .all()
        )
        c = Counter((emps[e], int(a)) for e, a in av)
        for (setor, ano), n in sorted(c.items()):
            print(f"  {_rotulo(setor)} | {ano} | {n} leituras")
        if not c:
            print("  nenhuma")
    except Exception as exc:  # coluna diferente do esperado: declara e segue
        s.rollback()
        print(f"  não medido: {type(exc).__name__}")

    # ── C ────────────────────────────────────────────────────────────────────────
    _secao("C [3] volume e custo por mês, últimos 6 meses (US$; R$ a 5,80)")
    desde = datetime.utcnow().replace(day=1) - timedelta(days=150)
    desde = desde.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    print(f"desde {desde.date()}; custo NULL sai contado à parte (nulo não é grátis)")

    def _mes(col):
        return func.to_char(col, literal_column("'YYYY-MM'"))  # literal: GROUP BY casa com o SELECT

    print("")
    print("coleta | mês | conector | execuções | coletados | novos | US$ Apify | execs sem custo")
    for mes, tipo, n, col, nov, cent, nulos in (
        s.query(
            _mes(CE.iniciado_em),
            Fonte.conector_tipo,
            func.count(CE.id),
            func.sum(CE.coletados),
            func.sum(CE.novos),
            func.sum(CE.custo_apify_centavos),
            func.count(CE.id) - func.count(CE.custo_apify_centavos),
        )
        .join(Fonte, Fonte.id == CE.fonte_id)
        .filter(CE.iniciado_em >= desde, CE.empresa_id.in_(ids))
        .group_by(_mes(CE.iniciado_em), Fonte.conector_tipo)
        .order_by(_mes(CE.iniciado_em), Fonte.conector_tipo)
        .all()
    ):
        usd = (cent or 0) / 100
        print(f"  {mes} | {tipo} | {n} | {col or 0} | {nov or 0} | {virg(usd)} | {nulos}")

    print("")
    print("classificação | mês | modelo | chamadas | escaladas | US$ | US$/chamada")
    for mes, modelo, n, esc, usd in (
        s.query(
            _mes(CM.chamada_em),
            CM.modelo,
            func.count(CM.id),
            func.sum(case((CM.escalado.is_(True), 1), else_=0)),
            func.sum(CM.custo_usd),
        )
        .filter(CM.chamada_em >= desde)
        .group_by(_mes(CM.chamada_em), CM.modelo)
        .order_by(_mes(CM.chamada_em), CM.modelo)
        .all()
    ):
        usd = usd or 0
        print(f"  {mes} | {modelo} | {n} | {esc or 0} | {virg(usd, 4)} | {virg(usd / n, 5)}")
    print("  (classifier_metrics não tem empresa: inclui as contas fora da contagem)")

    print("")
    print("seções de relatório (última geração) | mês | seções | tokens in | tokens out")
    for mes, n, ti, to in (
        s.query(
            _mes(RC.gerado_em), func.count(RC.id), func.sum(RC.tokens_in), func.sum(RC.tokens_out)
        )
        .filter(RC.gerado_em >= desde, RC.empresa_id.in_(ids))
        .group_by(_mes(RC.gerado_em))
        .order_by(_mes(RC.gerado_em))
        .all()
    ):
        print(f"  {mes} | {n} | {ti or 0} | {to or 0}")

    print("")
    print("sonda IA (3 famílias) | mês | execuções | US$ | sem custo")
    for mes, n, usd, nulos in (
        s.query(
            _mes(SondaIAExecucao.iniciado_em),
            func.count(SondaIAExecucao.id),
            func.sum(SondaIAExecucao.custo_usd),
            func.count(SondaIAExecucao.id) - func.count(SondaIAExecucao.custo_usd),
        )
        .filter(SondaIAExecucao.iniciado_em >= desde, SondaIAExecucao.empresa_id.in_(ids))
        .group_by(_mes(SondaIAExecucao.iniciado_em))
        .order_by(_mes(SondaIAExecucao.iniciado_em))
        .all()
    ):
        print(f"  {mes} | {n} | {virg(usd or 0, 4)} | {nulos}")

    print("")
    print("Avaliador | mês | leituras | US$")
    try:
        for mes, n, usd in (
            s.query(
                _mes(AvaliadorAnalise.criado_em),
                func.count(AvaliadorAnalise.id),
                func.sum(AvaliadorAnalise.custo_usd),
            )
            .filter(AvaliadorAnalise.criado_em >= desde)
            .group_by(_mes(AvaliadorAnalise.criado_em))
            .order_by(_mes(AvaliadorAnalise.criado_em))
            .all()
        ):
            print(f"  {mes} | {n} | {virg(usd or 0, 4)}")
        print("Avaliador, período inteiro, leituras prontas, por formato:")
        print("  formato | modelo | leituras | págs médias | US$ mín | US$ médio | US$ máx")
        for fmt, mod, n, pg, lo, md, hi in (
            s.query(
                AvaliadorAnalise.formato,
                AvaliadorAnalise.modelo,
                func.count(AvaliadorAnalise.id),
                func.avg(AvaliadorAnalise.n_paginas),
                func.min(AvaliadorAnalise.custo_usd),
                func.avg(AvaliadorAnalise.custo_usd),
                func.max(AvaliadorAnalise.custo_usd),
            )
            .filter(AvaliadorAnalise.status == "pronta")
            .group_by(AvaliadorAnalise.formato, AvaliadorAnalise.modelo)
            .all()
        ):
            print(
                f"  {fmt} | {mod} | {n} | {virg(float(pg or 0), 1)} |",
                f"{virg(lo or 0, 4)} | {virg(float(md or 0), 4)} | {virg(hi or 0, 4)}",
            )
    except Exception as exc:
        s.rollback()
        print(f"  não medido: {type(exc).__name__}")

    # ── D ────────────────────────────────────────────────────────────────────────
    _secao("D [4] tamanho do banco")
    tam = s.execute(text("SELECT pg_size_pretty(pg_database_size(current_database()))")).scalar()
    print(f"banco inteiro: {tam}")
    print("10 maiores tabelas | linhas (estimativa do Postgres) | tamanho com índices")
    for nome, linhas, t in s.execute(
        text(
            "SELECT relname, n_live_tup, pg_size_pretty(pg_total_relation_size(relid)) "
            "FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 10"
        )
    ):
        print(f"  {nome} | {linhas} | {t}")
    n_tab = s.execute(text("SELECT count(*) FROM pg_stat_user_tables")).scalar()
    print(f"tabelas: {n_tab}")

    # ── E ────────────────────────────────────────────────────────────────────────
    _secao("E [5] dupla classificação e distribuição dos 12 subpilares")
    rows = (
        s.query(CM.texto_hash, CM.modelo, CM.subpilar, CM.tipo, CM.escalado)
        .filter(CM.texto_hash.isnot(None))
        .order_by(CM.texto_hash, CM.id)
        .all()
    )
    grupos = defaultdict(list)
    for h, modelo, sub, tipo, esc in rows:
        grupos[h].append((modelo, sub, tipo, esc))
    multi = {h: g for h, g in grupos.items() if len(g) > 1}
    print(f"textos no classifier_metrics: {len(grupos)}; com mais de uma chamada: {len(multi)}")
    print("concordância = 1ª e última chamada do mesmo texto dão o mesmo (subpilar, tipo).")
    print("NÃO são classificações independentes: a 2ª chamada existe porque houve reprocesso")
    print("ou escalada (confiança baixa ⇒ casos difíceis); o número vale só com esse critério.")
    por_par = defaultdict(lambda: [0, 0])
    por_sub = defaultdict(lambda: [0, 0])
    for g in multi.values():
        a, b = g[0], g[-1]
        par = "mesmo modelo" if a[0] == b[0] else f"{a[0]} → {b[0]}"
        ok = (a[1], a[2]) == (b[1], b[2])
        por_par[par][0] += ok
        por_par[par][1] += 1
        por_sub[a[1]][0] += ok
        por_sub[a[1]][1] += 1
    for par, (ok, n) in sorted(por_par.items(), key=lambda kv: -kv[1][1]):
        print(f"  {par}: {ok}/{n} concordam ({_pct(ok, n)})")
    print("  por subpilar da 1ª chamada:")
    for sub in SUBPILARES_ORDEM + [x for x in por_sub if x not in SUBPILARES_ORDEM]:
        if sub in por_sub:
            ok, n = por_sub[sub]
            print(f"    {sub}: {ok}/{n} ({_pct(ok, n)})")

    n_recl = s.query(func.count(VR.id)).scalar()
    n_recl_v = s.query(func.count(func.distinct(VR.verbatim_id))).scalar()
    print("")
    print(f"reclassificações manuais (pessoa corrigiu a máquina): {n_recl} em {n_recl_v} verbatins")
    print("  só a correção é gravada, a confirmação não: não dá taxa de concordância.")

    print("")
    print("distribuição dos 12 subpilares, base inteira (verbatins com subpilar):")
    dist = dict(
        s.query(V.subpilar, func.count(V.id))
        .filter(V.empresa_id.in_(ids), V.subpilar.isnot(None))
        .group_by(V.subpilar)
        .all()
    )
    tot = sum(dist.values())
    for sub in SUBPILARES_ORDEM:
        print(f"  {sub} | {dist.get(sub, 0)} | {_pct(dist.get(sub, 0), tot)}")
    fora12 = sum(n for k, n in dist.items() if k not in SUBPILARES_ORDEM)
    print(f"  total {tot}; fora dos 12: {fora12}")
    if tot:  # taxa com 4 casas: é o p do piso, 1 casa de % não basta
        rara = min(SUBPILARES_ORDEM, key=lambda x: dist.get(x, 0))
        n_rara = dist.get(rara, 0)
        print(f"  posição mais rara: {rara} | {n_rara} de {tot} | taxa {virg(n_rara / tot, 4)}")

    print("")
    print("o mesmo por setor (% dentro do setor):")
    ds = defaultdict(Counter)
    for eid, sub, n in (
        s.query(V.empresa_id, V.subpilar, func.count(V.id))
        .filter(V.empresa_id.in_(ids), V.subpilar.isnot(None))
        .group_by(V.empresa_id, V.subpilar)
        .all()
    ):
        ds[emps[eid]][sub] += n
    print("setor | n | " + " | ".join(SUBPILARES_ORDEM))
    for setor in sorted(ds):
        c = ds[setor]
        t = sum(c.values())
        print(f"  {_rotulo(setor)} | {t} | " + " | ".join(_pct(c[x], t) for x in SUBPILARES_ORDEM))

    # ── F ────────────────────────────────────────────────────────────────────────
    _secao("F [2.4] usuários por papel (só contagem)")
    for papel, ativo, n in (
        s.query(Usuario.papel, Usuario.ativo, func.count(Usuario.id))
        .group_by(Usuario.papel, Usuario.ativo)
        .order_by(Usuario.papel)
        .all()
    ):
        print(f"  {papel} | ativo={ativo} | {n}")
    print("  (inclui usuários das contas fora da contagem)")

print("")
print(f"câmbio fixo R$ {virg(CAMBIO)}/US$ para converter os US$ acima")
