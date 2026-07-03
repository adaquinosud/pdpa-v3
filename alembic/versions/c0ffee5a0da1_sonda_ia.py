"""Reputação em IA — tabelas sonda_ia_* (ADITIVA)

Cria as 4 tabelas da frente IA: execução mensal, respostas raw por modelo/pergunta/
repetição, classificação PDPA da avaliação, e a leitura-síntese. FRONTEIRA: zero
FK para verbatins — a voz da IA é espelho, não entra na base do cliente. 100%
aditivo. Ver src/models/sonda_ia.py.

Revision ID: c0ffee5a0da1
Revises: d4e5f6a7b8c9
Create Date: 2026-07-03 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c0ffee5a0da1"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sonda_ia_execucoes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("competencia", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("modelos_json", sa.Text(), nullable=True),
        sa.Column("repeticoes", sa.Integer(), nullable=True),
        sa.Column("custo_usd", sa.Float(), nullable=True),
        sa.Column("iniciado_em", sa.DateTime(), nullable=True),
        sa.Column("concluido_em", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("empresa_id", "competencia", name="uq_sonda_execucao_mes"),
        sa.CheckConstraint(
            "status IN ('pendente','rodando','concluida','falhou')",
            name="ck_sonda_execucao_status",
        ),
    )
    op.create_index("idx_sonda_execucao_empresa", "sonda_ia_execucoes", ["empresa_id"])

    op.create_table(
        "sonda_ia_respostas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("execucao_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("vendor", sa.String(), nullable=False),
        sa.Column("modelo", sa.String(), nullable=False),
        sa.Column("pergunta_tipo", sa.String(), nullable=False),
        sa.Column("repeticao", sa.Integer(), nullable=False),
        sa.Column("resposta_texto", sa.Text(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["execucao_id"], ["sonda_ia_execucoes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "pergunta_tipo IN ('identidade','avaliacao','encaminhamento')",
            name="ck_sonda_resposta_pergunta",
        ),
    )
    op.create_index("idx_sonda_resposta_execucao", "sonda_ia_respostas", ["execucao_id"])
    op.create_index("idx_sonda_resposta_empresa", "sonda_ia_respostas", ["empresa_id"])
    op.create_index("idx_sonda_resposta_pergunta", "sonda_ia_respostas", ["pergunta_tipo"])

    op.create_table(
        "sonda_ia_avaliacoes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resposta_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("subpilar", sa.String(), nullable=True),
        sa.Column("tipo", sa.String(), nullable=True),
        sa.Column("tema_label", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["resposta_id"], ["sonda_ia_respostas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "subpilar IN ('P1','P2','P3','D1','D2','D3','Pa1','Pa2','Pa3',"
            "'A1','A2','A3','sem_lastro')",
            name="ck_sonda_avaliacao_subpilar",
        ),
        sa.CheckConstraint(
            "tipo IN ('promotor','conversivel','detrator','inativo')",
            name="ck_sonda_avaliacao_tipo",
        ),
    )
    op.create_index("idx_sonda_avaliacao_empresa", "sonda_ia_avaliacoes", ["empresa_id"])
    op.create_index("idx_sonda_avaliacao_resposta", "sonda_ia_avaliacoes", ["resposta_id"])

    op.create_table(
        "sonda_ia_leituras",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("execucao_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("competencia", sa.String(), nullable=False),
        sa.Column("identidade_ecoada", sa.Text(), nullable=True),
        sa.Column("identidade_vs_essencia", sa.Text(), nullable=True),
        sa.Column("encaminhamentos_json", sa.Text(), nullable=True),
        sa.Column("defasagem_json", sa.Text(), nullable=True),
        sa.Column("gerado_em", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["execucao_id"], ["sonda_ia_execucoes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("execucao_id", name="uq_sonda_leitura_execucao"),
    )
    op.create_index("idx_sonda_leitura_empresa", "sonda_ia_leituras", ["empresa_id"])


def downgrade() -> None:
    op.drop_index("idx_sonda_leitura_empresa", table_name="sonda_ia_leituras")
    op.drop_table("sonda_ia_leituras")
    op.drop_index("idx_sonda_avaliacao_resposta", table_name="sonda_ia_avaliacoes")
    op.drop_index("idx_sonda_avaliacao_empresa", table_name="sonda_ia_avaliacoes")
    op.drop_table("sonda_ia_avaliacoes")
    op.drop_index("idx_sonda_resposta_pergunta", table_name="sonda_ia_respostas")
    op.drop_index("idx_sonda_resposta_empresa", table_name="sonda_ia_respostas")
    op.drop_index("idx_sonda_resposta_execucao", table_name="sonda_ia_respostas")
    op.drop_table("sonda_ia_respostas")
    op.drop_index("idx_sonda_execucao_empresa", table_name="sonda_ia_execucoes")
    op.drop_table("sonda_ia_execucoes")
