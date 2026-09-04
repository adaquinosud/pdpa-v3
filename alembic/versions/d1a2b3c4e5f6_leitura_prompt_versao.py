"""sonda_ia_leituras.prompt_versao — versão do prompt que gerou a leitura

§6.22 fatia 3. NULLABLE de propósito: **NULL = pré-versionamento**, as leituras
que já existem. Sem backfill — NULL já é a resposta certa para o histórico.

⚠️ Sem esta coluna, trocar o prompt NÃO invalida nada: `sintetizar_leitura` pula
quando já existe leitura da execução (`classificador.py:176-177`), então renomear o
arquivo para _v2 deixaria toda leitura antiga intacta para sempre. É o oposto do
`PROMPT_SINTESE_VER` do Parecer, que entra no dados_hash e invalida.

🔒 A re-síntese NÃO é automática: existe o comando `flask sonda-resintetizar`, que
por padrão só REPORTA quantas leituras seriam afetadas e o custo. Quem decide
quando rodar é o Alexandre (§13 — run pago não dispara sozinho).

Revision ID: d1a2b3c4e5f6
Revises: c9e3f4a5b6d7
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1a2b3c4e5f6"
down_revision: Union[str, None] = "c9e3f4a5b6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sonda_ia_leituras") as b:
        b.add_column(sa.Column("prompt_versao", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sonda_ia_leituras") as b:
        b.drop_column("prompt_versao")
