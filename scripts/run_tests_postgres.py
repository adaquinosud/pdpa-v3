"""Roda a suíte de testes contra um Postgres REAL (não SQLite).

Sobe um Postgres efêmero via ``pgserver`` (binário self-contained, sem Docker),
seta ``TEST_DATABASE_URL`` e dispara o pytest — o ``conftest.py`` usa esse banco
quando a env está presente. Prova de PG-readiness do CP-1.1.

Uso:
    uv run python scripts/run_tests_postgres.py            # suíte inteira
    uv run python scripts/run_tests_postgres.py tests/test_painel.py -x

Requer ``pgserver`` e ``psycopg`` no venv (deps de dev).
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pgserver

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    data_dir = tempfile.mkdtemp(prefix="pdpa_pg_test_")
    print(f"[pg] subindo Postgres efêmero em {data_dir} …")
    server = pgserver.get_server(data_dir)
    try:
        uri = server.get_uri().replace("postgresql://", "postgresql+psycopg://")
        print(f"[pg] pronto: {uri.split('@')[-1]}")
        env = {
            **__import__("os").environ,
            "TEST_DATABASE_URL": uri,
            "PYTHONPATH": str(ROOT),
        }
        args = sys.argv[1:] or ["-q", "-p", "no:cacheprovider"]
        print(f"[pg] pytest {' '.join(args)}")
        return subprocess.run(
            [sys.executable, "-m", "pytest", *args], cwd=str(ROOT), env=env
        ).returncode
    finally:
        print("[pg] derrubando Postgres …")
        server.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
