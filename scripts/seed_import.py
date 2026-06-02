"""FASE 2 do seed de produção (CP-seed-cadastro-prod): IMPORT no Postgres.

Lê o JSON da FASE 1 e insere o cadastro no banco-alvo (``DATABASE_URL``), na
ordem de FK, com ID EXPLÍCITO (preserva as FKs). Corrige as sequences (PG) pra o
próximo cadastro pela UI não colidir com um ID migrado.

Idempotência (a opção mais SEGURA): se a empresa já existe no alvo, é **NO-OP** —
não duplica e NÃO trunca. (Truncar seria perigoso pós-recoleta: ``fontes`` tem
``verbatins`` com FK ON DELETE CASCADE → truncar fonte apagaria verbatins.)

Glossário: rodar ``scripts/seed_glossario.py`` à parte (não passa por aqui).

Uso: DATABASE_URL=postgresql://... uv run python scripts/seed_import.py \
         [--in data/seed_cadastro_prod.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import DateTime, create_engine, insert, select, text  # noqa: E402
from sqlalchemy.engine import Connection  # noqa: E402

from src.models.agrupamento import Agrupamento  # noqa: E402
from src.models.empresa import Empresa  # noqa: E402
from src.models.fonte import Fonte  # noqa: E402
from src.models.local import Local  # noqa: E402
from src.utils.db_url import normalize_db_url  # noqa: E402

# Mesma ordem de FK do export.
TABELAS = [Empresa, Agrupamento, Local, Fonte]


def _parse_datas(row: dict, t) -> dict:
    """Reidrata colunas DateTime (ISO string → datetime) pro insert no alvo."""
    dt_cols = {c.name for c in t.columns if isinstance(c.type, DateTime)}
    r = dict(row)
    for k in dt_cols:
        if r.get(k):
            r[k] = datetime.fromisoformat(r[k])
    return r


def importar(data: dict, conn: Connection) -> dict:
    """Insere o cadastro do JSON na conexão-alvo (transação do chamador).

    NO-OP se a empresa já existe (idempotente). Reseta as sequences no Postgres.
    Retorna um resumo {status, ...}."""
    empresa_id = data["empresa_id"]
    et = Empresa.__table__
    ja = conn.execute(select(et.c.id).where(et.c.id == empresa_id)).first()
    if ja is not None:
        return {"status": "skip", "motivo": f"empresa {empresa_id} já existe no alvo (no-op)"}

    inseridos: dict = {}
    for Model in TABELAS:
        t = Model.__table__
        rows = [_parse_datas(r, t) for r in data["tabelas"].get(t.name, [])]
        if rows:
            conn.execute(insert(t), rows)
        inseridos[t.name] = len(rows)

    # Reset de sequences (só Postgres — SQLite usa rowid e já avança sozinho).
    if conn.dialect.name == "postgresql":
        for Model in TABELAS:
            t = Model.__table__
            maxid = conn.execute(text(f"SELECT MAX(id) FROM {t.name}")).scalar()
            if maxid is not None:
                conn.execute(
                    text(f"SELECT setval(pg_get_serial_sequence('{t.name}', 'id'), {int(maxid)})")
                )

    return {"status": "ok", "inseridos": inseridos}


def main() -> None:
    p = argparse.ArgumentParser(description="Import do cadastro (FASE 2 do seed de prod)")
    p.add_argument("--in", dest="inp", default=str(ROOT / "data" / "seed_cadastro_prod.json"))
    a = p.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("[seed_import] DATABASE_URL não setada (alvo de prod).", file=sys.stderr)
        raise SystemExit(2)

    data = json.loads(Path(a.inp).read_text())
    eng = create_engine(normalize_db_url(url))
    try:
        with eng.begin() as conn:
            res = importar(data, conn)
    finally:
        eng.dispose()

    print(f"[seed_import] {res}")
    if res["status"] == "skip":
        print("[seed_import] nada a fazer — cadastro já presente.")
    else:
        print("[seed_import] cadastro inserido. Próximo: seed_glossario.py + recoleta.")


if __name__ == "__main__":
    main()
