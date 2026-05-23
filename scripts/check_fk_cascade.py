"""Smoke-test do PRAGMA foreign_keys via db_session().

Insere Empresa + 2 Locais via ORM. Deleta a Empresa com `DELETE FROM empresas`
em SQL puro (bypassa o cascade do ORM, força enforcement no nível do banco).
Verifica que os Locais sumiram por cascata da FK ON DELETE CASCADE.

Se o PRAGMA estiver OFF, os Locais ficariam órfãos e o assert falha.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

import src.models  # noqa: E402, F401  registra Base.metadata
from src.models import Empresa, Local  # noqa: E402
from src.utils.db import db_session, get_engine  # noqa: E402


def main() -> None:
    engine = get_engine()

    # Limpa qualquer resíduo de execução anterior (UNIQUE(nome) na tabela).
    with db_session() as s:
        s.execute(text("DELETE FROM empresas WHERE nome = 'Cascade Test SA'"))

    # 1. Confirma que o PRAGMA está ON
    with engine.connect() as conn:
        pragma = conn.execute(text("PRAGMA foreign_keys")).scalar()
        print(f"PRAGMA foreign_keys = {pragma} (esperado 1)")

    # 2. Insere Empresa + 2 Locais via ORM
    with db_session() as s:
        e = Empresa(nome="Cascade Test SA", setor="teste")
        e.locais = [Local(nome="L1"), Local(nome="L2")]
        s.add(e)
        s.flush()
        empresa_id = e.id
    print(f"Empresa criada: id={empresa_id}, 2 locais")

    # 3. Confirma os Locais no banco
    with db_session() as s:
        n_antes = s.query(Local).filter_by(empresa_id=empresa_id).count()
    print(f"Locais antes do DELETE: {n_antes} (esperado 2)")

    # 4. DELETE FROM empresas via SQL puro (bypassa o cascade do ORM)
    with db_session() as s:
        s.execute(text("DELETE FROM empresas WHERE id = :id"), {"id": empresa_id})
    print(f"Executado: DELETE FROM empresas WHERE id={empresa_id} (raw SQL)")

    # 5. Os Locais devem ter sumido pelo cascade do banco
    with db_session() as s:
        n_depois = s.query(Local).filter_by(empresa_id=empresa_id).count()
    print(f"Locais depois do DELETE: {n_depois} (esperado 0)")

    assert n_depois == 0, (
        "FALHA: PRAGMA foreign_keys não está ativo — "
        f"locais ficaram órfãos no banco (count={n_depois})"
    )
    print("\nOK — PRAGMA foreign_keys ativo e ON DELETE CASCADE funcionando.")


if __name__ == "__main__":
    main()
