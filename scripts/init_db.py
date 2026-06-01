"""Inicializa/atualiza o schema do banco.

**Wrapper fino (CP-1.2):** o runner real do schema é o **Alembic**, não mais os
`.sql` (aposentados em `migrations/legacy/`). Este script roda `alembic upgrade
head` — quem usava `python scripts/init_db.py` não quebra, só é redirecionado.

A URL do banco é resolvida pelo `alembic/env.py` (env `DATABASE_URL` com fallback
no `SQLALCHEMY_DATABASE_URI` do projeto). Em produção, o release roda
`alembic upgrade head` direto (ver docs/ROADMAP_PRODUCAO.md, Bloco 4 #7).
"""

import subprocess
import sys

from dotenv import load_dotenv


def run_migrations() -> int:
    """Aplica o schema via Alembic. Retorna o exit code do alembic."""
    load_dotenv()
    print("[init_db] runner: alembic upgrade head (os .sql estão em migrations/legacy/)")
    return subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"]).returncode


if __name__ == "__main__":
    raise SystemExit(run_migrations())
