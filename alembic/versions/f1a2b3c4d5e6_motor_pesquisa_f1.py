"""Motor de Pesquisa — Fase 1: tabelas pesquisas + pesquisa_perguntas

Schema ADITIVO e isolado (CP-Pesquisa-F1.1): cria só as 2 entidades da Fase 1
(geração assistida). Nenhuma tabela existente é tocada; nenhum código do
pipeline lê estas tabelas. Postgres-safe. Entidades de coleta (Respondente,
Resposta, RespostaVerbatim, Convite) ficam para a Fase 2.

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-06-25 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pesquisas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("natureza", sa.String(), nullable=False),
        sa.Column("titulo", sa.String(), nullable=False),
        sa.Column("objetivo", sa.Text(), nullable=True),
        sa.Column("entidade_tipo", sa.String(), nullable=True),
        sa.Column("entidade_id", sa.Integer(), nullable=True),
        sa.Column("escopo_local_modo", sa.String(), nullable=False),
        sa.Column("canal", sa.String(), nullable=True),
        sa.Column("anonima", sa.Boolean(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("criada_por", sa.Integer(), nullable=True),
        sa.Column("criada_em", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["criada_por"], ["usuarios.id"], ondelete="SET NULL"),
        sa.CheckConstraint("natureza IN ('externa','interna')", name="ck_pesquisas_natureza"),
        sa.CheckConstraint(
            "escopo_local_modo IN ('local','geral')",
            name="ck_pesquisas_escopo_local_modo",
        ),
        sa.CheckConstraint(
            "canal IS NULL OR canal IN ('web','whatsapp')", name="ck_pesquisas_canal"
        ),
        sa.CheckConstraint("status IN ('rascunho','pronta')", name="ck_pesquisas_status"),
    )
    op.create_index("idx_pesquisas_empresa", "pesquisas", ["empresa_id"], unique=False)

    op.create_table(
        "pesquisa_perguntas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pesquisa_id", sa.Integer(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("enunciado", sa.Text(), nullable=False),
        sa.Column("porque", sa.Text(), nullable=True),
        sa.Column("formato", sa.String(), nullable=False),
        sa.Column("subpilar_alvo", sa.String(), nullable=True),
        sa.Column("opcoes_json", sa.Text(), nullable=True),
        sa.Column("regua_valencia_json", sa.Text(), nullable=True),
        sa.Column("camada_origem", sa.String(), nullable=True),
        sa.Column("gerada_por_ancora", sa.Boolean(), nullable=False),
        sa.Column("validacao_json", sa.Text(), nullable=True),
        sa.Column("validado_em", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["pesquisa_id"], ["pesquisas.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "formato IN ('aberta','fechada','mista')",
            name="ck_pesquisa_perguntas_formato",
        ),
    )
    op.create_index(
        "idx_pesquisa_perguntas_pesquisa",
        "pesquisa_perguntas",
        ["pesquisa_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_pesquisa_perguntas_pesquisa", table_name="pesquisa_perguntas")
    op.drop_table("pesquisa_perguntas")
    op.drop_index("idx_pesquisas_empresa", table_name="pesquisas")
    op.drop_table("pesquisas")
