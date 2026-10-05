import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from db.session import Base, DATABASE_URL as APP_DATABASE_URL, setup_schema
from db.models import JobListing  # noqa: F401 — registers the table with Base


def _test_database_url() -> str:
    """Tests create/drop tables and wipe rows freely — never point that at
    the app's real database, or a local run against a shared dev DB (or a
    misconfigured CI job) silently destroys real data. Always use a
    dedicated *_test database, created on demand if it doesn't exist."""
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        return explicit
    base, _, dbname = APP_DATABASE_URL.rpartition("/")
    if dbname.endswith("_test"):
        return APP_DATABASE_URL
    return f"{base}/{dbname}_test"


TEST_DATABASE_URL = _test_database_url()


def _ensure_test_database_exists():
    admin_url = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
    test_db_name = TEST_DATABASE_URL.rsplit("/", 1)[1]
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": test_db_name},
            ).first()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{test_db_name}"'))
    finally:
        admin_engine.dispose()


_ensure_test_database_exists()
engine = create_engine(TEST_DATABASE_URL)
TestSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def _database():
    """Runs against TEST_DATABASE_URL (a dedicated *_test database), never
    the app's own DATABASE_URL — see _test_database_url() above. Also runs
    the same setup_schema() as init_db() (not just create_all()) — the
    skills filter calls a custom SQL function, and the RAG tables need the
    pgvector extension, so both must exist here too."""
    setup_schema(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db_session():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.query(JobListing).delete()
        session.commit()
        session.close()


_job_counter = 0


def make_job(session, **overrides):
    global _job_counter
    _job_counter += 1
    defaults = dict(
        source_job_id=f"test-job-{_job_counter}",
        title="Software Engineer",
        company="Acme Corp",
        source="indeed",
        url="https://example.com/job",
    )
    defaults.update(overrides)
    job = JobListing(**defaults)
    session.add(job)
    session.commit()
    return job
