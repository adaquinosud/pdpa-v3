"""avaliador_correcoes — cada correção à mão de uma leitura (recusa e inclusão de trecho).

ADITIVA: tabela nova, vazia. Nenhuma coluna existente muda e o resultado gravado das
leituras (``avaliador_analises.itens_json``) não é tocado: a tela aplica as correções por
cima. Desfazer marca ``desfeita_em``; a linha não sai (é o gabarito de erros reais).

Revision ID: c0e1f2a3b4d5
Revises: b9d0e1f2a3c4
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c0e1f2a3b4d5"
down_revision: Union[str, None] = "b9d0e1f2a3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "avaliador_correcoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "analise_id",
            sa.Integer(),
            sa.ForeignKey("avaliador_analises.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("conteudo_hash", sa.String(64), nullable=False),
        sa.Column("marca_codigo", sa.String(16), nullable=False),
        sa.Column("marca_texto", sa.Text(), nullable=False),
        sa.Column("tipo", sa.String(16), nullable=False),
        sa.Column("trecho", sa.Text(), nullable=False),
        sa.Column("pagina", sa.Integer(), nullable=True),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("desfeita_em", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_avaliador_correcoes_analise", "avaliador_correcoes", ["analise_id"])


def downgrade() -> None:
    op.drop_index("ix_avaliador_correcoes_analise", table_name="avaliador_correcoes")
    op.drop_table("avaliador_correcoes")
