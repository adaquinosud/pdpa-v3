"""CLI de recoleta de THREADS RA (modo B) — rede de segurança da Fatia 2.

Enquanto o botão dedicado (Fatia 5) e o cron mensal (Fatia 4) não existem, este
é o caminho pra baixar as threads/casos de uma fonte RA sob demanda (emergência,
fechar parecer). O roteamento noturno faz só o scorecard; threads NÃO saem por lá.

AÇÃO PAGA (Apify PPE): ~US$0,025/reclamação + US$0,005 start. Dimensione pela
janela (a coorte mensal da Localiza ~1.189 ≈ US$29,75). Exige --sim pra disparar.

Uso:
    PYTHONPATH=. python scripts/recoletar_threads.py --fonte 116 [--desde AAAA-MM-DD]
        [--ate AAAA-MM-DD] [--sim]

Sem --sim: DRY-RUN (mostra o que faria + custo estimado, não chama o actor).
--desde/--ate: coorte fechada (dateFrom+dateTo); omitindo --ate = janela deslizante.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.coletor.reclame_aqui import (  # noqa: E402
    CUSTO_POR_CASO_USD,
    CUSTO_START_USD,
    coletar_threads,
)
from src.models.fonte import Fonte  # noqa: E402
from src.models.fonte_reputacao import FonteReputacao  # noqa: E402
from src.utils.db import db_session  # noqa: E402


def _estimativa_custo(fonte_id: int) -> str:
    """Estima o custo pelo volume mensal do scorecard (complaints30Days), se houver."""
    import json

    with db_session() as s:
        rep = s.query(FonteReputacao).filter_by(fonte_id=fonte_id).one_or_none()
        vol = None
        if rep is not None and rep.raw_json:
            try:
                vol = json.loads(rep.raw_json).get("complaints30Days")
            except (ValueError, TypeError):
                vol = None
    if vol:
        usd = vol * CUSTO_POR_CASO_USD + CUSTO_START_USD
        return f"~{vol} reclam./mês → ~US${usd:.2f} (data-driven pelo scorecard)"
    return "volume desconhecido (sem scorecard ainda) — custo = nº retornado × US$0,025"


def main() -> None:
    ap = argparse.ArgumentParser(description="Recoleta de threads RA (modo B) sob demanda.")
    ap.add_argument("--fonte", type=int, required=True, help="fonte_id RA")
    ap.add_argument("--desde", help="dateFrom ISO (AAAA-MM-DD); omitido = janela deslizante")
    ap.add_argument("--ate", help="dateTo ISO (AAAA-MM-DD); com --desde = coorte fechada")
    ap.add_argument("--sim", action="store_true", help="confirma o disparo PAGO (sem = dry-run)")
    args = ap.parse_args()

    with db_session() as s:
        fonte = s.get(Fonte, args.fonte)
        if fonte is None or fonte.conector_tipo != "reclame_aqui":
            print(f"[threads] fonte {args.fonte} não é RA (ou não existe) — abortando")
            sys.exit(1)
        s.expunge(fonte)

    print(
        f"[threads] fonte={args.fonte} desde={args.desde or '(deslizante)'} "
        f"ate={args.ate or '—'}"
    )
    print(f"[threads] custo estimado: {_estimativa_custo(args.fonte)}")
    if not args.sim:
        print("[threads] DRY-RUN (sem --sim) — nada disparado. Reveja o custo e rode com --sim.")
        return

    print("[threads] disparando (force=True, ignora cadência)…")
    stats = coletar_threads(fonte, force=True, date_from=args.desde, date_to=args.ate)
    print(f"[threads] fim: {stats}")


if __name__ == "__main__":
    main()
