"""classificacao_batches: rastreio de batches da Anthropic Message Batches API

Tabela nova (aditiva) que persiste o ``batch_id`` retornado pela Anthropic ANTES
do polling, para reatamento após morte do processo (a pós-coleta roda em daemon-
thread que morre no deploy) — evita resubmissão e custo dobrado. Ver
``src/temas/pos_coleta.py`` (_classificar_pendentes_batch) e o model
``src/models/classificacao_batch.py``.

Aditiva, Postgres-safe (só CREATE TABLE + índices).

Revision ID: d4a1b2c3e5f6
Revises: c3f8a1d29b04
Create Date: 2026-06-19 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4a1b2c3e5f6"
down_revision: Union[str, None] = "c3f8a1d29b04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "classificacao_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.String(), nullable=False),
        sa.Column("modelo", sa.String(), nullable=False),
        sa.Column("passe", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="submitted"),
        sa.Column("criado_em", sa.DateTime(), nullable=True),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_classif_batch_empresa", "classificacao_batches", ["empresa_id"])
    op.create_index("idx_classif_batch_status", "classificacao_batches", ["status"])
    op.create_index("idx_classif_batch_batch_id", "classificacao_batches", ["batch_id"])


def downgrade() -> None:
    op.drop_index("idx_classif_batch_batch_id", table_name="classificacao_batches")
    op.drop_index("idx_classif_batch_status", table_name="classificacao_batches")
    op.drop_index("idx_classif_batch_empresa", table_name="classificacao_batches")
    op.drop_table("classificacao_batches")
