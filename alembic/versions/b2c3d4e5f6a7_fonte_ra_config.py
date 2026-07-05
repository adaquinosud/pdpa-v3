"""fonte: config de coleta RA por fonte (janela_meses + max_casos).

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-04

Override opcional por fonte da janela (meses) e do cap (máx. casos) da coleta
ReclameAqui. NULL = defaults globais do coletor. Aditiva.
"""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fontes", sa.Column("ra_janela_meses", sa.Integer(), nullable=True))
    op.add_column("fontes", sa.Column("ra_max_casos", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("fontes", "ra_max_casos")
    op.drop_column("fontes", "ra_janela_meses")
