"""⚠️ EXPERIMENTO DESCARTÁVEL — NÃO É FEATURE. Remover após o resultado.

Data: 2026-08-17. O que testa: ESTABILIDADE da leitura "Momentos/Ocupação" (degraus 1-2
do Capital de Escolha) para UMA empresa (Localiza), ANTES de decidir construir a frente.
Pergunta ao LLM (não toca o corpus): que SITUAÇÕES levam alguém a alugar carro (Mapa) e,
por situação, quem vem à cabeça (Ocupação). Roda no Render (chaves em env). Custo pinado
~US$1 (teto US$5); imprime o custo REAL no fim. Reusa src/sonda_ia/adapters.

CRITÉRIO TRAVADO 2026-08-17 (não muda depois de ver o resultado):
  momento CONVERGE  se Jaccard>=0.60 E Kendall-tau>=0.50 E alvo(Localiza) em 0/3 ou 3/3.
  falseamento §6:   cada momento precisa de >=1 candidato FORA da categoria de locadoras.
  PASSA  se: >=2 momentos convergem E Mapa Jaccard>=0.50 E fora-de-cat em >=2 momentos.
  REPROVA se qualquer uma falhar (inclusive "so locadoras" = estavel e inutil).
  Gate = repetição within-model; cross-modelo é informação.

Uso no Render:  PYTHONPATH=. python scripts/exp_momentos_localiza.py
"""

import json
import re
from itertools import combinations
from statistics import mean

from scipy.stats import kendalltau

from src.sonda_ia.adapters import chamar_claude, chamar_gemini, chamar_gpt

VENDORS = {"claude": chamar_claude, "gpt": chamar_gpt, "gemini": chamar_gemini}
REPS = 3
ALVO = "localiza"
# Falseamento §6: sinais de candidato FORA da categoria de locadoras.
FORA_CAT = (
    "uber",
    "99",
    "táxi",
    "taxi",
    "ônibus",
    "onibus",
    "carona",
    "transfer",
    "próprio",
    "proprio",
    "não ir",
    "nao ir",
    "não viaj",
    "nao viaj",
    "adiar",
    "metrô",
    "metro",
    "público",
    "publico",
    "bicicleta",
    "a pé",
    "a pe",
    "aplicativo",
    "blablacar",
    "meu carro",
    "carro da",
    "não alug",
    "nao alug",
)

MAPA = (
    "Uma pessoa no Brasil tem uma situação de vida que a leva a precisar de um carro por um "
    "período. Liste as SITUAÇÕES (não perfis de pessoa, não segmentos) que levam alguém a "
    "ALUGAR um carro. Cada item em 1ª pessoa e presente ('preciso...'). Responda SÓ um array "
    "JSON de strings curtas, do mais comum ao menos. Sem texto fora do JSON."
)
MOMENTOS = [
    "Meu carro está na oficina e preciso trabalhar essa semana",
    "Cheguei de avião numa cidade que não é a minha e preciso me locomover",
    "Vou viajar com a família no fim de semana",
]
OCUP = (
    'Situação, em 1ª pessoa: "{m}". Como uma pessoa resolveria isso? Liste os candidatos que '
    "viriam à cabeça dela, NA ORDEM em que pensaria, do mais provável ao menos. INCLUA opções "
    "fora da categoria de locadoras: carro próprio, aplicativo (Uber/99), ônibus, pedir carona, "
    "adiar ou não ir. Responda SÓ um array JSON de strings (nomes de empresas OU opções). "
    "Sem texto fora do JSON."
)


def _lista(txt):
    m = re.search(r"\[.*\]", txt, re.DOTALL)
    if not m:
        return None
    try:
        arr = json.loads(m.group(0))
    except Exception:  # noqa: BLE001 — resposta malformada = lista vazia (conta como divergência)
        return None
    return [str(x).strip().lower() for x in arr if str(x).strip()]


def _jaccard(a, b):
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if (sa | sb) else 0.0


