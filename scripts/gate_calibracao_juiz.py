"""Gate de calibração do LLM-juiz no DEPLOY (CP-Pesquisa-F1.4).

Roda no ``preDeployCommand`` do Render (que tem rede + ``ANTHROPIC_API_KEY`` via
env group). Chama o juiz REAL **uma vez** (batelada) contra o golden set
semântico e BLOQUEIA o deploy se a calibração regrediu:
 - falso-positivo em caso LIMPO (juiz acusando pergunta boa), ou
 - violação esperada não flagada.

Este é o ÚNICO ponto que chama o juiz real; o CI segue mockado. A lógica de
decisão (``rodar_gate``) é injetável p/ teste sem rede.

Saída: 0 = calibrado · 1 = calibração regrediu (bloqueia) · 2 = erro ao executar.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pesquisa.calibracao import GOLDEN_SET_JUIZ, perguntas_calibracao  # noqa: E402
from src.pesquisa.juiz import avaliar_perguntas  # noqa: E402


def rodar_gate(
    juiz_fn: Optional[Callable[[str, str], Dict[str, Any]]] = None,
) -> Tuple[bool, List, List]:
    """Avalia o golden set (1 chamada batelada) e devolve ``(ok, falsos_positivos,
    faltas)``. ``juiz_fn`` injetável p/ teste; default = juiz real."""
    veredito = avaliar_perguntas(perguntas_calibracao(), juiz_fn=juiz_fn)
    por_ordem = {p["ordem"]: {r["regra"] for r in p["regras"]} for p in veredito["perguntas"]}

    falsos_positivos: List = []
    faltas: List = []
    for i, (cid, _enun, _fmt, _sub, _opcoes, regra) in enumerate(GOLDEN_SET_JUIZ, 1):
        flags = por_ordem.get(i, set())
        if regra is None:
            if flags:
                falsos_positivos.append((cid, sorted(flags)))
        elif regra not in flags:
            faltas.append((cid, regra, sorted(flags)))

    return (not falsos_positivos and not faltas), falsos_positivos, faltas


def main() -> int:
    print(f"[gate-juiz] calibrando o LLM-juiz: {len(GOLDEN_SET_JUIZ)} casos, 1 chamada...")
    try:
        ok, falsos_positivos, faltas = rodar_gate()
    except Exception as exc:  # rede/chave/parse — não passa o gate sem rodar de fato
        print(f"[gate-juiz] ERRO ao executar o juiz: {exc}", file=sys.stderr)
        return 2

    for cid, flags in falsos_positivos:
        print(
            f"[gate-juiz] FALSO-POSITIVO em '{cid}' (limpo) — juiz acusou {flags}", file=sys.stderr
        )
    for cid, regra, flags in faltas:
        print(f"[gate-juiz] FALTOU a regra {regra} em '{cid}' — veio {flags}", file=sys.stderr)

    if ok:
        print("[gate-juiz] OK — 0 falso-positivo nos limpos e violações flagadas.")
        return 0
    print("[gate-juiz] BLOQUEADO — a calibração do juiz regrediu (ver acima).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
