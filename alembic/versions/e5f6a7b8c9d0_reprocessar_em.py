"""empresas.reprocessar_em: flag de reprocessamento da noturna (CP-reprocessar-sujos)

Coluna nullable setada pela reclassificação manual da UI. A noturna
(``coleta_noturna_todas.py``) varre empresas com ``reprocessar_em != NULL``, roda
reconciliar_vinculos + pós-coleta (recalcula temas/cache/anomalias; a
classificação manual é preservada) e limpa o flag. Aditiva, Postgres-safe.

Revision ID: e5f6a7b8c9d0
Revises: d4a1b2c3e5f6
Create Date: 2026-06-22 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4a1b2c3e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("empresas", sa.Column("reprocessar_em", sa.DateTime(), nullable=True))
    op.create_index("idx_empresas_reprocessar_em", "empresas", ["reprocessar_em"])


def downgrade() -> None:
    op.drop_index("idx_empresas_reprocessar_em", table_name="empresas")
    op.drop_column("empresas", "reprocessar_em")
