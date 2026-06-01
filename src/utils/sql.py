"""Helpers SQL portáveis entre SQLite (dev) e Postgres (prod).

``func.strftime`` é SQLite-only; no Postgres usa-se ``to_char``. ``_FmtData``
compila pro dialeto certo (strftime no SQLite, to_char no Postgres) — use os
wrappers ``fmt_ano_mes``/``fmt_ano``/``fmt_mes`` no lugar de ``func.strftime``.
"""

from __future__ import annotations

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ColumnElement, FunctionElement


class _FmtData(FunctionElement):
    """Formata uma coluna de data como texto, portável SQLite/Postgres.

    O FORMATO é renderizado INLINE como literal (não bound param): assim o mesmo
    ``_FmtData`` no SELECT e no GROUP BY produz SQL idêntico — o Postgres é
    estrito e exige expressões textualmente iguais no GROUP BY. Os formatos são
    constantes internas (sem risco de injeção)."""

    name = "fmt_data"
    inherit_cache = False  # o formato varia por instância; não compartilhar o cache

    def __init__(self, col: ColumnElement, sqlite_fmt: str, pg_fmt: str) -> None:
        super().__init__(col)
        self._sqlite_fmt = sqlite_fmt
        self._pg_fmt = pg_fmt


@compiles(_FmtData, "sqlite")
def _fmt_sqlite(element, compiler, **kw):  # noqa: ANN001, ANN201
    (col,) = element.clauses
    return f"strftime('{element._sqlite_fmt}', {compiler.process(col, **kw)})"


@compiles(_FmtData)
def _fmt_default(element, compiler, **kw):  # noqa: ANN001, ANN201 — Postgres + outros
    (col,) = element.clauses
    return f"to_char({compiler.process(col, **kw)}, '{element._pg_fmt}')"


def fmt_ano_mes(col: ColumnElement) -> _FmtData:
    """'2026-05' — equivale a ``strftime('%Y-%m', col)``."""
    return _FmtData(col, "%Y-%m", "YYYY-MM")


def fmt_ano(col: ColumnElement) -> _FmtData:
    """'2026' — equivale a ``strftime('%Y', col)``."""
    return _FmtData(col, "%Y", "YYYY")


def fmt_mes(col: ColumnElement) -> _FmtData:
    """'05' — equivale a ``strftime('%m', col)`` (zero-padded)."""
    return _FmtData(col, "%m", "MM")


class _GroupConcat(FunctionElement):
    """Agregado de concatenação portável: ``group_concat`` (SQLite) /
    ``string_agg`` (Postgres). Separador inline (constante interna)."""

    name = "group_concat_portable"
    inherit_cache = False

    def __init__(self, col: ColumnElement, sep: str) -> None:
        super().__init__(col)
        self._sep = sep


@compiles(_GroupConcat, "sqlite")
def _gc_sqlite(element, compiler, **kw):  # noqa: ANN001, ANN201
    (col,) = element.clauses
    return f"group_concat({compiler.process(col, **kw)}, '{element._sep}')"


@compiles(_GroupConcat)
def _gc_default(element, compiler, **kw):  # noqa: ANN001, ANN201 — Postgres + outros
    (col,) = element.clauses
    # string_agg exige texto; cast defensivo p/ colunas não-text.
    return f"string_agg({compiler.process(col, **kw)}::text, '{element._sep}')"


def group_concat(col: ColumnElement, sep: str = "|") -> _GroupConcat:
    """Concatena valores agregados com ``sep``. Portável SQLite/Postgres."""
    return _GroupConcat(col, sep)
