"""Verbatim.respondente_id — liga o verbatim de pesquisa ao seu Respondente (ADITIVA)

Adiciona `verbatins.respondente_id` (FK nullable, SET NULL) + índice. Fecha a
corrente verbatim → respondente → pesquisa, que estava partida no 1º elo: o
Verbatim de coleta-proposito só apontava pra fonte (compartilhada) e carregava o
respondente_id apenas como substring de `review_id_externo` (`resp:<rid>:<qid>`).
Com a FK, o verbatim anônimo (pessoa_id NULL) também deixa de ser órfão — os N
verbatins de um mesmo respondente ficam agrupáveis mesmo sem identidade (fundação
da ficha da pessoa e da comparação de ondas).

100% aditivo: nasce NULL em todo verbatim existente (reviews espontâneos RA/Google/
Excel não têm respondente — NULL é o correto). `pessoa_id`/`fonte_id`/`hash_dedup`/
`review_id_externo` intactos. Ver src/pesquisa/coleta.py e src/models/verbatim.py.

Revision ID: a3f1c2d4e5b6
Revises: c2b001d44919
Create Date: 2026-07-14 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f1c2d4e5b6"
down_revision: Union[str, None] = "c2b001d44919"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("verbatins", sa.Column("respondente_id", sa.Integer(), nullable=True))
    op.create_index("idx_verbatins_respondente", "verbatins", ["respondente_id"], unique=False)
    # FK a nível de banco só fora do SQLite: o SQLite não faz ALTER ADD CONSTRAINT
    # (e nem precisa aqui — o schema de teste vem do create_all dos models, que já
    # carregam a FK inline). Em Postgres (prod) a FK é criada de verdade.
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_verbatins_respondente",
            "verbatins",
            "respondente",
            ["respondente_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    op.drop_index("idx_verbatins_respondente", table_name="verbatins")
    op.drop_column("verbatins", "respondente_id")  # a FK inline cai junto com a coluna
