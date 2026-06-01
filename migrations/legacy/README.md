# migrations/legacy/ — migrations SQLite históricas (APOSENTADAS)

Estes 32 `.sql` (001→032) construíram o schema incrementalmente no dev-SQLite,
aplicados por `scripts/init_db.py` ("roda todos os `.sql` em ordem").

**A partir do CP-1.2, o runner de schema é o Alembic** — não estes `.sql`.

- **Fonte do schema:** os **models SQLAlchemy** (`src/models/`). O baseline do
  Alembic (`alembic/versions/*_baseline_schema.py`) é gerado por `autogenerate`
  a partir de `Base.metadata`.
- **Aplicar schema (dev/CI/prod):** `alembic upgrade head` (lê `DATABASE_URL`).
  `scripts/init_db.py` virou um wrapper fino que chama isso — o comando antigo
  não quebra.
- **Novas mudanças de schema:** `alembic revision --autogenerate -m "..."`
  (depois de editar os models), revisar a migration gerada, commitar.

**Não edite nem adicione `.sql` aqui** — são histórico. Mantidos para
rastreabilidade (o que cada migration fez, quando). O drift entre estes `.sql` e
os models foi reconciliado no CP-1.2 (índices de performance, índice parcial 015,
CHECKs) — diff column-set provou drift-zero antes do baseline.
