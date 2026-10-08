"""Database engine, session factory and the legacy schema-sync helper.

Schema changes are owned by **Alembic** (``alembic/``). ``run_migrations`` is
retained as a compatibility shim for databases created before Alembic was
introduced: it inspects the live schema and applies anything the models declare
but the database lacks. New work must add an Alembic revision instead.
"""

import logging

from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DEFAULT_SQLITE_PATH, REPO_ROOT, settings

logger = logging.getLogger(__name__)

SQLALCHEMY_DATABASE_URL = settings.resolved_database_url

engine = create_engine(SQLALCHEMY_DATABASE_URL, **settings.sqlalchemy_engine_options())

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Deterministic constraint names.
#
# SQLite cannot ALTER most things in place, so Alembic rewrites the table in
# "batch" mode — and that requires every constraint to have a name. Autogenerate
# emits `None` for unnamed constraints, which then raises
# "Constraint must have a name" during the rewrite. A naming convention fixes the
# root cause once instead of hand-naming constraints in every future migration.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

Base = declarative_base(metadata=MetaData(naming_convention=NAMING_CONVENTION))



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _column_ddl(column, dialect) -> str:
    """Render ``name TYPE`` for an ADD COLUMN statement on the target dialect."""
    col_type = column.type.compile(dialect=dialect)
    return f'"{column.name}" {col_type}'


def run_migrations(bind=engine) -> list[str]:
    """Create missing tables/columns/indexes. Returns a log of applied changes."""
    applied: list[str] = []

    # 1. Create any brand new tables (and the indexes attached to them).
    Base.metadata.create_all(bind=bind)

    inspector = inspect(bind)
    dialect = bind.dialect

    with bind.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue

            existing_cols = {c["name"] for c in inspector.get_columns(table.name)}

            # 2. Add columns that exist on the model but not in the database.
            for column in table.columns:
                if column.name in existing_cols:
                    continue
                # SQLite cannot add a NOT NULL column without a default; new
                # columns are therefore created nullable and backfilled below.
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN {_column_ddl(column, dialect)}'
                try:
                    conn.execute(text(ddl))
                    applied.append(f"ADD COLUMN {table.name}.{column.name}")
                    logger.info("Migration applied: %s", ddl)
                except Exception as exc:  # pragma: no cover - dialect specific
                    logger.warning("Could not add %s.%s: %s", table.name, column.name, exc)

            # 3. Backfill literal defaults (e.g. ``default=False``) for the
            #    columns we just added, so existing rows are not left NULL where
            #    the application expects a value.
            for column in table.columns:
                if column.name in existing_cols:
                    continue
                default = column.default
                value = default.arg if default is not None and getattr(default, "is_scalar", False) else None
                # bool False must still be written, so compare against None.
                if value is None:
                    continue
                conn.execute(
                    text(f'UPDATE "{table.name}" SET "{column.name}" = :v WHERE "{column.name}" IS NULL'),
                    {"v": value},
                )

            # 4. Create indexes declared on the model that the DB is missing.
            existing_indexes = {i["name"] for i in inspector.get_indexes(table.name)}
            for index in table.indexes:
                if index.name in existing_indexes:
                    continue
                cols = ", ".join(f'"{c.name}"' for c in index.columns)
                stmt = f'CREATE INDEX IF NOT EXISTS "{index.name}" ON "{table.name}" ({cols})'
                try:
                    conn.execute(text(stmt))
                    applied.append(f"CREATE INDEX {index.name}")
                    logger.info("Migration applied: %s", stmt)
                except Exception as exc:  # pragma: no cover - dialect specific
                    logger.warning("Could not create index %s: %s", index.name, exc)

    if applied:
        logger.info("Schema migration complete: %d change(s)", len(applied))
    return applied
