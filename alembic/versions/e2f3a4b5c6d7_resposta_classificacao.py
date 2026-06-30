"""Fase 2 · Passo 5a — colunas de classificação na Resposta (base do confronto)

Frente ADITIVA: classifica o comentário do colaborador (Resposta de pesquisas
proposito='confronto') no MESMO vocabulário dos verbatins (subpilar+valência),
mas MANTIDO no espaço da Resposta — NUNCA vira Verbatim, NUNCA toca o ratio do
cliente (fronteira por ausência de ponte). Respostas existentes ficam NULL até o
passo de classificação rodar. Ver src/pesquisa/confronto.py.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-06-30 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("resposta", sa.Column("subpilar_classificado", sa.String(), nullable=True))
    op.add_column("resposta", sa.Column("valencia_classificada", sa.String(), nullable=True))
    op.add_column("resposta", sa.Column("confianca_classificacao", sa.Float(), nullable=True))
    op.add_column("resposta", sa.Column("classificado_em", sa.DateTime(), nullable=True))
    op.add_column("resposta", sa.Column("prompt_versao", sa.String(), nullable=True))
    # CHECK só fora do SQLite (ALTER ADD CONSTRAINT não é suportado lá; o schema de
    # teste vem do create_all dos models, que já carrega o CHECK). Postgres ganha.
    if op.get_bind().dialect.name != "sqlite":
        op.create_check_constraint(
            "ck_resposta_valencia",
            "resposta",
            "valencia_classificada IS NULL OR valencia_classificada IN "
            "('promotor','conversivel','detrator','inativo')",
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("ck_resposta_valencia", "resposta", type_="check")
    op.drop_column("resposta", "prompt_versao")
    op.drop_column("resposta", "classificado_em")
    op.drop_column("resposta", "confianca_classificacao")
    op.drop_column("resposta", "valencia_classificada")
    op.drop_column("resposta", "subpilar_classificado")
