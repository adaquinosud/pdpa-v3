"""Empresa.pos_coleta_limiar — limiar da CAUDA por empresa (corte #4, ADITIVA)

Adiciona `empresas.pos_coleta_limiar` (Integer, nullable). É o mínimo de material
pendente (verbatim com texto sem embedding) p/ rodar a CAUDA cara do pós-coleta.
NULL = usa o default do código (LIMIAR_NOVOS_DEFAULT, agora 10). A cabeça barata
(classificação de verbatim + desfecho RA) roda sempre, independente disto.

100% aditiva: só uma coluna nullable; nenhum backfill (NULL = default).

Revision ID: b2d3f4a5c6e7
Revises: a1c2e3d4f5b6
Create Date: 2026-07-18 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2d3f4a5c6e7"
down_revision: Union[str, None] = "a1c2e3d4f5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("empresas", sa.Column("pos_coleta_limiar", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("empresas", "pos_coleta_limiar")
