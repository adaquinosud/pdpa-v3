"""Onda 1 — base de contatos por-empresa (empresa_contatos, contato_atributos,
pesquisa_convites). ADITIVA: três tabelas novas, nenhuma existente é tocada.

- empresa_contatos: vínculo (empresa ↔ Pessoa global) da base de contatos, status
  ativo|inativo, unidade opcional (local_id). UNIQUE (empresa_id, pessoa_id).
- contato_atributos: atributo livre consultável por (empresa, pessoa) — valor_atual +
  valor_anterior + data_mudanca inline. UNIQUE (empresa_id, pessoa_id, chave).
- pesquisa_convites: token opaco por-pessoa de cada pesquisa (universo de convidados).
  UNIQUE (pesquisa_id, pessoa_id) e token UNIQUE.

Revision ID: c1d2e3f4a5b6
Revises: b2d3f4a5c6e7
Create Date: 2026-07-19 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b2d3f4a5c6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "empresa_contatos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "empresa_id",
            sa.Integer(),
            sa.ForeignKey("empresas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pessoa_id",
            sa.Integer(),
            sa.ForeignKey("pessoa.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "local_id",
            sa.Integer(),
            sa.ForeignKey("locais.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="ativo"),
        sa.Column("criado_em", sa.DateTime(), nullable=True),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('ativo','inativo')", name="ck_empresa_contatos_status"),
        sa.UniqueConstraint("empresa_id", "pessoa_id", name="uq_empresa_contato"),
    )
    op.create_index("idx_empresa_contatos_empresa", "empresa_contatos", ["empresa_id"])
    op.create_index("idx_empresa_contatos_pessoa", "empresa_contatos", ["pessoa_id"])

    op.create_table(
        "contato_atributos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "empresa_id",
            sa.Integer(),
            sa.ForeignKey("empresas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pessoa_id",
            sa.Integer(),
            sa.ForeignKey("pessoa.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chave", sa.String(), nullable=False),
        sa.Column("valor_atual", sa.String(), nullable=True),
        sa.Column("valor_anterior", sa.String(), nullable=True),
        sa.Column("data_mudanca", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("empresa_id", "pessoa_id", "chave", name="uq_contato_atributo"),
    )
    op.create_index("idx_contato_atributos_seg", "contato_atributos", ["empresa_id", "chave"])
    op.create_index("idx_contato_atributos_pessoa", "contato_atributos", ["pessoa_id"])

    op.create_table(
        "pesquisa_convites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "empresa_id",
            sa.Integer(),
            sa.ForeignKey("empresas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pesquisa_id",
            sa.Integer(),
            sa.ForeignKey("pesquisas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pessoa_id",
            sa.Integer(),
            sa.ForeignKey("pessoa.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("respondido_em", sa.DateTime(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("pesquisa_id", "pessoa_id", name="uq_pesquisa_convite"),
        sa.UniqueConstraint("token", name="uq_pesquisa_convite_token"),
    )
    op.create_index("idx_pesquisa_convites_empresa", "pesquisa_convites", ["empresa_id"])
    op.create_index("idx_pesquisa_convites_token", "pesquisa_convites", ["token"])


def downgrade() -> None:
    op.drop_index("idx_pesquisa_convites_token", table_name="pesquisa_convites")
    op.drop_index("idx_pesquisa_convites_empresa", table_name="pesquisa_convites")
    op.drop_table("pesquisa_convites")
    op.drop_index("idx_contato_atributos_pessoa", table_name="contato_atributos")
    op.drop_index("idx_contato_atributos_seg", table_name="contato_atributos")
    op.drop_table("contato_atributos")
    op.drop_index("idx_empresa_contatos_pessoa", table_name="empresa_contatos")
    op.drop_index("idx_empresa_contatos_empresa", table_name="empresa_contatos")
    op.drop_table("empresa_contatos")
