"""avaliador_pareceres.empresa_da_peca: o nome que sai no título do Word (22/10).

ADITIVA: uma coluna com valor padrão vazio. O título usava o nome da empresa em que a leitura
foi feita no app, que não é a empresa da peça quando se lê um prospect: o Word da #32
(E2Carbon) saiu com o nome de outra empresa da conta. Agora a pessoa escreve o nome, e o
Word não sai com ele em branco.

Revision ID: c4e8a1f7b2d9
Revises: b9d4e6f1a2c3
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4e8a1f7b2d9"
down_revision: Union[str, None] = "b9d4e6f1a2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "avaliador_pareceres",
        sa.Column("empresa_da_peca", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("avaliador_pareceres", "empresa_da_peca")
