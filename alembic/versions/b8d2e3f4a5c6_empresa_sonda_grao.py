"""empresas.sonda_grao — grão de entidade que a sonda de IA pergunta

Aditiva e DORMENTE: nenhum consumidor lê esta coluna nesta fatia (§6.22, fatia 1).
Quem passa a ler é a fatia 2, que troca o termo do prompt pelo nome da entidade.

`server_default='empresa'` → as empresas existentes nascem no grão de hoje, e a
migração é NEUTRA em comportamento e em custo (§13): nada passa a sondar N vezes
por ter subido esta coluna.

⚠️ server_default STRING CRUA é o certo AQUI (literal), ao contrário do booleano da
a7c1d2e3f4b5, que exigia sa.text("true"): para String o SQLAlchemy cita e gera
DEFAULT 'empresa'; text("empresa") viraria identificador sem aspas. Precedente na
casa: Fonte.ra_modo (server_default="padrao").

Primeiro CHECK da tabela `empresas`.

⚠️ O CHECK vai por `op.batch_alter_table` (padrão da casa: b8c9d0e1f2a3, c3d4e5f6a7b8).
`op.create_check_constraint` solto levanta `NotImplementedError: No support for ALTER
of constraints in SQLite dialect` — medido nesta fatia. Em prod (Postgres) passaria,
mas quebraria todo `alembic upgrade head` em dev. É a §6.23: o DDL do MODELO (CHECK
inline no CREATE TABLE) funciona nos dois, o da MIGRATION não — duas fontes do mesmo
DDL, e só uma foi exercitada.

Revision ID: b8d2e3f4a5c6
Revises: a7c1d2e3f4b5
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8d2e3f4a5c6"
down_revision: Union[str, None] = "a7c1d2e3f4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "empresas",
        sa.Column("sonda_grao", sa.String(), nullable=False, server_default="empresa"),
    )
    with op.batch_alter_table("empresas") as b:
        b.create_check_constraint(
            "ck_empresas_sonda_grao", "sonda_grao IN ('empresa','agrupamento','loja')"
        )


def downgrade() -> None:
    with op.batch_alter_table("empresas") as b:
        b.drop_constraint("ck_empresas_sonda_grao", type_="check")
    op.drop_column("empresas", "sonda_grao")
