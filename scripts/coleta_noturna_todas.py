"""Noturna de TODAS as empresas LIGADAS (CP-noturna-toggle).

Enumera as empresas com ``coleta_noturna_ativa=TRUE`` **E** ≥1 fonte ativa com
coletor, e roda o pipeline noturno (``run_noturna.sh``) por empresa, em loop.
Reusa o pipeline por-empresa de hoje (coleta incremental → pós-coleta → relatório):
o incremental é **por-fonte** (15 meses / desde o último review), sem all-time e
sem interferência cruzada entre empresas.

  --dry-run : lista as empresas que coletaria, SEM coletar (validação).

Roda no Shell do Render / no cron. O ``render.yaml`` aponta o cron pra
``run_noturna_todas.sh`` (wrapper deste script).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.models.empresa import Empresa  # noqa: E402
from src.models.fonte import Fonte  # noqa: E402
from src.utils.db import db_session  # noqa: E402


def empresas_elegiveis() -> List[Tuple[int, str, int]]:
    """Empresas com ``coleta_noturna_ativa=TRUE`` e ≥1 fonte ATIVA com coletor.
    Retorna ``[(id, nome, n_fontes_coletaveis)]`` ordenado por id."""
    from src.api.coleta import _roteamento_coletores

    suportados = set(_roteamento_coletores().keys())
    out: List[Tuple[int, str, int]] = []
    with db_session() as s:
        ligadas = (
            s.query(Empresa)
            .filter(Empresa.coleta_noturna_ativa.is_(True))
            .order_by(Empresa.id)
            .all()
        )
        for e in ligadas:
            n = (
                s.query(Fonte)
                .filter(
                    Fonte.empresa_id == e.id,
                    Fonte.ativo.is_(True),
                    Fonte.conector_tipo.in_(suportados),
                )
                .count()
            )
            if n > 0:
                out.append((e.id, e.nome, n))
    return out


def _guard_simbolos_residuais(dry_run: bool) -> None:
    """Guard auto-curável de símbolos residuais (CP-guard-simbolos): varre TODAS as
    empresas (não só as ligadas) e re-roda a redistribuição nas que têm símbolo
    preso no marcador provisório — pós-coleta que pulou (``novos < limiar``) ou
    morreu (daemon-thread). $0, determinístico, idempotente. Roda sempre, mesmo
    sem empresa coletando e no dry-run (que só lista)."""
    from src.coletor.distribuicao_simbolos import curar_simbolos_residuais

    print("\n" + "═" * 72)
    print("[guard-simbolos] varrendo resíduo (tem_texto=False, rating-heuristica-v1)…")
    g = curar_simbolos_residuais(dry_run=dry_run)
    if not g["curadas"]:
        print("[guard-simbolos] nenhum resíduo — nada a curar.")
    else:
        marca = " [DRY-RUN, não gravou]" if dry_run else ""
        for c in g["curadas"]:
            print(
                f"  • empresa {c['empresa_id']}: {c['total_simbolos']} símbolos redistribuídos "
                f"({c['saem_de_pa1']} saem de Pa1){marca}"
            )
    print("═" * 72)


def main(dry_run: bool) -> int:
    elegiveis = empresas_elegiveis()
    print("═" * 72)
    print(f"[noturna-todas] empresas LIGADAS com fonte coletável: {len(elegiveis)}")
    for eid, nome, n in elegiveis:
        print(f"  • empresa {eid:<4} {nome[:40]:40} fontes_coletáveis={n}")
    print("═" * 72)

    if dry_run:
        print(
            "[noturna-todas] DRY-RUN — nada coletado. Estas seriam coletadas (loop run_noturna.sh)."
        )
    elif not elegiveis:
        print("[noturna-todas] nenhuma empresa ligada com fonte — nada a coletar.")
    else:
        for eid, nome, _ in elegiveis:
            print(f"\n[noturna-todas] ▶ empresa {eid} ({nome}) — run_noturna.sh {eid}")
            # Reusa o pipeline por-empresa (coleta → pós-coleta → relatório), que já é
            # "não-para-por-nada"; uma empresa falhar não derruba as outras.
            subprocess.run(
                ["bash", str(ROOT / "scripts" / "run_noturna.sh"), str(eid)], cwd=str(ROOT)
            )
        print("\n[noturna-todas] FIM — todas as empresas ligadas processadas.")

    # Guard de símbolos residuais: roda DEPOIS da coleta (cura o que cada pós-coleta
    # deixou pra trás) e independe de haver empresa elegível.
    _guard_simbolos_residuais(dry_run)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Noturna de todas as empresas ligadas (CP-toggle).")
    ap.add_argument(
        "--dry-run", action="store_true", help="lista as empresas que coletaria, sem coletar"
    )
    args = ap.parse_args()
    raise SystemExit(main(args.dry_run))
