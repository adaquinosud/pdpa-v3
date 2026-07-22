"""id_cliente por empresa (§5.5) — PessoaIdentificador.empresa_id + índices parciais.

E-mail/handle = chave GLOBAL (empresa_id NULL, único no mundo); crm/id_cliente = chave
POR EMPRESA (empresa_id preenchido, único só dentro dela). Substitui a UNIQUE global
(tipo, fonte, external_id) por dois índices PARCIAIS — o global (WHERE empresa_id IS
NULL) e o por-empresa (WHERE empresa_id IS NOT NULL). Resolve a semântica de NULL sem
depender de PG15 (NULLS NOT DISTINCT), cross-dialect.

ADITIVA na coluna (nasce NULL). Sem backfill aqui — o dano era só do laboratório
(wipe). CRM legado real, se houver, recebe empresa_id por um passo separado.

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-07-20 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tabela_ident_base() -> sa.Table:
    """Table explícita do estado ATUAL de `pessoa_identificador` (antes desta migration),
    para o batch do SQLite recriar SEM refletir (a reflexão do CHECK quebra com "Constraint
    must have a name"). A UNIQUE antiga é OMITIDA de propósito → o recreate a descarta."""
    meta = sa.MetaData()
    return sa.Table(
        "pessoa_identificador",
        meta,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pessoa_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("fonte", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("atributos_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["pessoa_id"], ["pessoa.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "tipo IN ('publico','interno_consentido')",
            name="ck_pessoa_identificador_tipo",
        ),
        # sa.UniqueConstraint(...) global OMITIDA — é justamente o que dropamos aqui.
    )


def upgrade() -> None:
    # Prod é Postgres: coluna com FK + DROP CONSTRAINT direto. SQLite não faz ALTER de
    # constraint; então recriamos a tabela via batch (copy_from explícito, sem reflexão)
    # já sem a UNIQUE global antiga — senão ela sobreviveria e continuaria FUNDINDO o
    # mesmo id_cliente entre empresas, anulando o fix. (Os testes usam create_all, que
    # já nasce sem a UNIQUE; isto cobre o banco migrado à mão.)
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(
            "pessoa_identificador",
            copy_from=_tabela_ident_base(),
            recreate="always",
        ) as batch:
            batch.add_column(sa.Column("empresa_id", sa.Integer(), nullable=True))
    else:
        op.add_column(
            "pessoa_identificador",
            sa.Column(
                "empresa_id",
                sa.Integer(),
                sa.ForeignKey("empresas.id", ondelete="CASCADE"),
                nullable=True,
            ),
        )
        op.drop_constraint(
            "uq_pessoa_identificador_natural", "pessoa_identificador", type_="unique"
        )
    op.create_index(
        "uq_ident_global",
        "pessoa_identificador",
        ["tipo", "fonte", "external_id"],
        unique=True,
        postgresql_where=sa.text("empresa_id IS NULL"),
        sqlite_where=sa.text("empresa_id IS NULL"),
    )
    op.create_index(
        "uq_ident_empresa",
        "pessoa_identificador",
        ["tipo", "fonte", "external_id", "empresa_id"],
        unique=True,
        postgresql_where=sa.text("empresa_id IS NOT NULL"),
        sqlite_where=sa.text("empresa_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_ident_empresa", table_name="pessoa_identificador")
    op.drop_index("uq_ident_global", table_name="pessoa_identificador")
    if op.get_bind().dialect.name == "sqlite":
        # Recria a tabela SEM empresa_id e COM a UNIQUE global de volta (batch, copy_from
        # do estado pós-upgrade: base + empresa_id, sem unique).
        atual = _tabela_ident_base()
        atual.append_column(sa.Column("empresa_id", sa.Integer(), nullable=True))
        with op.batch_alter_table(
            "pessoa_identificador",
            copy_from=atual,
            recreate="always",
        ) as batch:
            batch.drop_column("empresa_id")
            batch.create_unique_constraint(
                "uq_pessoa_identificador_natural", ["tipo", "fonte", "external_id"]
            )
    else:
        op.create_unique_constraint(
            "uq_pessoa_identificador_natural",
            "pessoa_identificador",
            ["tipo", "fonte", "external_id"],
        )
        op.drop_column("pessoa_identificador", "empresa_id")
