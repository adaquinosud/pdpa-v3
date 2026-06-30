"""Fase 2 · Passo 1 — estrutura de coleta: Pesquisa.proposito + respondente + resposta

Frente ADITIVA: adiciona `pesquisas.proposito` (default 'coleta' → pesquisas
existentes viram coleta) e cria `respondente` + `resposta`. Nada existente é
tocado; o caminho de verbatim/coleta segue idêntico. Escopo do respondente
espelha o vocabulário da Pesquisa (entidade_tipo/entidade_id). Ver
src/models/respondente.py.

Revision ID: c9d3e4f5a6b7
Revises: b8c4e1f2a3d6
Create Date: 2026-06-29 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d3e4f5a6b7"
down_revision: Union[str, None] = "b8c4e1f2a3d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Pesquisa.proposito — server_default 'coleta' popula as linhas existentes
    # (NOT NULL satisfeito sem backfill manual).
    op.add_column(
        "pesquisas",
        sa.Column("proposito", sa.String(), nullable=False, server_default="coleta"),
    )

    op.create_table(
        "respondente",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pesquisa_id", sa.Integer(), nullable=False),
        sa.Column("pessoa_id", sa.Integer(), nullable=True),
        sa.Column("entidade_tipo", sa.String(), nullable=False),
        sa.Column("entidade_id", sa.Integer(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["pesquisa_id"], ["pesquisas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pessoa_id"], ["pessoa.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "entidade_tipo IN ('local','agrupamento','empresa')",
            name="ck_respondente_entidade_tipo",
        ),
    )
    op.create_index("idx_respondente_pesquisa", "respondente", ["pesquisa_id"], unique=False)
    op.create_index("idx_respondente_pessoa", "respondente", ["pessoa_id"], unique=False)

    op.create_table(
        "resposta",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("respondente_id", sa.Integer(), nullable=False),
        sa.Column("pergunta_id", sa.Integer(), nullable=False),
        sa.Column("valor_texto", sa.Text(), nullable=True),
        sa.Column("valor_nota", sa.Integer(), nullable=True),
        sa.Column("valor_opcao", sa.String(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["respondente_id"], ["respondente.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pergunta_id"], ["pesquisa_perguntas.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "respondente_id", "pergunta_id", name="uq_resposta_respondente_pergunta"
        ),
    )
    op.create_index("idx_resposta_respondente", "resposta", ["respondente_id"], unique=False)
    op.create_index("idx_resposta_pergunta", "resposta", ["pergunta_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_resposta_pergunta", table_name="resposta")
    op.drop_index("idx_resposta_respondente", table_name="resposta")
    op.drop_table("resposta")
    op.drop_index("idx_respondente_pessoa", table_name="respondente")
    op.drop_index("idx_respondente_pesquisa", table_name="respondente")
    op.drop_table("respondente")
    op.drop_column("pesquisas", "proposito")
