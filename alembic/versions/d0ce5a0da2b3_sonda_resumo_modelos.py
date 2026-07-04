"""sonda_ia_leituras.resumo_modelos_json — resumo por modelo (ADITIVA)

Adiciona ``resumo_modelos_json`` (Text, nullable) à leitura da sonda: 1–2 frases
destiladas do que CADA IA diz da empresa (vendor → frase). 100% aditivo; nasce
NULL. Ver src/models/sonda_ia.py e src/sonda_ia/classificador.py.

Revision ID: d0ce5a0da2b3
Revises: c0ffee5a0da1
Create Date: 2026-07-03 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d0ce5a0da2b3"
down_revision: Union[str, None] = "c0ffee5a0da1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sonda_ia_leituras", sa.Column("resumo_modelos_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("sonda_ia_leituras", "resumo_modelos_json")
