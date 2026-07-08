"""RA dois-modos (Fatia 3.5): fontes.ra_coortes_ativas + backfill conservador.

Nova coluna = o controle demo↔cliente do custo de threads: nº de coortes mensais
que o refresh mantém ativas (custo ≈ coortes × volume-do-mês × US$0,025). Default 1
(conservador — toda empresa nasce em demonstração/custo-Loyall; sobe manual quando
vira pagante). Backfill: TODA fonte RA existente → 1 (não deriva de janela_meses).

ra_janela_meses e ra_max_casos ficam DORMANT (deprecados na UI; coluna preservada —
max_casos vira teto-de-segurança default ilimitado no coletor). Reversível.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fontes", sa.Column("ra_coortes_ativas", sa.Integer(), nullable=True))
    # Backfill conservador: toda fonte RA nasce/migra com 1 coorte ativa (demo).
    op.execute("UPDATE fontes SET ra_coortes_ativas = 1 WHERE conector_tipo = 'reclame_aqui'")


def downgrade() -> None:
    op.drop_column("fontes", "ra_coortes_ativas")
