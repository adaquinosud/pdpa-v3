"""Fase 2 · Passo 2a — Pesquisa.token_publico (slug público do formulário web)

Frente ADITIVA: adiciona `pesquisas.token_publico` (String, nullable, UNIQUE) —
âncora estável da URL pública /p/<token>, gerada ao publicar (status→'pronta').
Nada existente é tocado; nasce NULL nas pesquisas existentes. Ver
src/pesquisa/coleta.py / src/pesquisa/persistencia.py.

Revision ID: d1e2f3a4b5c6
Revises: c9d3e4f5a6b7
Create Date: 2026-06-30 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c9d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pesquisas", sa.Column("token_publico", sa.String(), nullable=True))
    op.create_index(
        "uq_pesquisas_token_publico",
        "pesquisas",
        ["token_publico"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_pesquisas_token_publico", table_name="pesquisas")
    op.drop_column("pesquisas", "token_publico")
