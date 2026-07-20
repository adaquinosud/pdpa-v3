"""PesquisaPergunta.tema_declarado — tema declarado pelo operador por pergunta (§6.7).

ADITIVA: uma coluna String nullable. NULL = pergunta sem tema (segue válida); nenhum
backfill. Toda resposta a uma pergunta com tema_declarado recebe o vínculo direto
(origem='manual' + bucket), sem embedding/clustering.

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-07-20 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pesquisa_perguntas", sa.Column("tema_declarado", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("pesquisa_perguntas", "tema_declarado")
