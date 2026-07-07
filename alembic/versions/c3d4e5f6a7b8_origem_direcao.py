"""ORIGEM: camada 'proposito' → 'direcao' (rename do valor + CHECK ck_origem_nivel)

Rename de método aprovado: a 3ª camada da cadeia generativa passa de Propósito
para Direção. Aqui só o VALOR persistido + a CHECK; os rótulos/prompt/UI mudam no
código. 1ª migration não-no-op da sequência — /healthz é o gate do deploy.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-07
"""

from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None

_OLD = "nivel IN ('resultado','caminho','proposito','significado','essencia')"
_NEW = "nivel IN ('resultado','caminho','direcao','significado','essencia')"


def upgrade() -> None:
    # afrouxa a CHECK → converte o dado → recria com 'direcao' (batch = SQLite + PG)
    with op.batch_alter_table("origem_analise") as b:
        b.drop_constraint("ck_origem_nivel", type_="check")
    op.execute("UPDATE origem_analise SET nivel='direcao' WHERE nivel='proposito'")
    with op.batch_alter_table("origem_analise") as b:
        b.create_check_constraint("ck_origem_nivel", _NEW)


def downgrade() -> None:
    with op.batch_alter_table("origem_analise") as b:
        b.drop_constraint("ck_origem_nivel", type_="check")
    op.execute("UPDATE origem_analise SET nivel='proposito' WHERE nivel='direcao'")
    with op.batch_alter_table("origem_analise") as b:
        b.create_check_constraint("ck_origem_nivel", _OLD)
