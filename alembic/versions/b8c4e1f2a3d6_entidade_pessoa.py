"""Entidade Pessoa — fundação do eixo individual (ADITIVA)

Cria `pessoa` + `pessoa_identificador` (1:N, pronto p/ merge futuro sem lógica de
resolução) e adiciona `verbatins.pessoa_id` (FK nullable, SET NULL) + índice.
100% aditivo: nada existente é tocado; `pessoa_id` nasce NULL em todo verbatim
existente; `autor`/`hash_dedup`/`review_id_externo` intactos. Nenhuma criação
retroativa de Pessoa. Ver src/models/pessoa.py.

Revision ID: b8c4e1f2a3d6
Revises: a7d2f3b9c4e1
Create Date: 2026-06-29 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8c4e1f2a3d6"
down_revision: Union[str, None] = "a7d2f3b9c4e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pessoa",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("nome_display", sa.String(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("tipo IN ('publico','interno_consentido')", name="ck_pessoa_tipo"),
    )

    op.create_table(
        "pessoa_identificador",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pessoa_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("fonte", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("atributos_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["pessoa_id"], ["pessoa.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "tipo IN ('publico','interno_consentido')",
            name="ck_pessoa_identificador_tipo",
        ),
        sa.UniqueConstraint("tipo", "fonte", "external_id", name="uq_pessoa_identificador_natural"),
    )
    op.create_index(
        "idx_pessoa_identificador_pessoa",
        "pessoa_identificador",
        ["pessoa_id"],
        unique=False,
    )

    op.add_column("verbatins", sa.Column("pessoa_id", sa.Integer(), nullable=True))
    op.create_index("idx_verbatins_pessoa", "verbatins", ["pessoa_id"], unique=False)
    # FK a nível de banco só fora do SQLite: o SQLite não faz ALTER ADD CONSTRAINT
    # (e nem precisa aqui — o schema de teste vem do create_all dos models, que já
    # carregam a FK inline). Em Postgres (prod) a FK é criada de verdade.
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_verbatins_pessoa",
            "verbatins",
            "pessoa",
            ["pessoa_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    op.drop_index("idx_verbatins_pessoa", table_name="verbatins")
    op.drop_column("verbatins", "pessoa_id")  # a FK inline cai junto com a coluna
    op.drop_index("idx_pessoa_identificador_pessoa", table_name="pessoa_identificador")
    op.drop_table("pessoa_identificador")
    op.drop_table("pessoa")
