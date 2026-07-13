"""pessoa_merges auditoria

Registra cada fusão de Pessoa (reconciliação multi-chave e-mail↔código de CRM).
Migration escrita à mão: o --autogenerate detectou drift espúrio do dev-SQLite
(TEXT→String, REAL→Float em dezenas de tabelas — os "SQLite-isms" já anotados no
PENDENCIAS), então mantemos APENAS a criação da tabela nova.

Revision ID: c2b001d44919
Revises: f2a3b4c5d6e7
Create Date: 2026-07-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2b001d44919"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pessoa_merges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pessoa_alvo_id", sa.Integer(), nullable=False),
        sa.Column("pessoa_absorvida_id", sa.Integer(), nullable=False),
        sa.Column("gatilho", sa.String(), nullable=True),
        sa.Column("chaves_json", sa.Text(), nullable=True),
        sa.Column("verbatins_reassignados", sa.Integer(), nullable=False),
        sa.Column("respondentes_reassignados", sa.Integer(), nullable=False),
        sa.Column("ids_json", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_pessoa_merges_alvo", "pessoa_merges", ["pessoa_alvo_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_pessoa_merges_alvo", table_name="pessoa_merges")
    op.drop_table("pessoa_merges")
