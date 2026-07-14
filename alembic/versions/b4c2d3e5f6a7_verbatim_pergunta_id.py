"""Verbatim.pergunta_id — liga o verbatim de pesquisa à pergunta que respondeu (ADITIVA)

Adiciona `verbatins.pergunta_id` (FK nullable, SET NULL) + índice. Fecha o último
elo que faltava pra tela de respostas ler o mundo coleta: o retorno agrega POR
PERGUNTA, e o Verbatim só carregava a pergunta como substring de review_id_externo
(`resp:<rid>:<qid>`) — e só no canal web. Torna o elo first-class (o dado já está no
escopo do write-path, src/pesquisa/coleta.py: `r["pergunta_id"]`), como fizemos com
respondente_id. Pega os dois canais (web + Excel).

100% aditivo: nasce NULL em todo verbatim existente (review espontâneo RA/Google/
Excel não responde pergunta — NULL correto). Mesmo padrão de pessoa_id/respondente_id
(guard SQLite/Postgres p/ a FK). Ver src/pesquisa/retorno.py (leitura ramifica por
proposito) e src/models/verbatim.py.

Revision ID: b4c2d3e5f6a7
Revises: a3f1c2d4e5b6
Create Date: 2026-07-14 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4c2d3e5f6a7"
down_revision: Union[str, None] = "a3f1c2d4e5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("verbatins", sa.Column("pergunta_id", sa.Integer(), nullable=True))
    op.create_index("idx_verbatins_pergunta", "verbatins", ["pergunta_id"], unique=False)
    # FK a nível de banco só fora do SQLite: o SQLite não faz ALTER ADD CONSTRAINT
    # (e nem precisa aqui — o schema de teste vem do create_all dos models, que já
    # carregam a FK inline). Em Postgres (prod) a FK é criada de verdade.
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_verbatins_pergunta",
            "verbatins",
            "pesquisa_perguntas",
            ["pergunta_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    op.drop_index("idx_verbatins_pergunta", table_name="verbatins")
    op.drop_column("verbatins", "pergunta_id")  # a FK inline cai junto com a coluna
