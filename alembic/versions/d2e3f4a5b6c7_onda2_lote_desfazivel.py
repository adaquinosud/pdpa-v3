"""Onda 2 — lote de import desfazível. Cria importacao_lotes + adiciona a FK
nullable indexada import_lote_id em verbatins, respondente, empresa_contatos,
contato_atributos. ADITIVA: coluna nasce NULL (só imports novos são desfazíveis).

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-07-19 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABELAS = ("verbatins", "respondente", "empresa_contatos", "contato_atributos")
_IDX = {
    "verbatins": "idx_verbatins_lote",
    "respondente": "idx_respondente_lote",
    "empresa_contatos": "idx_empresa_contatos_lote",
    "contato_atributos": "idx_contato_atributos_lote",
}


def upgrade() -> None:
    op.create_table(
        "importacao_lotes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "empresa_id",
            sa.Integer(),
            sa.ForeignKey("empresas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("arquivo_nome", sa.String(), nullable=True),
        sa.Column(
            "autor_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="ativo"),
        sa.Column("contadores_json", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=True),
        sa.Column("desfeito_em", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "tipo IN ('contatos','respostas','verbatins')", name="ck_importacao_lotes_tipo"
        ),
        sa.CheckConstraint("status IN ('ativo','desfeito')", name="ck_importacao_lotes_status"),
    )
    op.create_index("idx_importacao_lotes_empresa", "importacao_lotes", ["empresa_id"])

    # batch_alter_table: no Postgres emite ALTER direto; no SQLite (testes) faz o
    # copy-and-move que a coluna+FK exige. A coluna é nullable → sem backfill.
    for tab in _TABELAS:
        with op.batch_alter_table(tab) as batch_op:
            batch_op.add_column(sa.Column("import_lote_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                f"fk_{tab}_import_lote",
                "importacao_lotes",
                ["import_lote_id"],
                ["id"],
                ondelete="SET NULL",
            )
        op.create_index(_IDX[tab], tab, ["import_lote_id"])


def downgrade() -> None:
    for tab in _TABELAS:
        op.drop_index(_IDX[tab], table_name=tab)
        with op.batch_alter_table(tab) as batch_op:
            batch_op.drop_column("import_lote_id")
    op.drop_index("idx_importacao_lotes_empresa", table_name="importacao_lotes")
    op.drop_table("importacao_lotes")
