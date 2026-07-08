"""Coorte mensal (dois-modos): casos.coorte_ano_mes + índice + fonte_coorte_coleta.

Fatia 3. Aditivo/quase-neutro: grava a chave de coorte mas ninguém ainda LÊ (o
consumo é a Fatia 4); a tabela nasce VAZIA. Backfill DA CHAVE em Python
(op.get_bind() — DB-agnóstico, sem strftime/to_char) nos casos existentes, a partir
de criado_em_origem; loga quantos ficaram NULL (sem data → fora de janela mensal).
NÃO rebusca nada (custo zero) — o preenchimento dos buracos é a Fatia 4.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("casos", sa.Column("coorte_ano_mes", sa.Integer(), nullable=True))
    op.create_index("idx_casos_fonte_coorte", "casos", ["fonte_id", "coorte_ano_mes"])
    op.create_table(
        "fonte_coorte_coleta",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "fonte_id", sa.Integer(), sa.ForeignKey("fontes.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "empresa_id",
            sa.Integer(),
            sa.ForeignKey("empresas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("coorte_ano_mes", sa.Integer(), nullable=False),
        sa.Column("ultima_coleta_coorte", sa.DateTime(), nullable=True),
        sa.Column("fechada", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("n_casos", sa.Integer(), nullable=True),
        sa.UniqueConstraint("fonte_id", "coorte_ano_mes", name="uq_fonte_coorte"),
    )

    # ── Backfill DA CHAVE (Python, DB-agnóstico) ──────────────────────────────
    bind = op.get_bind()
    casos = sa.table(
        "casos",
        sa.column("id", sa.Integer),
        sa.column("criado_em_origem", sa.DateTime),
        sa.column("coorte_ano_mes", sa.Integer),
    )
    rows = bind.execute(sa.select(casos.c.id, casos.c.criado_em_origem)).fetchall()
    n_total = len(rows)
    n_null = 0
    for cid, dt in rows:
        if dt is None:
            n_null += 1
            continue
        cam = dt.year * 100 + dt.month
        bind.execute(sa.update(casos).where(casos.c.id == cid).values(coorte_ano_mes=cam))
    print(
        f"[migration coorte] backfill: {n_total} casos, {n_total - n_null} com coorte, "
        f"{n_null} NULL (sem criado_em_origem)"
    )


def downgrade() -> None:
    op.drop_table("fonte_coorte_coleta")
    op.drop_index("idx_casos_fonte_coorte", table_name="casos")
    op.drop_column("casos", "coorte_ano_mes")
