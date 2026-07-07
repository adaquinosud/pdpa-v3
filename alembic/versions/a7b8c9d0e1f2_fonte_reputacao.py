"""Módulo Vitrine · Bloco A: tabela fonte_reputacao (scorecard OFICIAL da fonte).

Reputação do universo completo (RA ``recordType='company'``): consumer_score
conhecido + taxas mapeadas defensivamente + raw_json p/ refino. 1 linha por fonte.

Revision ID: a7b8c9d0e1f2
Revises: c3d4e5f6a7b8
Create Date: 2026-07-07
"""

import sqlalchemy as sa
from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fonte_reputacao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "fonte_id",
            sa.Integer(),
            sa.ForeignKey("fontes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "empresa_id",
            sa.Integer(),
            sa.ForeignKey("empresas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provedor", sa.String(), nullable=False),
        sa.Column("coletado_em", sa.DateTime(), nullable=True),
        sa.Column("consumer_score", sa.Float(), nullable=True),
        sa.Column("response_rate", sa.Float(), nullable=True),
        sa.Column("resolution_rate", sa.Float(), nullable=True),
        sa.Column("recommendation_rate", sa.Float(), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.UniqueConstraint("fonte_id", name="uq_fonte_reputacao"),
    )


def downgrade() -> None:
    op.drop_table("fonte_reputacao")
