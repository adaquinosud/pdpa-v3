"""Caso: novo desfecho 'nao_rastreado' no CHECK ck_casos_desfecho

Correção de método (maturação): separa o artefato de coleta do desfecho real.
- 'abandonado' = SÓ quando seguimos rebuscando o caso e o consumidor não voltou
  (thread parada 90d, ``ultima_coleta`` recente).
- 'nao_rastreado' = caso que SAIU do fetch (janela deslizante LATEST×cap) e
  congelou — parou de amadurecer por artefato NOSSO, nunca falso-abandono.

Só afrouxa a CHECK p/ aceitar o novo valor (o split vive no coletor). Aditivo:
nenhum dado é convertido. batch = SQLite (dev) + Postgres (prod).

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-08
"""

from alembic import op

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None

_OLD = (
    "desfecho IN ('resolvido','nao_resolvido','respondida_em_disputa',"
    "'abandonado','respondida_sem_avaliacao','nao_respondida')"
)
_NEW = (
    "desfecho IN ('resolvido','nao_resolvido','respondida_em_disputa',"
    "'abandonado','respondida_sem_avaliacao','nao_respondida','nao_rastreado')"
)


def upgrade() -> None:
    with op.batch_alter_table("casos") as b:
        b.drop_constraint("ck_casos_desfecho", type_="check")
        b.create_check_constraint("ck_casos_desfecho", _NEW)


def downgrade() -> None:
    # Reverter o valor antes de reapertar a CHECK (senão a recriação falha).
    op.execute("UPDATE casos SET desfecho=NULL WHERE desfecho='nao_rastreado'")
    with op.batch_alter_table("casos") as b:
        b.drop_constraint("ck_casos_desfecho", type_="check")
        b.create_check_constraint("ck_casos_desfecho", _OLD)
