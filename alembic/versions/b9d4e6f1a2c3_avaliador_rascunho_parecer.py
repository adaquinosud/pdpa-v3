"""avaliador_pareceres: o rascunho do modelo (fatia 3, 22/10).

ADITIVA: quatro colunas com valor padrão, nenhuma linha muda de sentido.
- rascunho_json: por campo (ordem ou subpilar) que o modelo rascunhou, o texto que ele
  escreveu, como a pessoa passou por ele ("pendente", "aceito" ou "editado") e a base (hash
  da tela que o modelo leu). Guardar qual foi qual é o que diz depois se o rascunho merece
  confiança.
- rascunho_custo_usd, rascunho_em, rascunho_versao: o gasto (entra no teto mensal da
  empresa), quando e com que pedido.

Revision ID: b9d4e6f1a2c3
Revises: a7f3c2e9d1b4
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b9d4e6f1a2c3"
down_revision: Union[str, None] = "a7f3c2e9d1b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "avaliador_pareceres",
        sa.Column("rascunho_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "avaliador_pareceres",
        sa.Column("rascunho_custo_usd", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column("avaliador_pareceres", sa.Column("rascunho_em", sa.DateTime(), nullable=True))
    op.add_column("avaliador_pareceres", sa.Column("rascunho_versao", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("avaliador_pareceres", "rascunho_versao")
    op.drop_column("avaliador_pareceres", "rascunho_em")
    op.drop_column("avaliador_pareceres", "rascunho_custo_usd")
    op.drop_column("avaliador_pareceres", "rascunho_json")
