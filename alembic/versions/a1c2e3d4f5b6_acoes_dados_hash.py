"""AcaoVenda.dados_hash — hash de conteúdo p/ o skip das ações (ADITIVA)

Adiciona `acoes_venda.dados_hash` (String, nullable). É o hash do conteúdo que gera a
ação (contexto do LLM + fingerprint do prompt + modelo). Nasce NULL em toda linha
existente → a 1ª coleta pós-deploy regenera (NULL != hash), depois o hash-skip evita
regenerar o alvo cujo conteúdo não mudou (fim do delete-all + regenera-tudo a cada
coleta). Identidade da ação continua em `hash_escopo` (empresa|label|tipo).

100% aditiva: só uma coluna nullable; nenhum backfill (NULL = "regenerar na próxima").

Revision ID: a1c2e3d4f5b6
Revises: f4b5c6d7e8a9
Create Date: 2026-07-18 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1c2e3d4f5b6"
down_revision: Union[str, None] = "f4b5c6d7e8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("acoes_venda", sa.Column("dados_hash", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("acoes_venda", "dados_hash")
