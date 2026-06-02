"""FASE 1 do seed de produção (CP-seed-cadastro-prod): EXPORT read-only.

Lê do SQLite dev (read-only) SÓ o cadastro de UMA empresa — ``empresas[id]``,
``agrupamentos``, ``locais``, ``fontes`` — e gera um JSON legível para REVISÃO
antes de aplicar em prod (FASE 2 = ``scripts/seed_import.py``).

NÃO exporta verbatins nem derivados (recoleta + recalcula em prod). NÃO exporta o
glossário: o texto aprovado dos 77 termos é idêntico ao ``scripts/seed_glossario.py``
(conferido) → em prod roda-se aquele script, não migra a tabela.

Preserva os IDs (as FKs dependem: fonte.entidade_id→local, local.agrupamento_id→
agrupamento). Ordem de FK fixada em ``TABELAS``.

Uso: uv run python scripts/seed_export.py [--empresa 4]
         [--dev-db pdpa_v3_dev.db] [--out data/seed_cadastro_prod.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

from src.models.agrupamento import Agrupamento  # noqa: E402
from src.models.empresa import Empresa  # noqa: E402
from src.models.fonte import Fonte  # noqa: E402
from src.models.local import Local  # noqa: E402

# Ordem de FK — export e import seguem a mesma.
TABELAS = [Empresa, Agrupamento, Local, Fonte]


def _ser(v):
    """Serializa valores não-JSON (datetime/date → ISO)."""
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def exportar(source_engine: Engine, empresa_id: int) -> dict:
    """Lê as 4 tabelas de cadastro da empresa do engine de origem e devolve um
    dict pronto pra serializar (IDs preservados)."""
    out: dict = {"empresa_id": empresa_id, "tabelas": {}}
    with source_engine.connect() as conn:
        for Model in TABELAS:
            t = Model.__table__
            # 'empresas' filtra por id; as demais por empresa_id.
            coluna = t.c.id if t.name == "empresas" else t.c.empresa_id
            stmt = select(t).where(coluna == empresa_id).order_by(t.c.id)
            out["tabelas"][t.name] = [
                {k: _ser(v) for k, v in row._mapping.items()} for row in conn.execute(stmt)
            ]
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Export do cadastro (FASE 1 do seed de prod)")
    p.add_argument("--empresa", type=int, default=4, help="empresa_id a exportar (default 4)")
    p.add_argument("--dev-db", default=str(ROOT / "pdpa_v3_dev.db"), help="SQLite dev de origem")
    p.add_argument("--out", default=str(ROOT / "data" / "seed_cadastro_prod.json"))
    a = p.parse_args()

    eng = create_engine(f"sqlite:///{a.dev_db}")
    try:
        data = exportar(eng, a.empresa)
    finally:
        eng.dispose()

    out_path = Path(a.out)
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    counts = {t: len(rows) for t, rows in data["tabelas"].items()}
    print(f"[seed_export] empresa={a.empresa} → {out_path}")
    print(f"[seed_export] contagens: {counts}")
    print("[seed_export] REVISE o JSON antes de aplicar (FASE 2: scripts/seed_import.py).")


if __name__ == "__main__":
    main()
