"""Corrige o GRÃO de uma fonte RA cadastrada sob um local: re-graneia os
casos/verbatins pro nível empresa (local_id=NULL) + limpa o cache de temas do
agrupamento órfão + recompõe os temas (pós-coleta retroativo).

  --list                  : lista as fontes reclame_aqui (id · empresa · url · nº casos)
  --fonte <id>            : re-graneia essa fonte + rebuild dos temas
  --fonte <id> --dry-run  : só mostra o grão atual dos verbatins/casos (não altera)

Roda no Shell do Render (prod). Imprime contagens ANTES/DEPOIS.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.utils.db import db_session  # noqa: E402


def _listar():
    from src.models.caso import Caso
    from src.models.fonte import Fonte

    with db_session() as s:
        fontes = s.query(Fonte).filter(Fonte.conector_tipo == "reclame_aqui").all()
        print(f"fontes reclame_aqui: {len(fontes)}")
        for f in fontes:
            n = s.query(Caso).filter(Caso.fonte_id == f.id).count()
            print(
                f"  fonte {f.id} · empresa {f.empresa_id} · "
                f"entidade={f.entidade_tipo}#{f.entidade_id} · casos={n} · url={f.url}"
            )


def _dry(fonte_id: int):
    from sqlalchemy import func

    from src.models.caso import Caso
    from src.models.fonte import Fonte
    from src.models.verbatim import Verbatim

    with db_session() as s:
        f = s.get(Fonte, fonte_id)
        if f is None:
            print(f"fonte {fonte_id} não encontrada")
            return
        vg = (
            s.query(Verbatim.local_id, func.count())
            .filter(Verbatim.fonte_id == fonte_id)
            .group_by(Verbatim.local_id)
            .all()
        )
        cg = (
            s.query(Caso.local_id, func.count())
            .filter(Caso.fonte_id == fonte_id)
            .group_by(Caso.local_id)
            .all()
        )
        print(f"[dry-run] fonte {fonte_id} (empresa {f.empresa_id}) · {f.url}")
        print(f"[dry-run] verbatins por local_id: {vg}  (None = empresa-wide)")
        print(f"[dry-run] casos por local_id:     {cg}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Correção de grão de fonte RA.")
    ap.add_argument("--list", action="store_true", help="lista as fontes reclame_aqui")
    ap.add_argument("--fonte", type=int, default=None, help="id da fonte a re-granear")
    ap.add_argument("--dry-run", action="store_true", help="só mostra o grão atual, não altera")
    args = ap.parse_args()

    if args.list:
        _listar()
        return 0
    if args.fonte is None:
        ap.error("informe --list ou --fonte <id>")
    if args.dry_run:
        _dry(args.fonte)
        return 0

    from src.coletor.regrao_ra import regrao_empresa_wide
    from src.temas.pos_coleta import executar_pos_coleta

    r = regrao_empresa_wide(args.fonte)
    print(f"[regrão] fonte {args.fonte} · empresa {r['empresa_id']}")
    print(
        f"[regrão] agrupamento_antigo={r['agrupamento_antigo']} · "
        f"verbatins→NULL={r['verbatins']} · casos→NULL={r['casos']} · "
        f"cache_removido={r['cache_removido']}"
    )
    print("[regrão] recompondo temas (pós-coleta retroativo)…")
    resumo = executar_pos_coleta(r["empresa_id"], force=True, aplicar_janela=False)
    print(
        f"[regrão] recomputado: classificados={resumo.classificados} "
        f"clusters={resumo.clusters_rotulados}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
