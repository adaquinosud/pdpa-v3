"""sonda: flag por entidade (locais/agrupamentos) + origem da resposta

§6.22 fatia 2 — duas colunas aditivas, ambas neutras:

- ``locais.sonda_ativa`` / ``agrupamentos.sonda_ativa``: elegibilidade da entidade
  na sondagem. Default TRUE = toda entidade existente entra; quem NÃO deve entrar
  (local que é canal de coleta, ex. as fontes de RA cadastradas como loja) é
  desmarcado no cadastro. ⚠️ A elegibilidade é a FLAG e só ela — não filtramos por
  status nem por contagem de verbatim: loja nova sem coleta entra (reconhecimento
  em IA independe de termos coletado, §6.22.10).
- ``sonda_ia_respostas.entidade``: o NOME perguntado. NULL = grão empresa (tudo que
  existe hoje). Sem backfill — NULL já é a resposta certa para o histórico.

⚠️ ``server_default=sa.text("true")`` porque booleano É expressão SQL. É o INVERSO
do literal de string da b8d2e3f4a5c6 (``server_default="empresa"``, que o SQLAlchemy
cita). A distinção custou um defeito na fatia da invalidação (§6.23).

⚠️ ``batch_alter_table`` em tudo: ``op.create_check_constraint``/``alter`` solto
levanta NotImplementedError no SQLite, medido na fatia 1.

Sem constraint nova em ``sonda_ia_respostas`` — a tabela não tem UNIQUE e continua
sem, que é o que deixa N entidades coexistirem na MESMA execução (§6.22.6).

Revision ID: c9e3f4a5b6d7
Revises: b8d2e3f4a5c6
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9e3f4a5b6d7"
down_revision: Union[str, None] = "b8d2e3f4a5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COL = lambda: sa.Column(  # noqa: E731
    "sonda_ativa", sa.Boolean(), nullable=False, server_default=sa.text("true")
)


def upgrade() -> None:
    for tabela in ("locais", "agrupamentos"):
        with op.batch_alter_table(tabela) as b:
            b.add_column(_COL())
    with op.batch_alter_table("sonda_ia_respostas") as b:
        b.add_column(sa.Column("entidade", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sonda_ia_respostas") as b:
        b.drop_column("entidade")
    for tabela in ("agrupamentos", "locais"):
        with op.batch_alter_table(tabela) as b:
            b.drop_column("sonda_ativa")
