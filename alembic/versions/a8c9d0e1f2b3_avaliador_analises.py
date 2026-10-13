"""avaliador_analises — Avaliador de documentos (fatia 3)

ADITIVA: tabela nova, nenhuma tabela existente é tocada. Uma linha por peça lida
(arquivo ou texto colado). ``texto_json`` é apagado ao concluir ou após N dias sem uso
(retenção da análise aberta); resumo, itens, trechos citados e custo permanecem.

Revision ID: a8c9d0e1f2b3
Revises: e2b3c4d5f6a7
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a8c9d0e1f2b3"
down_revision: Union[str, None] = "e2b3c4d5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "avaliador_analises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "empresa_id",
            sa.Integer(),
            sa.ForeignKey("empresas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.Column("usado_em", sa.DateTime(), nullable=False),
        sa.Column("origem", sa.String(length=8), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("arquivo_nome", sa.String(), nullable=True),
        sa.Column("conteudo_hash", sa.String(length=64), nullable=False),
        sa.Column("formato", sa.String(length=8), nullable=False),
        sa.Column("n_paginas", sa.Integer(), nullable=False),
        sa.Column("paginas_sem_texto_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("texto_json", sa.Text(), nullable=True),
        sa.Column("texto_apagado_em", sa.DateTime(), nullable=True),
        sa.Column("texto_apagado_motivo", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pendente"),
        sa.Column("erro_motivo", sa.String(), nullable=True),
        sa.Column("resumo", sa.Text(), nullable=True),
        sa.Column("itens_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("modelo", sa.String(), nullable=False),
        sa.Column("regua_versao", sa.String(), nullable=False),
        sa.Column("prompt_versao", sa.String(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_cache_criacao", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_cache_leitura", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("custo_usd", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_avaliador_analises_empresa_criado",
        "avaliador_analises",
        ["empresa_id", "criado_em"],
    )


def downgrade() -> None:
    op.drop_index("ix_avaliador_analises_empresa_criado", table_name="avaliador_analises")
    op.drop_table("avaliador_analises")
