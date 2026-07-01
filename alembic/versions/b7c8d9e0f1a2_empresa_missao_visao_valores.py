"""empresas: missao/visao/valores — essência declarada (ORIGEM fatia 1)

Três colunas Text nullable. A régua de profundidade do confronto (ORIGEM, fatia 2)
mede os gaps contra a essência DECLARADA da empresa. Aditiva, nullable, sem
server_default (empresas existentes nascem NULL). SQLite/Postgres-safe.

Revision ID: b7c8d9e0f1a2
Revises: f3a4b5c6d7e8
Create Date: 2026-07-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("empresas", sa.Column("missao", sa.Text(), nullable=True))
    op.add_column("empresas", sa.Column("visao", sa.Text(), nullable=True))
    op.add_column("empresas", sa.Column("valores", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("empresas", "valores")
    op.drop_column("empresas", "visao")
    op.drop_column("empresas", "missao")
