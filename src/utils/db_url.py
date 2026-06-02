"""Normalização da URL do banco para o driver psycopg3 (deploy — CP-deploy-1).

Render (e Heroku) entregam ``DATABASE_URL`` como ``postgresql://…`` ou
``postgres://…`` — esquemas que o SQLAlchemy 2.0 roteia para o **psycopg2**, que
não está instalado (usamos ``psycopg[binary]`` v3). Sem reescrever o esquema para
``postgresql+psycopg://`` o app/alembic quebram no boot em produção.

Helper único, reusado por ``src/config.py`` e ``alembic/env.py`` (os dois pontos
que leem ``DATABASE_URL`` cru) — a lógica não fica duplicada.
"""

from __future__ import annotations

_PSYCOPG_DIALECT = "postgresql+psycopg://"


def normalize_db_url(url: str) -> str:
    """Força o dialeto psycopg3 nos esquemas Postgres "nus" do Render/Heroku.

    - ``postgresql://…``  → ``postgresql+psycopg://…``
    - ``postgres://…``    → ``postgresql+psycopg://…`` (legacy Heroku)
    - Idempotente: ``postgresql+psycopg://`` (ou qualquer ``postgresql+driver://``)
      passa intacto — não começa com ``postgresql://`` (o próximo char é ``+``).
    - ``sqlite://…`` e qualquer outro esquema passam intactos.
    - ``None``/``""`` passam intactos.
    """
    if not url:
        return url
    if url.startswith("postgresql://"):
        return _PSYCOPG_DIALECT + url.removeprefix("postgresql://")
    if url.startswith("postgres://"):
        return _PSYCOPG_DIALECT + url.removeprefix("postgres://")
    return url
