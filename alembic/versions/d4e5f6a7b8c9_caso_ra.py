"""Caso (ReclameAqui como sequência viva) + verbatins.caso_id (ADITIVA)

Cria `casos` (reclamação RA com ciclo de vida: fatos da origem + thread + saídas
do classificador de desfecho + bookkeeping de recoleta) e adiciona
`verbatins.caso_id` (FK nullable, SET NULL) + índice. 100% aditivo: nada
existente é tocado; `caso_id` nasce NULL em todo verbatim. Ver src/models/caso.py
e docs/CONTRATO_RA_ACTOR.md.

Revision ID: d4e5f6a7b8c9
Revises: c8d9e0f1a2b3
Create Date: 2026-07-03 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "casos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("fonte_id", sa.Integer(), nullable=False),
        sa.Column("local_id", sa.Integer(), nullable=True),
        sa.Column("pessoa_id", sa.Integer(), nullable=True),
        sa.Column("origem_id", sa.String(), nullable=False),
        sa.Column("origem_legacy_id", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("titulo", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("status_label", sa.String(), nullable=True),
        sa.Column("solved", sa.Boolean(), nullable=True),
        sa.Column("evaluated", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("categoria", sa.String(), nullable=True),
        sa.Column("problema_tipo", sa.String(), nullable=True),
        sa.Column("criado_em_origem", sa.DateTime(), nullable=True),
        sa.Column("thread_json", sa.Text(), nullable=True),
        sa.Column("interactions_count", sa.Integer(), nullable=True),
        sa.Column("hash_thread", sa.String(), nullable=True),
        sa.Column("autor_cidade", sa.String(), nullable=True),
        sa.Column("autor_estado", sa.String(), nullable=True),
        sa.Column("autor_origem_id", sa.String(), nullable=True),
        sa.Column("desfecho", sa.String(), nullable=True),
        sa.Column("causa_resolvida", sa.Boolean(), nullable=True),
        sa.Column("desfecho_confianca", sa.Float(), nullable=True),
        sa.Column("desfecho_justificativa", sa.Text(), nullable=True),
        sa.Column("desfecho_versao", sa.String(), nullable=True),
        sa.Column("primeira_coleta", sa.DateTime(), nullable=True),
        sa.Column("ultima_coleta", sa.DateTime(), nullable=True),
        sa.Column("thread_mudou_em", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fonte_id"], ["fontes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["local_id"], ["locais.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["pessoa_id"], ["pessoa.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("fonte_id", "origem_id", name="uq_casos_origem"),
        sa.CheckConstraint(
            "desfecho IN ('resolvido','nao_resolvido','respondida_em_disputa',"
            "'abandonado','respondida_sem_avaliacao','nao_respondida')",
            name="ck_casos_desfecho",
        ),
    )
    op.create_index("idx_casos_empresa", "casos", ["empresa_id"], unique=False)
    op.create_index("idx_casos_fonte", "casos", ["fonte_id"], unique=False)
    op.create_index("idx_casos_status", "casos", ["status"], unique=False)
    op.create_index("idx_casos_ultima_coleta", "casos", ["ultima_coleta"], unique=False)

    op.add_column("verbatins", sa.Column("caso_id", sa.Integer(), nullable=True))
    op.create_index("idx_verbatins_caso", "verbatins", ["caso_id"], unique=False)
    # FK a nível de banco só fora do SQLite (mesma razão da migration do pessoa_id:
    # SQLite não faz ALTER ADD CONSTRAINT; no teste a FK vem inline do create_all).
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_verbatins_caso",
            "verbatins",
            "casos",
            ["caso_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    op.drop_index("idx_verbatins_caso", table_name="verbatins")
    op.drop_column("verbatins", "caso_id")  # a FK inline cai junto com a coluna
    op.drop_index("idx_casos_ultima_coleta", table_name="casos")
    op.drop_index("idx_casos_status", table_name="casos")
    op.drop_index("idx_casos_fonte", table_name="casos")
    op.drop_index("idx_casos_empresa", table_name="casos")
    op.drop_table("casos")
