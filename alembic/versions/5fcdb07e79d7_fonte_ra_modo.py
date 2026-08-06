"""Fonte.ra_modo ('padrao'|'completo') — modo de coleta RA (abertura vs +thread).

ADITIVA: coluna nova com server_default='padrao' → toda fonte existente (RA ou não)
nasce 'padrao'. Só o coletor RA lê o campo; 'padrao' = includeInteractions False
(abertura imutável, sem re-visita/OOM). Nada mais muda.

Revision ID: 5fcdb07e79d7
Revises: f4a5b6c7d8e9
Create Date: 2026-08-05 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5fcdb07e79d7"
down_revision: Union[str, None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "fontes",
        sa.Column("ra_modo", sa.String(), nullable=True, server_default="padrao"),
    )


def downgrade() -> None:
    op.drop_column("fontes", "ra_modo")
