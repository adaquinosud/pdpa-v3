"""coleta_noturna_toggle: empresas.coleta_noturna_ativa (default FALSE; Confins TRUE)

Toggle por empresa do cron noturno (CP-coleta-noturna-toggle). A noturna passa a
varrer só as empresas com ``coleta_noturna_ativa=TRUE``.

  - Coluna NOT NULL com server_default=false → empresa nova NÃO coleta à noite até
    ligar explicitamente (decisão de produto).
  - Backfill: marca a empresa 4 (Confins) como TRUE — ela está validada e já coleta
    à noite hoje; não pode ser interrompida.

Aditiva, Postgres-safe (só ADD COLUMN + 1 UPDATE pontual por id).

Revision ID: c3f8a1d29b04
Revises: b7e3f9a2c1d8
Create Date: 2026-06-11 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f8a1d29b04"
down_revision: Union[str, None] = "b7e3f9a2c1d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "empresas",
        sa.Column(
            "coleta_noturna_ativa",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    # Confins (empresa 4) já coleta à noite e está validada → mantém ligada.
    op.execute("UPDATE empresas SET coleta_noturna_ativa = true WHERE id = 4")


def downgrade() -> None:
    with op.batch_alter_table("empresas") as batch:
        batch.drop_column("coleta_noturna_ativa")
