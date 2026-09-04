"""sonda_ia_leituras.encaminhamentos_categorias_json

§6.22 / card da Vitrine. ADITIVA e não-destrutiva: `encaminhamentos_json` fica
INTOCADO, com a lista plana. O template da aba faz `{% for d in
snap.encaminhamentos %}` e renderizaria dicionários se a forma daquele campo
mudasse — por isso coluna nova, não mudança de shape.

Guarda `{concorrentes: [], canais_reclamacao: [], fabricante: []}` (prompt v3).
NULL = leitura anterior ao v3 (não há backfill possível: a categoria só existe se
o LLM a produziu).

⚠️ Motivo: `n_concorrentes = len(encaminhamentos)` contava Procon,
consumidor.gov.br, Reclame Aqui e o SAC do FABRICANTE como concorrente — 33
destinos na exec 28, dos quais só parte é concorrência real. Mandar o cliente ao
SAC da própria marca não é perder o cliente para um rival.

Revision ID: e2b3c4d5f6a7
Revises: d1a2b3c4e5f6
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2b3c4d5f6a7"
down_revision: Union[str, None] = "d1a2b3c4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sonda_ia_leituras") as b:
        b.add_column(sa.Column("encaminhamentos_categorias_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sonda_ia_leituras") as b:
        b.drop_column("encaminhamentos_categorias_json")
