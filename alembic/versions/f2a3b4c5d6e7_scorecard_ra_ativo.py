"""Separação de controles (Fatia 4.5a): empresas.scorecard_ra_ativo (default True).

Separa o controle do scorecard RA (barato, cron próprio) do coleta_noturna_ativa
(que volta a governar só o não-RA). Default TRUE — liga em quase todo mundo (é
centavos, alimenta a Vitrine mesmo em empresa com noturno desligado). Reversível.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "empresas",
        sa.Column(
            "scorecard_ra_ativo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("empresas", "scorecard_ra_ativo")
