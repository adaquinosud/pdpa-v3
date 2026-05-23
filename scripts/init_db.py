"""Inicializa o banco aplicando todas as migrations em ordem."""

import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"
DB_PATH = os.getenv("DATABASE_URL", "sqlite:///pdpa_v3_dev.db").replace("sqlite:///", "")


def run_migrations():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
    for m in migrations:
        print(f"Aplicando {m.name}...")
        with open(m) as f:
            conn.executescript(f.read())
        conn.commit()

    conn.close()
    print(f"Banco inicializado em {DB_PATH}")


if __name__ == "__main__":
    run_migrations()
