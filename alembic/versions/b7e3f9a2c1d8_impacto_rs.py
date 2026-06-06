"""impacto_rs: ltv inputs no local + taxas na empresa

Liga o Impacto em R$ (CP-impacto-rs) sem reescrita. Adiciona:
  - locais.ticket_medio, locais.frequencia, locais.ltv_origem  (inputs do LTV
    da loja; LTV = ticket × frequencia é DERIVADO no app, nunca guardado)
  - empresas.taxa_alto/taxa_medio/taxa_baixo  (taxa de sucesso por prioridade,
    editável por empresa; server_default pré-popula as existentes com os valores
    sugeridos 0.50/0.35/0.20)

Aditivo e seguro pra prod (Postgres): só ADD COLUMN. As taxas entram NOT NULL
com server_default (backfill automático das linhas existentes). As 3 colunas do
local são nullable → loja sem LTV mantém R$ "—" honesto.

Revision ID: b7e3f9a2c1d8
Revises: 8295ca9dc780
Create Date: 2026-06-06 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e3f9a2c1d8"
down_revision: Union[str, None] = "8295ca9dc780"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Inputs do LTV por loja (derivado = ticket × frequencia; nunca guardado).
    op.add_column("locais", sa.Column("ticket_medio", sa.Float(), nullable=True))
    op.add_column("locais", sa.Column("frequencia", sa.Float(), nullable=True))
    op.add_column("locais", sa.Column("ltv_origem", sa.String(), nullable=True))
    # Taxas de sucesso por prioridade, por empresa. NOT NULL + server_default →
    # as empresas já existentes herdam os valores sugeridos sem backfill manual.
    op.add_column(
        "empresas",
        sa.Column("taxa_alto", sa.Float(), server_default="0.50", nullable=False),
    )
    op.add_column(
        "empresas",
        sa.Column("taxa_medio", sa.Float(), server_default="0.35", nullable=False),
    )
    op.add_column(
        "empresas",
        sa.Column("taxa_baixo", sa.Float(), server_default="0.20", nullable=False),
    )


def downgrade() -> None:
    # batch_alter_table: DROP COLUMN portável (SQLite recria a tabela; Postgres
    # dropa direto).
    with op.batch_alter_table("empresas") as batch:
        batch.drop_column("taxa_baixo")
        batch.drop_column("taxa_medio")
        batch.drop_column("taxa_alto")
    with op.batch_alter_table("locais") as batch:
        batch.drop_column("ltv_origem")
        batch.drop_column("frequencia")
        batch.drop_column("ticket_medio")
