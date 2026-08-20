"""⚠️ EXPERIMENTO DESCARTÁVEL — NÃO É FEATURE. Remover após o resultado.

Data: 2026-08-20. Testa: o CLASSIFICADOR (Haiku, o modelo real de produção) consegue
atribuir a ETAPA DOMINANTE da jornada a um verbatim da Localiza? É a cautela do arco
de Momentos: saída plausível pode ter 2% de precisão; etapa é tarefa FECHADA (escolher
de 6) e provavelmente mais fácil — mas "provavelmente" não é medição.

NÃO grava nada (medição, não classificação). NÃO cria coluna/tabela/tela. A jornada
abaixo é fixa à mão SÓ para este teste.

Amostra ESTRATIFICADA (não aleatória): 25 do ReclameAqui (relato longo) + 25 do Google
(relato curto), p/ ver se a precisão cai no texto curto (que é a maioria do corpus).
Saída pede JSON {etapa, confianca, motivo}; "nenhuma" é resposta VÁLIDA (verbatim que
não fala de etapa não deve ser forçado numa).

Custo estimado ~US$0,05-0,15 (teto US$3). Imprime custo REAL no fim.
Uso no Render:  PYTHONPATH=. python scripts/exp_etapa_precisao_localiza.py [empresa=17]
"""

import json
import re
import sys

from src.classifier.classifier_v3 import HAIKU_MODEL, PRICING_USD_PER_MTOK, _get_client
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim as V
from src.utils.db import db_session

EMPRESA = int(sys.argv[1]) if len(sys.argv) > 1 else 17
N_POR_FONTE = 25
MAX_TEXTO = 1000  # enviado ao modelo (o display corta em 200)

RA_RX = re.compile(r"reclame|^ra$|ra_|_ra\b", re.IGNORECASE)
ETAPAS = ["reservar", "ir até o local", "retirar", "usar", "devolver", "pós-serviço"]
VALIDAS = set(ETAPAS) | {"nenhuma"}

PROMPT = (
    "JORNADA (experiência do cliente de uma LOCADORA de carros):\n"
    "1. reservar — escolher/reservar o carro (site, app, telefone, balcão)\n"
    "2. ir até o local — deslocamento/chegada à loja ou unidade\n"
    "3. retirar — pegar o carro (fila, cadastro, vistoria inicial, entrega das chaves)\n"
    "4. usar — período com o carro (o veículo em si, quebra, assistência na estrada)\n"
    "5. devolver — entregar o carro de volta (vistoria final, fila de devolução)\n"
    "6. pós-serviço — depois de devolver (cobrança, reembolso, SAC, multa, caução)\n\n"
    "Tarefa: dado um comentário de cliente, diga a ÚNICA etapa DOMINANTE de que ele fala.\n"
    'Se o comentário não fala de nenhuma etapa (ex.: "adoro a Localiza", elogio ou '
    'xingamento genérico), responda "nenhuma". NÃO force uma etapa.\n'
    'Responda SÓ JSON: {"etapa":"<uma das 6 exatas ou nenhuma>",'
    '"confianca":0.0-1.0,"motivo":"<=8 palavras"}\n\n'
    "Comentário: "
)


def _spread(items, k):
    """Amostra determinística espalhada (evita concentrar no início do id)."""
    if len(items) <= k:
        return items
    step = len(items) / k
    return [items[int(i * step)] for i in range(k)]


def _parse(txt):
    m = re.search(r"\{.*\}", txt or "", re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return None
    et = str(d.get("etapa", "")).strip().lower()
    et = et if et in VALIDAS else ("nenhuma" if not et else et)
    return {
        "etapa": et if et in VALIDAS else "INVALIDA:" + et,
        "conf": d.get("confianca"),
        "motivo": str(d.get("motivo", ""))[:60],
    }


def _short(t):
    return " ".join((t or "").split())[:200]


def _classificar(texto):
    cli = _get_client()
    r = cli.messages.create(
        model=HAIKU_MODEL,
        max_tokens=120,
        messages=[{"role": "user", "content": PROMPT + texto[:MAX_TEXTO]}],
    )
    txt = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
    u = r.usage
    return txt, int(u.input_tokens or 0), int(u.output_tokens or 0)


with db_session() as s:
    linhas = (
        s.query(V.id, V.texto, Fonte.conector_tipo)
        .outerjoin(Fonte, V.fonte_id == Fonte.id)
        .filter(V.empresa_id == EMPRESA, V.tem_texto.is_(True))
        .order_by(V.id)
        .all()
    )
    ra = [(i, t) for i, t, c in linhas if c and RA_RX.search(c)]
    gg = [(i, t) for i, t, c in linhas if c == "google"]
    print(f"empresa {EMPRESA}: {len(linhas)} c/texto | RA disp={len(ra)} Google disp={len(gg)}")
    amostra = [("RA", i, t) for i, t in _spread(ra, N_POR_FONTE)] + [
        ("google", i, t) for i, t in _spread(gg, N_POR_FONTE)
    ]
    if len(amostra) < 2 * N_POR_FONTE:
        print(f"⚠️ amostra incompleta ({len(amostra)}/{2*N_POR_FONTE}) — fonte sem volume.")

    tin = tout = 0
    dist = {e: 0 for e in list(ETAPAS) + ["nenhuma"]}
    dist_fonte = {"RA": dict(dist), "google": dict(dist)}
    invalidas = 0
    print("\n=== OS 50 (julgar um a um: a etapa atribuida esta certa?) ===")
    for fonte, vid, txt in amostra:
        raw, i_, o_ = _classificar(txt or "")
        tin += i_
        tout += o_
        p = _parse(raw) or {"etapa": "PARSE_FAIL", "conf": None, "motivo": raw[:40]}
        et = p["etapa"]
        if et in dist:
            dist[et] += 1
            dist_fonte[fonte][et] += 1
        else:
            invalidas += 1
        cf = f"{p['conf']:.2f}" if isinstance(p["conf"], (int, float)) else "?"
        print(f"[{fonte:6} #{vid}] {et:14} c={cf}  {p['motivo']}")
        print(f"        {_short(txt)!r}")

    print("\n=== 2) DISTRIBUICAO das etapas atribuidas ===")
    for e in list(ETAPAS) + ["nenhuma"]:
        print(f"  {e:14} {dist[e]:>3}")
    if invalidas:
        print(f"  {'INVALIDA/fail':14} {invalidas:>3}  (etapa fora da lista ou parse falhou)")

    print("\n=== 3) 'nenhuma' (nao forcado) ===")
    print(f"  nenhuma: {dist['nenhuma']} de {len(amostra)}  (verbatim sem etapa e saida valida)")

    print("\n=== 4) DISTRIBUICAO por fonte (precisao = teu julgamento manual por bloco) ===")
    for f in ("RA", "google"):
        linha = " ".join(f"{e[:6]}={dist_fonte[f][e]}" for e in list(ETAPAS) + ["nenhuma"])
        print(f"  {f:6} {linha}")

    custo = tin / 1e6 * PRICING_USD_PER_MTOK[HAIKU_MODEL]["input"]
    custo += tout / 1e6 * PRICING_USD_PER_MTOK[HAIKU_MODEL]["output"]
    print(f"\n=== 5) CUSTO REAL: ~US$ {custo:.3f}  (in={tin} out={tout}, Haiku) ===")
    print("Precisao NAO e automatica (nao ha gabarito) — julgue os 50 e conte por bloco RA/google.")
