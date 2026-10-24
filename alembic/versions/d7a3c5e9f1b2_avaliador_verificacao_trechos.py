"""avaliador_pareceres: a verificação dos trechos que vão sozinhos para o parecer (24/10).

ADITIVA: três colunas com valor padrão. ``verificacao_json`` guarda a decisão do modelo por
trecho (passa ou exclui, e o tipo da exclusão: navegação, lista, dois-pontos sem o que
anuncia), chaveada pelo texto impresso do trecho; ``verificacao_custo_usd`` e
``verificacao_em`` entram no teto mensal pela data da verificação, como o rascunho. O
resultado gravado da leitura não muda. Guarda trecho de peça de cliente: apagar a leitura
limpa o JSON (o custo fica).

Revision ID: d7a3c5e9f1b2
Revises: c4e8a1f7b2d9
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d7a3c5e9f1b2"
down_revision: Union[str, None] = "c4e8a1f7b2d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "avaliador_pareceres",
        sa.Column("verificacao_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "avaliador_pareceres",
        sa.Column("verificacao_custo_usd", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column("avaliador_pareceres", sa.Column("verificacao_em", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("avaliador_pareceres", "verificacao_em")
    op.drop_column("avaliador_pareceres", "verificacao_custo_usd")
    op.drop_column("avaliador_pareceres", "verificacao_json")
