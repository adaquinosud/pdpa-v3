"""frases_posicao: a frase do cartão da aba Posições, uma linha por chamada ao modelo (08/11).

ADITIVA: tabela nova, nada existente muda. Só acrescenta (aceita ou rejeitada, toda chamada
vira linha) porque o custo mora aqui: ``custo_usd`` NOT NULL, gravado mesmo na rejeição.

Revision ID: e8b2d4f6a1c3
Revises: d7a3c5e9f1b2
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e8b2d4f6a1c3"
down_revision: Union[str, None] = "d7a3c5e9f1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "frases_posicao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "empresa_id",
            sa.Integer(),
            sa.ForeignKey("empresas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agrupamento_id",
            sa.Integer(),
            sa.ForeignKey("agrupamentos.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "local_id", sa.Integer(), sa.ForeignKey("locais.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("subpilar", sa.String(), nullable=False),
        sa.Column("dados_hash", sa.String(), nullable=False),
        sa.Column("frase", sa.Text(), nullable=True),
        sa.Column("motivo_rejeicao", sa.String(), nullable=True),
        sa.Column("modelo", sa.String(), nullable=False),
        sa.Column("prompt_versao", sa.String(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("custo_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("gerado_em", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_frases_posicao_escopo",
        "frases_posicao",
        ["empresa_id", "agrupamento_id", "local_id", "subpilar"],
    )


def downgrade() -> None:
    op.drop_index("ix_frases_posicao_escopo", table_name="frases_posicao")
    op.drop_table("frases_posicao")
