"""FonteReputacao append-history (Fatia 4a): dropa UNIQUE(fonte_id) + índice.

Passa de 1-linha-sobrescrita a N-linhas-por-fonte (1 por coleta) — a série semanal
do scorecard é o valor do modo barato + base do gatilho-delta (v2). Os leitores
passam a pegar a MAIS RECENTE (order_by coletado_em desc). Neutro em custo.

Downgrade: DEDUP (mantém a linha mais recente por fonte, em Python DB-agnóstico)
antes de recriar o UNIQUE — senão a recriação falharia com histórico acumulado.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op

revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("fonte_reputacao") as b:
        b.drop_constraint("uq_fonte_reputacao", type_="unique")
    op.create_index(
        "idx_fonte_reputacao_fonte_coletado", "fonte_reputacao", ["fonte_id", "coletado_em"]
    )


def downgrade() -> None:
    # Dedup antes de reapertar o UNIQUE: mantém a linha mais recente por fonte.
    bind = op.get_bind()
    fr = sa.table(
        "fonte_reputacao",
        sa.column("id", sa.Integer),
        sa.column("fonte_id", sa.Integer),
        sa.column("coletado_em", sa.DateTime),
    )
    rows = bind.execute(
        sa.select(fr.c.id, fr.c.fonte_id).order_by(fr.c.fonte_id, fr.c.coletado_em.desc())
    ).fetchall()
    vistos: set = set()
    for rid, fid in rows:
        if fid in vistos:
            bind.execute(sa.delete(fr).where(fr.c.id == rid))
        else:
            vistos.add(fid)
    op.drop_index("idx_fonte_reputacao_fonte_coletado", table_name="fonte_reputacao")
    with op.batch_alter_table("fonte_reputacao") as b:
        b.create_unique_constraint("uq_fonte_reputacao", ["fonte_id"])
