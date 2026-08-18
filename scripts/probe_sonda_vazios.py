"""PROBE DESCARTÁVEL — a Sonda de Reputação IA está rodando Claude-only em silêncio?

READ-ONLY, custo US$0 (só lê SondaIAResposta já gravada — NÃO chama LLM). Responde:
  Q2  quantas respostas de GPT e Gemini estão VAZIAS (resposta_texto nulo/branco)?
  Q3  desde quando? há alguma resposta NÃO-vazia desses dois em alguma competência?

Motivo: adapters de prod usam MAX_OUT_TOKENS=500; GPT (reasoning) e Gemini (thinking
ligado, SEM thinkingConfig) gastam o cap pensando e zeram o texto — mesmo bug que o
experimento de Momentos pegou. Aqui medimos no DADO REAL.

Uso no Render:  PYTHONPATH=. python scripts/probe_sonda_vazios.py
Remover após o diagnóstico.
"""

from sqlalchemy import func

from src.models.sonda_ia import SondaIAExecucao, SondaIAResposta
from src.utils.db import db_session


def _vazio(txt):
    return not (txt or "").strip()


with db_session() as s:
    tot = s.query(func.count(SondaIAResposta.id)).scalar() or 0
    print(f"=== SondaIAResposta: {tot} respostas gravadas ===\n")
    if not tot:
        print("Nenhuma resposta gravada — sonda nunca rodou em prod. Nada a diagnosticar.")
        raise SystemExit

    # Q2 — por vendor: total, vazias, % vazio, tokens_out médio (vazio => out alto sem texto).
    print(f"{'vendor':8} {'total':>6} {'vazias':>7} {'%vazio':>7} {'out_medio':>9}")
    for (vendor,) in s.query(SondaIAResposta.vendor).distinct().order_by(SondaIAResposta.vendor):
        rs = s.query(SondaIAResposta).filter(SondaIAResposta.vendor == vendor).all()
        n = len(rs)
        vaz = sum(1 for r in rs if _vazio(r.resposta_texto))
        outm = sum(int(r.tokens_out or 0) for r in rs) / n if n else 0
        print(f"{vendor:8} {n:>6} {vaz:>7} {100*vaz/n:>6.0f}% {outm:>9.0f}")

    # Q3 — por competência × vendor: quantas não-vazias. Mostra desde quando (e se algum dia
    # GPT/Gemini produziram texto de verdade).
    print("\n=== por competência × vendor (nao-vazias / total) ===")
    comps = [
        c
        for (c,) in s.query(SondaIAExecucao.competencia)
        .distinct()
        .order_by(SondaIAExecucao.competencia)
    ]
    vendors = [
        v for (v,) in s.query(SondaIAResposta.vendor).distinct().order_by(SondaIAResposta.vendor)
    ]
    print(f"{'comp':9} " + " ".join(f"{v:>14}" for v in vendors))
    for c in comps:
        exs = [e.id for e in s.query(SondaIAExecucao).filter(SondaIAExecucao.competencia == c)]
        celulas = []
        for v in vendors:
            rs = (
                s.query(SondaIAResposta)
                .filter(SondaIAResposta.vendor == v, SondaIAResposta.execucao_id.in_(exs))
                .all()
            )
            nv = sum(1 for r in rs if not _vazio(r.resposta_texto))
            celulas.append(f"{nv}/{len(rs)}")
        print(f"{c:9} " + " ".join(f"{x:>14}" for x in celulas))

    # Q3b — se GPT/Gemini têm ALGUMA não-vazia, mostra a mais recente (prova de vida).
    print("\n=== prova de vida: resposta NAO-vazia mais recente por vendor ===")
    for v in vendors:
        r = (
            s.query(SondaIAResposta)
            .filter(SondaIAResposta.vendor == v)
            .order_by(SondaIAResposta.criado_em.desc())
            .all()
        )
        viva = next((x for x in r if not _vazio(x.resposta_texto)), None)
        if viva:
            amostra = (viva.resposta_texto or "").strip().replace("\n", " ")[:80]
            print(f"  {v:8} SIM  ({viva.criado_em:%Y-%m-%d} #{viva.pergunta_tipo}): {amostra!r}")
        else:
            print(f"  {v:8} NAO — nunca produziu texto (todas vazias)")

    print("\nLeitura: se gpt/gemini = 100% vazio e prova-de-vida NAO => sonda e Claude-only.")
