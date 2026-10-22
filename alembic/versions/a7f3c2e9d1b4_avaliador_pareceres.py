"""avaliador_pareceres — o que a pessoa escreve no parecer de uma leitura.

ADITIVA: tabela nova, vazia, uma linha por leitura (a frase da ordem, os doze achados e a nota
do bloco C). O que a peça diz e o que não diz não é guardado aqui: sai da leitura com as
correções na hora de gerar o Word.

Revision ID: a7f3c2e9d1b4
Revises: c0e1f2a3b4d5
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7f3c2e9d1b4"
down_revision: Union[str, None] = "c0e1f2a3b4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "avaliador_pareceres",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "analise_id",
            sa.Integer(),
            sa.ForeignKey("avaliador_analises.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("ordem", sa.Text(), nullable=False, server_default=""),
        sa.Column("achados_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("nota_c", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("avaliador_pareceres")
