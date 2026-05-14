"""Shared pytest fixtures.

Integration tests require a running PostgreSQL. The TEST_DATABASE_URL must
point to a live PostgreSQL instance:
- Locally: run `docker compose up db -d`, then `pytest tests/integration/`.
- In CI: uses the GitHub Actions postgres service (see .github/workflows/ci.yml).
  See docs/runbook.md for the local developer workflow.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy import text as _text
from sqlmodel import Session, SQLModel

# Import all models so SQLModel metadata is populated.
import durgam.models  # noqa: F401
from durgam.config import settings


def _ensure_test_db(url: str) -> None:
    """Create the test database if it does not exist yet.

    Connects to the 'postgres' maintenance database (always present) with
    AUTOCOMMIT so the CREATE DATABASE DDL is not wrapped in a transaction.
    """
    base, db_name = url.rsplit("/", 1)
    maint_engine = create_engine(f"{base}/postgres", isolation_level="AUTOCOMMIT")
    with maint_engine.connect() as conn:
        exists = conn.scalar(
            _text("SELECT 1 FROM pg_database WHERE datname = :n"),
            {"n": db_name},
        )
        if not exists:
            conn.execute(_text(f'CREATE DATABASE "{db_name}"'))
    maint_engine.dispose()


@pytest.fixture(scope="session")
def db_engine():
    """Session-scoped engine pointing at the TEST database.

    Creates the database (if absent) and all tables at session start,
    drops tables at session end. Uses a DIFFERENT database from the dev
    database (durgam_test).
    """
    _ensure_test_db(settings.test_database_url)
    engine = create_engine(settings.test_database_url, echo=False)
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    """Function-scoped session that rolls back after each test.

    All changes made within a test are undone on teardown — the DB stays clean.
    If a test raises IntegrityError inside pytest.raises, SQLAlchemy internally
    deassociates the transaction; the try/except handles that case without warning.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    try:
        transaction.rollback()
    except Exception:
        pass
    connection.close()


@pytest.fixture(scope="session")
def seeded_db_engine():
    """Session-scoped engine with seed data applied once for the session."""
    from scripts.seed import seed

    _ensure_test_db(settings.test_database_url)
    engine = create_engine(settings.test_database_url, echo=False)
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        seed(session)

    yield engine
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def seeded_session(seeded_db_engine):
    """Read-only-ish session on top of seeded data (still uses rollback)."""
    connection = seeded_db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    try:
        transaction.rollback()
    except Exception:
        pass
    connection.close()
