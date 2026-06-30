"""P2.E — tabela pesquisa_escopos (escopo multi-alvo da pesquisa)

Frente ADITIVA: N alvos por pesquisa, todos do MESMO tipo. O tipo mora em
``pesquisas.entidade_tipo`` (local|agrupamento); aqui só os ``entidade_id``. Sem
coluna de tipo aqui → impossível misturar loja+agrupamento (garantia estrutural).
Nada existente é tocado. Ver src/models/pesquisa.py (PesquisaEscopo).

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-06-30 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pesquisa_escopos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pesquisa_id", sa.Integer(), nullable=False),
        sa.Column("entidade_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["pesquisa_id"], ["pesquisas.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("pesquisa_id", "entidade_id", name="uq_pesquisa_escopo"),
    )
    op.create_index(
        "idx_pesquisa_escopos_pesquisa", "pesquisa_escopos", ["pesquisa_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("idx_pesquisa_escopos_pesquisa", table_name="pesquisa_escopos")
    op.drop_table("pesquisa_escopos")
