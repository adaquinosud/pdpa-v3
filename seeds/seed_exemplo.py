"""Seed mínimo de demonstração — empresa fictícia com 3 locais.

Popula o banco com dados neutros para teste e desenvolvimento. Não simula
cliente real. Não é idempotente — re-rodar falha nos UNIQUE constraints;
reinicie o banco com `python scripts/init_db.py` se precisar repetir.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bcrypt  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from src.models.agrupamento import Agrupamento  # noqa: E402
from src.models.empresa import Empresa  # noqa: E402
from src.models.local import Local  # noqa: E402
from src.models.usuario import Usuario  # noqa: E402

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///pdpa_v3_dev.db")


def seed() -> None:
    """Insere uma empresa fictícia, 3 locais, 1 agrupamento e 1 admin."""
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Empresa fictícia
    empresa = Empresa(
        nome="Empresa Demo",
        razao_social="Empresa Demo Ltda",
        setor="demo",
    )
    session.add(empresa)
    session.commit()

    # 2. Locais
    locais_dados = [
        {"nome": "Loja A"},
        {"nome": "Loja B"},
        {"nome": "Loja C"},
    ]
    locais = []
    for ld in locais_dados:
        local = Local(
            empresa_id=empresa.id,
            nome=ld["nome"],
            cidade="São Paulo",
            uf="SP",
        )
        session.add(local)
        session.commit()
        locais.append(local)

    # 3. Agrupamento "Grupo Principal" com Loja A
    grupo = Agrupamento(
        empresa_id=empresa.id,
        nome="Grupo Principal",
        tipo="lista",
    )
    session.add(grupo)
    session.commit()
    grupo.locais.append(locais[0])
    session.commit()

    # 4. Usuario admin
    senha_hash = bcrypt.hashpw(b"loyall2026", bcrypt.gensalt()).decode()
    admin = Usuario(
        email="admin@loyall.com",
        nome="Admin Loyall",
        senha_hash=senha_hash,
        papel="admin_loyall",
    )
    session.add(admin)
    session.commit()

    print("Seed concluído!")
    print(f"  Empresa: {empresa.nome} (id={empresa.id})")
    print(f"  Locais: {len(locais)}")
    print(f"  Agrupamento: {grupo.nome}")
    print(f"  Admin: {admin.email} / senha: loyall2026")


if __name__ == "__main__":
    seed()
