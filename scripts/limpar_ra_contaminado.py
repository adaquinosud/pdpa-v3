"""Limpa a contaminação de uma coleta RA com alvo errado (ex.: Sebracom sob o
Club Med) e recomputa os derivados da empresa.

  --list                  : lista as fontes reclame_aqui (id · empresa · url · nº casos)
  --fonte <id>            : limpa essa fonte + recomputa (pós-coleta retroativo)
  --fonte <id> --dry-run  : só mostra as contagens ANTES (não apaga)

Roda no Shell do Render (prod). Imprime contagens ANTES/DEPOIS pra provar que zerou.
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
            print(f"  fonte {f.id} · empresa {f.empresa_id} · casos={n} · url={f.url}")


def _contagem_dry(fonte_id: int):
    from src.coletor.limpeza_ra import _contar
    from src.models.fonte import Fonte
    from src.models.verbatim import Verbatim

    with db_session() as s:
        f = s.get(Fonte, fonte_id)
        if f is None:
            print(f"fonte {fonte_id} não encontrada")
            return
        vids = [r[0] for r in s.query(Verbatim.id).filter(Verbatim.fonte_id == fonte_id).all()]
        print(f"[dry-run] fonte {fonte_id} (empresa {f.empresa_id}) · {f.url}")
        print(f"[dry-run] ANTES: {_contar(s, f.empresa_id, fonte_id, vids)}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Limpeza de contaminação RA.")
    ap.add_argument("--list", action="store_true", help="lista as fontes reclame_aqui")
    ap.add_argument("--fonte", type=int, default=None, help="id da fonte a limpar")
    ap.add_argument("--dry-run", action="store_true", help="só mostra contagens, não apaga")
    args = ap.parse_args()

    if args.list:
        _listar()
        return 0
    if args.fonte is None:
        ap.error("informe --list ou --fonte <id>")
    if args.dry_run:
        _contagem_dry(args.fonte)
        return 0

    from src.coletor.limpeza_ra import limpar_contaminacao_ra
    from src.temas.pos_coleta import executar_pos_coleta

    r = limpar_contaminacao_ra(args.fonte)
    if "erro" in r:
        print(f"[limpeza] {r['erro']}")
        return 1
    print(f"[limpeza] fonte {args.fonte} · empresa {r['empresa_id']} · url={r['url']}")
    print(f"[limpeza] ANTES : {r['antes']}")
    print(f"[limpeza] DEPOIS: {r['depois']}")
    print("[limpeza] recomputando (pós-coleta retroativo)…")
    resumo = executar_pos_coleta(r["empresa_id"], force=True, aplicar_janela=False)
    print(
        f"[limpeza] recomputado: classificados={resumo.classificados} "
        f"clusters={resumo.clusters_rotulados} diagnóstico={resumo.diagnostico_gerados}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
