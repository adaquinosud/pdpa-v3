"""ORIGEM fatia 2 — tabelas origem_analise + origem_sintese

Régua de profundidade do confronto. ``origem_analise`` por (pesquisa, subpilar):
nível da ruptura na cadeia generativa + lado (gravidade/solidez) + justificativa.
``origem_sintese`` 1 por pesquisa. Aditivas, filhas de pesquisa (FK CASCADE).
Ver src/models/origem.py.

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-07-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "origem_analise",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pesquisa_id", sa.Integer(), nullable=False),
        sa.Column("subpilar", sa.String(), nullable=False),
        sa.Column("nivel", sa.String(), nullable=False),
        sa.Column("lado", sa.String(), nullable=False),
        sa.Column("justificativa", sa.Text(), nullable=True),
        sa.Column("gerado_em", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["pesquisa_id"], ["pesquisas.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("pesquisa_id", "subpilar", name="uq_origem_analise"),
        sa.CheckConstraint(
            "nivel IN ('resultado','caminho','proposito','significado','essencia')",
            name="ck_origem_nivel",
        ),
        sa.CheckConstraint("lado IN ('gravidade','solidez')", name="ck_origem_lado"),
    )
    op.create_index("idx_origem_analise_pesquisa", "origem_analise", ["pesquisa_id"], unique=False)
    op.create_table(
        "origem_sintese",
        sa.Column("pesquisa_id", sa.Integer(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=True),
        sa.Column("gerado_em", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("pesquisa_id"),
        sa.ForeignKeyConstraint(["pesquisa_id"], ["pesquisas.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("origem_sintese")
    op.drop_index("idx_origem_analise_pesquisa", table_name="origem_analise")
    op.drop_table("origem_analise")