def _tau(a, b):
    comuns = [x for x in a if x in b]
    if len(comuns) < 2:
        return None
    ra = [a.index(x) for x in comuns]
    rb = [b.index(x) for x in comuns]
    t, _ = kendalltau(ra, rb)
    return t


def _coletar(prompt):
    """{vendor: [lista_rep1..N]} + tokens (in, out) acumulados."""
    out, tin, tout = {}, 0, 0
    for v, fn in VENDORS.items():
        out[v] = []
        for _ in range(REPS):
            r = fn(prompt)
            tin += r.get("tokens_in", 0)
            tout += r.get("tokens_out", 0)
            out[v].append(_lista(r.get("texto", "")) or [])
    return out, tin, tout


def _fora_cat(reps):
    """True se ALGUMA rep traz ALGUM candidato fora da categoria de locadoras."""
    return any(any(any(k in c for k in FORA_CAT) for c in r) for r in reps)


def _metricas(reps):
    pares = list(combinations(range(len(reps)), 2))
    js = [_jaccard(reps[i], reps[j]) for i, j in pares]
    ts = [t for i, j in pares if (t := _tau(reps[i], reps[j])) is not None]
    alvo = sum(1 for r in reps if any(ALVO in c for c in r))
    return (mean(js) if js else 0.0), (mean(ts) if ts else None), alvo


def main():
    tin = tout = 0
    print("=== MAPA (estabilidade da enumeração) ===")
    mapa, ti, to = _coletar(MAPA)
    tin += ti
    tout += to
    mapa_js = []
    for v, reps in mapa.items():
        j, _t, _a = _metricas(reps)
        mapa_js.append(j)
        print(f"  {v:7} Jaccard={j:.2f}  (ex rep1: {reps[0][:4]})")
    mapa_ok = mean(mapa_js) >= 0.50
    print(f"  -> Mapa Jaccard medio {mean(mapa_js):.2f}  ({'OK >=0.50' if mapa_ok else 'BAIXO'})")

    conv = 0
    sem_fora = 0  # momentos SEM candidato fora-de-categoria (falseamento §6)
    for m in MOMENTOS:
        print(f"\n=== OCUPACAO: {m!r} ===")
        dados, ti, to = _coletar(OCUP.format(m=m))
        tin += ti
        tout += to
        votos = 0
        fora_algum = False
        for v, reps in dados.items():
            j, t, alvo = _metricas(reps)
            ok = j >= 0.60 and (t is not None and t >= 0.50) and alvo in (0, REPS)
            votos += ok
            fora_algum = fora_algum or _fora_cat(reps)
            ts = f"{t:.2f}" if t is not None else "n/a"
            print(
                f"  {v:7} Jaccard={j:.2f} tau={ts} alvo={alvo}/3 fora_cat={_fora_cat(reps)}"
                f"  {'CONVERGE' if ok else '-'}"
            )
            print(f"          rep1: {reps[0][:6]}")
        m_ok = votos >= 2  # within-model e o gate; maioria dos modelos
        conv += m_ok
        if not fora_algum:
            sem_fora += 1
        print(
            f"  -> momento {'CONVERGE' if m_ok else 'NAO'} ({votos}/3 modelos) - "
            f"fora-de-categoria: {'SIM' if fora_algum else 'NAO (falseamento)'}"
        )

    custo = tin / 1e6 * 3.0 + tout / 1e6 * 12.0
    print("\n=== VEREDITO ===")
    print(
        f"convergem: {conv}/3 - Mapa OK: {mapa_ok} - momentos SEM fora-de-categoria: {sem_fora}/3"
    )
    falseou = sem_fora >= 2  # 4o criterio: so locadoras em >=2 momentos -> REPROVA
    passa = conv >= 2 and mapa_ok and not falseou
    if falseou:
        print("REPROVA - falseamento §6: so locadoras em >=2 momentos (estavel e inutil)")
    else:
        print("PASSA - construir" if passa else "REPROVA - sem leitura confiavel, parar")
    print(f"custo real: ~US$ {custo:.2f}  (tokens in={tin} out={tout})")


if __name__ == "__main__":
    main()
