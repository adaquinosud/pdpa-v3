"""P2.A — drop da coluna órfã pesquisa_perguntas.camada_origem

Decisão (sessão de revisão conceitual): o Modelo ORIGEM NÃO é camada da
pergunta — é a régua de profundidade do gap, aplicada na análise do confronto
cliente×colaborador (Fase 4). A coluna `camada_origem` na pergunta nasceu
reservada (F1.1) e ficou órfã: a geração nunca a popula e nada a lê
(persistência/templates/queries). Drop aditivo-seguro. Ver docs/MOTOR_PESQUISA_PDPA.md.

Revision ID: a7d2f3b9c4e1
Revises: f1a2b3c4d5e6
Create Date: 2026-06-29 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7d2f3b9c4e1"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("pesquisa_perguntas", "camada_origem")


def downgrade() -> None:
    # espelha a coluna como nasceu na f1a2b3c4d5e6 (nullable, sem default).
    op.add_column(
        "pesquisa_perguntas",
        sa.Column("camada_origem", sa.String(), nullable=True),
    )
