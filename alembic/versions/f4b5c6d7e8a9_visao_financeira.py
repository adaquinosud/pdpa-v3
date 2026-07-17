"""Visão Financeira C-Level — input corrente + snapshots imutáveis (ADITIVA)

Duas tabelas novas da tela interna (Nível A):
- ``visao_financeira_input``: os 5 números do operador, 1 por empresa (UNIQUE),
  reexibido ao reabrir. Editável (estado corrente).
- ``visao_financeira_snapshot``: foto imutável (``foto_json`` materializa VALORES —
  ratios de termo + cenários + inputs + timestamp). Vários por empresa.

100% aditiva: nenhuma tabela existente é tocada. FK a nível de banco só fora do
SQLite (o schema de teste vem do create_all dos models, que já carrega a FK inline;
em Postgres a FK CASCADE é criada de verdade). Mesmo guard das migrations recentes.

Revision ID: f4b5c6d7e8a9
Revises: b4c2d3e5f6a7
Create Date: 2026-07-17 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4b5c6d7e8a9"
down_revision: Union[str, None] = "b4c2d3e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    eh_sqlite = op.get_bind().dialect.name == "sqlite"

    op.create_table(
        "visao_financeira_input",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("receita_recorrente_base", sa.Float(), nullable=False),
        sa.Column("churn_atual", sa.Float(), nullable=False),
        sa.Column("taxa_expansao", sa.Float(), nullable=False),
        sa.Column("cac", sa.Float(), nullable=False),
        sa.Column("volume_aquisicao", sa.Float(), nullable=False),
        sa.Column("atualizado_por", sa.String(), nullable=True),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("empresa_id", name="uq_visao_fin_input_empresa"),
    )
    op.create_table(
        "visao_financeira_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("gerado_em", sa.DateTime(), nullable=True),
        sa.Column("gerado_por", sa.String(), nullable=True),
        sa.Column("foto_json", sa.Text(), nullable=False),
    )
    op.create_index("idx_visao_fin_snapshot_empresa", "visao_financeira_snapshot", ["empresa_id"])

    if not eh_sqlite:
        op.create_foreign_key(
            "fk_visao_fin_input_empresa",
            "visao_financeira_input",
            "empresas",
            ["empresa_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_foreign_key(
            "fk_visao_fin_snapshot_empresa",
            "visao_financeira_snapshot",
            "empresas",
            ["empresa_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    op.drop_index("idx_visao_fin_snapshot_empresa", table_name="visao_financeira_snapshot")
    op.drop_table("visao_financeira_snapshot")
    op.drop_table("visao_financeira_input")
