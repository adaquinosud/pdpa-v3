"""Probe SÓ-LEITURA: quanto da base de cada empresa está fora da janela de 180 dias (31/out).

Uso (Shell do Render):  PULA=4 PYTHONPATH=. python scripts/sonda_horizonte.py

$0: nenhuma chamada LLM, nenhuma escrita. ``PULA`` = empresas fora (4 = BH Airport, veto).

Por empresa: verbatim mais antigo e mais novo (``data_criacao_original``), total, sem data,
dentro da janela dos temas (``temas.janela.data_corte`` = MAX(data_coleta) − 180 dias; sem data
ENTRA, mesma semântica do ``filtro_janela``), dentro de 15 meses (janela de coleta, mesma âncora),
e o mesmo só para detratores. A âncora é a dos temas de propósito: é a régua que produziu os
"11 detratores dentro da janela" da sonda_niveis.

Parte B (pedido de 31/out): a decisão de agosto (ratio no período inteiro) foi provada só
para o Índice PDPA. Por empresa, o gargalo (``gargalo_detalhe``, régua canônica) e o 1º da
Sequência de ação (``sequencia_de_acao``) com o período inteiro × com a janela dos temas
(``agregar_subpilares(desde=data_corte)``), e quantos subpilares com dado ficam abaixo do piso
de 30 na janela curta. Não muda nada: mede se a decisão continua valendo para o gargalo.

No fim: toda execução registrada de ``flask retencao-aplicar`` (a única poda de verbatim que
existe; manual, sem cron) em ``eventos_manutencao``.
"""

import os
from datetime import timedelta

from sqlalchemy import func

from src.api.engajamento import VOLUME_CONFIANCA_ALTA
from src.api.painel import gargalo_detalhe, sequencia_de_acao
from src.diagnostico.leituras import agregar_subpilares
from src.models.empresa import Empresa
from src.models.evento_manutencao import EventoManutencao
from src.models.verbatim import Verbatim as V
from src.temas.janela import data_corte, filtro_janela
from src.utils.db import db_session

PULA = {int(x) for x in os.environ.get("PULA", "").split(",") if x}


def _pct(a, b):
    return f"{100 * a / b:.0f}%" if b else "—"


with db_session() as s:
    emps = s.query(Empresa.id, Empresa.nome).order_by(Empresa.id).all()
    print("empresa | antigo..novo | total (sem data) | em 180d | em 15m | det total | det em 180d")
    tot = {"t": 0, "j": 0, "d": 0, "dj": 0}
    for emp, nome in emps:
        if emp in PULA:
            continue
        base = s.query(V).filter(V.empresa_id == emp)
        total = base.count()
        if not total:
            continue
        antigo, novo = (
            s.query(func.min(V.data_criacao_original), func.max(V.data_criacao_original))
            .filter(V.empresa_id == emp)
            .one()
        )
        sem_data = base.filter(V.data_criacao_original.is_(None)).count()
        corte = data_corte(emp, s)
        cl180 = filtro_janela(corte)
        cl15 = filtro_janela(corte + timedelta(days=180) - timedelta(days=450)) if corte else None
        em180 = base.filter(cl180).count() if cl180 is not None else total
        em15 = base.filter(cl15).count() if cl15 is not None else total
        det = base.filter(V.tipo == "detrator")
        dt = det.count()
        dj = det.filter(cl180).count() if cl180 is not None else dt
        a = antigo.strftime("%m/%Y") if antigo else "—"
        n = novo.strftime("%m/%Y") if novo else "—"
        print(
            f"  {emp} {nome[:22]!r} | {a}..{n} | {total} ({sem_data}) |",
            f"{em180} {_pct(em180, total)} | {em15} {_pct(em15, total)} |",
            f"{dt} | {dj} {_pct(dj, dt)}",
        )
        tot["t"] += total
        tot["j"] += em180
        tot["d"] += dt
        tot["dj"] += dj
    print(
        f"  TOTAL: {tot['t']} verbatins, {tot['j']} em 180d ({_pct(tot['j'], tot['t'])});",
        f"{tot['d']} detratores, {tot['dj']} em 180d ({_pct(tot['dj'], tot['d'])})",
    )
    print("")
    print("== B. GARGALO e 1o da Sequencia: periodo inteiro x janela de 180 dias")
    print("empresa | gargalo inteiro -> 180d | 1o seq inteiro -> 180d | subs < 30 na janela")

    def _g(agg):
        d = gargalo_detalhe(agg)
        if not d:
            return "—"
        el = (d.get("eleitor") or {}).get("subpilar")
        return d["pilar"] + (f"({el})" if el else "")

    n_emp = mud_g = mud_s = 0
    for emp, nome in emps:
        if emp in PULA:
            continue
        cheio = agregar_subpilares(s, emp, None)
        if not cheio:
            continue
        corte = data_corte(emp, s)
        curto = agregar_subpilares(s, emp, None, desde=corte) if corte else cheio
        g1, g2 = _g(cheio), _g(curto)
        s1 = (sequencia_de_acao(cheio)[0] or ["—"])[0]
        s2 = (sequencia_de_acao(curto)[0] or ["—"])[0]
        baixos = sum(1 for d in curto.values() if (d.get("total") or 0) < VOLUME_CONFIANCA_ALTA)
        n_emp += 1
        mud_g += g1 != g2
        mud_s += s1 != s2
        marca = " <-- muda" if (g1 != g2 or s1 != s2) else ""
        print(
            f"  {emp} {nome[:22]!r} | {g1} -> {g2} | {s1} -> {s2} |",
            f"{baixos} de {len(curto)}{marca}",
        )
    print(f"  TOTAL: {n_emp} empresas; gargalo muda em {mud_g}; 1o da Sequencia muda em {mud_s}")
    print("")
    print("retencao-aplicar executado (eventos_manutencao, tipo=retencao_verbatins):")
    ev = (
        s.query(EventoManutencao)
        .filter(EventoManutencao.tipo == "retencao_verbatins")
        .order_by(EventoManutencao.id)
        .all()
    )
    if not ev:
        print("  nenhuma execucao registrada")
    for e in ev:
        print(
            f"  {e.executado_em} dry_run={e.dry_run}",
            f"qtd={e.qtd_afetada} | {e.mensagem}",
        )
