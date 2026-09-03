"""sonda_ia_execucoes: valida + invalidada_motivo + invalidada_em

Aditiva. Uma execução pode estar `concluida` (rodou e devolveu) e mesmo assim não
valer como medição — foi o caso da BEXP, sondada pelo termo "Grupo BEXP", que o
§6.22.4 mediu como artefato (fintech, mineração, BMW/MINI).

⚠️ NÃO é um valor novo em `status`: `status` é o ciclo de vida da máquina; `valida`
é julgamento sobre o INSUMO. Marcar 'falhou' escreveria estado falso com consumidor
visível — a aba diria "as IAs não retornaram", quando retornaram.

`server_default='true'` → toda linha existente nasce válida, e a migração é neutra
em comportamento.

Revision ID: a7c1d2e3f4b5
Revises: 8b35926ac8e5
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7c1d2e3f4b5"
down_revision: Union[str, None] = "8b35926ac8e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sonda_ia_execucoes",
        sa.Column("valida", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column("sonda_ia_execucoes", sa.Column("invalidada_motivo", sa.Text(), nullable=True))
    op.add_column("sonda_ia_execucoes", sa.Column("invalidada_em", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("sonda_ia_execucoes", "invalidada_em")
    op.drop_column("sonda_ia_execucoes", "invalidada_motivo")
    op.drop_column("sonda_ia_execucoes", "valida")
