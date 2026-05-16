"""Integration tests: forward and reverse migration against real PostgreSQL.

Migrations run against the TEST database (settings.test_database_url),
not the dev database. This avoids wiping seed data from the dev DB when
running 'alembic downgrade base'.
"""

import os
import subprocess
import sys

import sqlalchemy
import sqlmodel

import durgam.models  # noqa: F401 — populate SQLModel.metadata before drop_all
from durgam.config import settings


def _reset_test_db() -> None:
    """Drop ALL tables (SQLModel + alembic_version) then upgrade to head.

    The seeded_db_engine fixture (session-scoped) calls
    SQLModel.metadata.drop_all() which removes all user/role/etc. tables but
    leaves alembic_version at the current head revision. This creates an
    inconsistent state that makes both 'downgrade base' and 'upgrade head'
    fail. The fix: drop everything including alembic_version, then let
    'upgrade head' recreate the schema cleanly from scratch.
    """
    engine = sqlalchemy.create_engine(settings.test_database_url)
    try:
        # Drop alembic_version (not in SQLModel metadata so drop_all misses it).
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("DROP TABLE IF EXISTS alembic_version"))
            conn.commit()
        # Drop all SQLModel tables.
        sqlmodel.SQLModel.metadata.drop_all(engine)
    finally:
        engine.dispose()
    # Recreate schema from scratch via Alembic (sets alembic_version = head).
    _alembic("upgrade", "head")


def _alembic(*args: str) -> subprocess.CompletedProcess[str]:
    """Run an alembic command against the TEST database."""
    env = os.environ.copy()
    # Override the database URLs so alembic/env.py targets the test database.
    env["DATABASE_URL"] = settings.test_database_url
    env["DATABASE_URL_SYNC"] = settings.test_database_url
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        capture_output=True,
        text=True,
        env=env,
    )


class TestMigrations:
    def test_downgrade_to_base_and_upgrade_to_head(self):
        """Verify full down-to-base then up-to-head cycle works cleanly.

        Runs upgrade head first to repair any inconsistency caused by the
        seeded_db_engine fixture's teardown: that fixture calls
        SQLModel.metadata.drop_all() which removes all user tables but leaves
        alembic_version at the current head. Without this repair step, the
        subsequent downgrade fails with 'relation "users" does not exist'
        because Alembic reads alembic_version=head but the table is gone.
        """
        # Reset to a guaranteed-clean state before the downgrade/upgrade cycle.
        _reset_test_db()

        result = _alembic("downgrade", "base")
        assert result.returncode == 0, f"downgrade base failed:\n{result.stderr}"

        result = _alembic("upgrade", "head")
        assert result.returncode == 0, f"upgrade head failed:\n{result.stderr}"

    def test_current_shows_head_after_upgrade(self):
        result = _alembic("current")
        assert result.returncode == 0
        assert "(head)" in result.stdout or "(head)" in result.stderr

    def test_downgrade_minus_one_from_head(self):
        result = _alembic("downgrade", "-1")
        assert result.returncode == 0, f"downgrade -1 failed:\n{result.stderr}"

        # Upgrade back so subsequent tests have a schema
        result = _alembic("upgrade", "head")
        assert result.returncode == 0
