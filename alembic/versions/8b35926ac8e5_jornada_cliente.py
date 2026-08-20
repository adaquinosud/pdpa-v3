"""Frente Jornada — empresa_jornada_etapas + Verbatim.etapa/etapa_confianca/etapa_versao.

ADITIVA: cria a tabela filha da jornada por-empresa e adiciona 3 colunas nullable em
``verbatins``. Sem backfill (o backfill de etapa é operação separada, com botão admin,
custo declarado e aprovação própria — NÃO entra aqui). ADD COLUMN nullable é O(1) e não
reescreve as linhas de ``verbatins``. Nada lê ``etapa`` até a aba Jornada existir.

Revision ID: 8b35926ac8e5
Revises: 5fcdb07e79d7
Create Date: 2026-08-20 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8b35926ac8e5"
down_revision: Union[str, None] = "5fcdb07e79d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "empresa_jornada_etapas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("rotulo", sa.String(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("criada_em", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "empresa_id", "versao", "ordem", name="uq_jornada_empresa_versao_ordem"
        ),
    )
    op.create_index("idx_jornada_empresa", "empresa_jornada_etapas", ["empresa_id"])

    op.add_column("verbatins", sa.Column("etapa", sa.String(), nullable=True))
    op.add_column("verbatins", sa.Column("etapa_confianca", sa.Float(), nullable=True))
    op.add_column("verbatins", sa.Column("etapa_versao", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("verbatins", "etapa_versao")
    op.drop_column("verbatins", "etapa_confianca")
    op.drop_column("verbatins", "etapa")
    op.drop_index("idx_jornada_empresa", table_name="empresa_jornada_etapas")
    op.drop_table("empresa_jornada_etapas")
