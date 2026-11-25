"""custos_execucao: o odômetro — custo de cada execução paga, medido × estimado (25/11).

ADITIVA: tabela nova, nada existente muda.

Revision ID: a9c1e3f5b7d2
Revises: e8b2d4f6a1c3
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9c1e3f5b7d2"
down_revision: Union[str, None] = "e8b2d4f6a1c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "custos_execucao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "empresa_id",
            sa.Integer(),
            sa.ForeignKey("empresas.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("origem", sa.String(), nullable=False),
        sa.Column("executado_em", sa.DateTime(), nullable=False),
        sa.Column("usd_medido", sa.Float(), nullable=False),
        sa.Column("usd_estimado", sa.Float(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("partes_json", sa.Text(), nullable=False),
        sa.Column("cauda_executou", sa.Boolean(), nullable=True),
    )
    op.create_index(
        "ix_custos_execucao_empresa_data", "custos_execucao", ["empresa_id", "executado_em"]
    )


def downgrade() -> None:
    op.drop_index("ix_custos_execucao_empresa_data", table_name="custos_execucao")
    op.drop_table("custos_execucao")
