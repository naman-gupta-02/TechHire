import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://techhire:localdev@localhost:5432/techhire_db")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# Trigram GIN indexes matching the exact expressions _build_query() filters
# on in api.py (lower(title)/lower(company) LIKE, array_to_string(...) ILIKE)
# — created via raw SQL rather than SQLAlchemy Index() because
# create_all() only creates indexes as part of creating a brand-new table,
# never adds them to a table that already exists (which every environment
# but a fresh one is). IF NOT EXISTS makes this safe to run on every startup.
#
# array_to_string() can't be indexed directly — Postgres marks it STABLE,
# not IMMUTABLE, so it refuses it in an expression index. Wrapping it in a
# trivial SQL function we declare IMMUTABLE ourselves is the standard
# workaround (safe here since the separator is a literal, so the output
# really is deterministic for a given input). api.py's skills filter calls
# this same wrapper instead of the built-in, so the planner can match it
# against the index.
_INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS ix_job_listings_title_trgm "
    "ON job_listings USING gin (lower(title) gin_trgm_ops)",
    "CREATE INDEX IF NOT EXISTS ix_job_listings_company_trgm "
    "ON job_listings USING gin (lower(company) gin_trgm_ops)",
    "CREATE OR REPLACE FUNCTION immutable_array_to_string(text[], text) "
    "RETURNS text AS $$ SELECT array_to_string($1, $2) $$ "
    "LANGUAGE sql IMMUTABLE PARALLEL SAFE",
    "CREATE INDEX IF NOT EXISTS ix_job_listings_skills_trgm "
    "ON job_listings USING gin (immutable_array_to_string(required_skills, ',') gin_trgm_ops)",
]


# Must run before create_all(): job_chunks/job_vectors declare `vector`
# columns, which don't exist as a type until the extension is loaded.
_EXTENSION_STATEMENTS = [
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
    "CREATE EXTENSION IF NOT EXISTS vector",
]


def setup_schema(target_engine):
    """Extensions → tables → raw-SQL indexes, in that order. Shared by
    init_db() and the test suite so both build the exact same schema."""
    from . import models  # noqa: F401 — registers models with Base
    with target_engine.begin() as conn:
        for stmt in _EXTENSION_STATEMENTS:
            conn.execute(text(stmt))
    Base.metadata.create_all(target_engine)
    with target_engine.begin() as conn:
        for stmt in _INDEX_STATEMENTS:
            conn.execute(text(stmt))


def init_db():
    setup_schema(engine)
