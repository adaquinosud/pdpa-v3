"""pos-coleta watchdog: estado do pós-coleta na empresa (auto-retomada + banner).

Revision ID: a1b2c3d4e5f6
Revises: d0ce5a0da2b3
Create Date: 2026-07-04

Adiciona 4 colunas em ``empresas`` p/ o watchdog do pós-coleta:
- pos_coleta_status (rodando|completo|interrompido)
- pos_coleta_iniciado_em / pos_coleta_concluido_em
- pos_coleta_pendencias_json (último snapshot de pendências)
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "d0ce5a0da2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("empresas", sa.Column("pos_coleta_status", sa.String(), nullable=True))
    op.add_column("empresas", sa.Column("pos_coleta_iniciado_em", sa.DateTime(), nullable=True))
    op.add_column("empresas", sa.Column("pos_coleta_concluido_em", sa.DateTime(), nullable=True))
    op.add_column("empresas", sa.Column("pos_coleta_pendencias_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("empresas", "pos_coleta_pendencias_json")
    op.drop_column("empresas", "pos_coleta_concluido_em")
    op.drop_column("empresas", "pos_coleta_iniciado_em")
    op.drop_column("empresas", "pos_coleta_status")
