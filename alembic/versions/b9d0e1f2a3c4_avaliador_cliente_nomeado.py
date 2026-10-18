"""avaliador_analises.cliente_nomeado — a peça foi feita para um cliente com nome?

ADITIVA: coluna nova, NULL nas leituras que já existem (o campo não era perguntado; a
tela declara "não informado"). Quem envia responde no formulário; o balizador de marcas
usa a resposta só para AGRUPAR na tela as sete marcas que só se esperam em peça para
cliente com nome (decisão de 18/10). Nada mais muda.

Revision ID: b9d0e1f2a3c4
Revises: a8c9d0e1f2b3
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b9d0e1f2a3c4"
down_revision: Union[str, None] = "a8c9d0e1f2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "avaliador_analises",
        sa.Column("cliente_nomeado", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("avaliador_analises", "cliente_nomeado")
