"""Integration tests: forward and reverse migration against real PostgreSQL.

Migrations run against the TEST database (settings.test_database_url),
not the dev database. This avoids wiping seed data from the dev DB when
running 'alembic downgrade base'.
"""

import os
import subprocess
import sys

from durgam.config import settings


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
        """Verify full down-to-base then up-to-head cycle works cleanly."""
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
