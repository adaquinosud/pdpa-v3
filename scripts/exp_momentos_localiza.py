"""⚠️ EXPERIMENTO DESCARTÁVEL — NÃO É FEATURE. Remover após o resultado.

Data: 2026-08-17. O que testa: ESTABILIDADE da leitura "Momentos/Ocupação" (degraus 1-2
do Capital de Escolha) para UMA empresa (Localiza), ANTES de decidir construir a frente.
Pergunta ao LLM (não toca o corpus). Roda no Render (chaves em env).

⚠️ FIX 2026-08-17 (1ª rodada deu GPT/Gemini VAZIOS): não era parse — o cap MAX_OUT_TOKENS=500
dos adapters era comido pelo RACIOCÍNIO (GPT reasoning) / THINKING (Gemini), zerando o texto.
Aqui: chamadas próprias com GPT reasoning_effort=minimal + cap 1500 e Gemini thinkingBudget=0.
NÃO toca os adapters compartilhados (mudaria a sonda de reputação — que provavelmente sofre o
mesmo bug e roda Claude-only; investigar à parte). Custo re-pinado ~US$0.30 (teto US$5);
imprime custo REAL + tokens/vazios POR MODELO no fim.

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
import urllib.request
from itertools import combinations
from statistics import mean

from scipy.stats import kendalltau

from src.config import get_config
from src.sonda_ia.adapters import chamar_claude

REPS = 3
ALVO = "localiza"
PRECO = {"claude": (3.0, 15.0), "gpt": (1.25, 10.0), "gemini": (0.30, 2.50)}
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


def _gpt(prompt):
    """GPT-5 com reasoning_effort=minimal + cap 1500 (o 'low'+500 dos adapters zerava o texto)."""
    key = get_config().OPENAI_API_KEY
    if not key:
        raise ValueError("OPENAI_API_KEY ausente")
    body = {
        "model": "gpt-5",
        "messages": [{"role": "user", "content": prompt}],
        "max_completion_tokens": 1500,
        "reasoning_effort": "minimal",
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    u = d.get("usage", {})
    return {
        "texto": d["choices"][0]["message"].get("content") or "",
        "tokens_in": int(u.get("prompt_tokens", 0) or 0),
        "tokens_out": int(u.get("completion_tokens", 0) or 0),
    }


def _gemini(prompt):
    """Gemini 2.5 Flash com thinkingBudget=0 (o thinking ligado comia o cap e zerava o texto)."""
    key = get_config().GOOGLE_API_KEY
    if not key:
        raise ValueError("GOOGLE_API_KEY ausente")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={key}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 800, "thinkingConfig": {"thinkingBudget": 0}},
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.load(r)
    cand = (d.get("candidates") or [{}])[0]
    parts = ((cand.get("content") or {}).get("parts")) or [{}]
    u = d.get("usageMetadata", {})
    return {
        "texto": parts[0].get("text", ""),
        "tokens_in": int(u.get("promptTokenCount", 0) or 0),
        "tokens_out": int(u.get("candidatesTokenCount", 0) or 0),
    }


def _claude(prompt):
    r = chamar_claude(prompt)
    return {"texto": r["texto"], "tokens_in": r["tokens_in"], "tokens_out": r["tokens_out"]}


VENDORS = {"claude": _claude, "gpt": _gpt, "gemini": _gemini}
STATS = {v: {"in": 0, "out": 0, "vazio": 0, "n": 0} for v in VENDORS}


def _lista(txt):
    """Extrai o 1º array JSON de STRINGS — robusto a fence ```json e a citações [1] em prosa."""
    for m in re.finditer(r"\[[^\[\]]*\]", txt, re.DOTALL):
        try:
            arr = json.loads(m.group(0))
        except Exception:  # noqa: BLE001
            continue
        if isinstance(arr, list) and arr and all(isinstance(x, str) for x in arr):
            return [x.strip().lower() for x in arr if x.strip()]
    return None


def _jaccard(a, b):
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if (sa | sb) else 0.0


def _tau(a, b):
    comuns = [x for x in a if x in b]
    if len(comuns) < 2:
        return None
    t, _ = kendalltau([a.index(x) for x in comuns], [b.index(x) for x in comuns])
    return t


def _coletar(prompt):
    out = {}
    for v, fn in VENDORS.items():
        out[v] = []
        for _ in range(REPS):
            r = fn(prompt)
            STATS[v]["in"] += r.get("tokens_in", 0)
            STATS[v]["out"] += r.get("tokens_out", 0)
            STATS[v]["n"] += 1
            lst = _lista(r.get("texto", ""))
            if not lst:
                STATS[v]["vazio"] += 1
            out[v].append(lst or [])
    return out


def _fora_cat(reps):
    return any(any(any(k in c for k in FORA_CAT) for c in r) for r in reps)


def _metricas(reps):
    pares = list(combinations(range(len(reps)), 2))
    js = [_jaccard(reps[i], reps[j]) for i, j in pares]
    ts = [t for i, j in pares if (t := _tau(reps[i], reps[j])) is not None]
    alvo = sum(1 for r in reps if any(ALVO in c for c in r))
    return (mean(js) if js else 0.0), (mean(ts) if ts else None), alvo


def main():
    print("=== MAPA (estabilidade da enumeração) ===")
    mapa = _coletar(MAPA)
    mapa_js = []
    for v, reps in mapa.items():
        j, _t, _a = _metricas(reps)
        mapa_js.append(j)
        print(f"  {v:7} Jaccard={j:.2f}  (ex rep1: {reps[0][:4]})")
    mapa_ok = mean(mapa_js) >= 0.50
    print(f"  -> Mapa Jaccard medio {mean(mapa_js):.2f}  ({'OK >=0.50' if mapa_ok else 'BAIXO'})")

    conv = 0
    sem_fora = 0
    for m in MOMENTOS:
        print(f"\n=== OCUPACAO: {m!r} ===")
        dados = _coletar(OCUP.format(m=m))
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
        m_ok = votos >= 2
        conv += m_ok
        if not fora_algum:
            sem_fora += 1
        print(
            f"  -> momento {'CONVERGE' if m_ok else 'NAO'} ({votos}/3 modelos) - "
            f"fora-de-categoria: {'SIM' if fora_algum else 'NAO (falseamento)'}"
        )

    print("\n=== POR MODELO (prova do fix: vazios devem ser 0) ===")
    custo = 0.0
    for v, s in STATS.items():
        pin, pout = PRECO[v]
        c = s["in"] / 1e6 * pin + s["out"] / 1e6 * pout
        custo += c
        print(
            f"  {v:7} chamadas={s['n']} vazios={s['vazio']} in={s['in']} out={s['out']} ~US${c:.2f}"
        )

    print("\n=== VEREDITO ===")
    print(
        f"convergem: {conv}/3 - Mapa OK: {mapa_ok} - momentos SEM fora-de-categoria: {sem_fora}/3"
    )
    falseou = sem_fora >= 2
    passa = conv >= 2 and mapa_ok and not falseou
    if falseou:
        print("REPROVA - falseamento §6: so locadoras em >=2 momentos (estavel e inutil)")
    else:
        print("PASSA - construir" if passa else "REPROVA - sem leitura confiavel, parar")
    print(f"custo real total: ~US$ {custo:.2f}")


if __name__ == "__main__":
    main()
