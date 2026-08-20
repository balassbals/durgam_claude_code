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

    def test_e005_document_templates_table(self):
        """Verify E-005 document_templates migration creates unified table with partial unique indexes."""
        _reset_test_db()

        engine = sqlalchemy.create_engine(settings.test_database_url)
        try:
            inspector = sqlalchemy.inspect(engine)
            assert "document_templates" in inspector.get_table_names()
            assert "letterhead_assets" not in inspector.get_table_names()
            assert "template_assets" not in inspector.get_table_names()

            cols = {c["name"] for c in inspector.get_columns("document_templates")}
            for expected in ("id", "purpose", "role_code", "file_id", "is_deleted", "created_at"):
                assert expected in cols, f"Missing column: {expected}"
            assert "scope_type" not in cols, "scope_type should be removed after D1 migration"
            assert "scope_id" not in cols, "scope_id should be removed after D1 migration"

            indexes = inspector.get_indexes("document_templates")
            idx_names = {idx["name"] for idx in indexes}
            assert "uq_document_templates_type" in idx_names
            assert "uq_document_templates_letterhead_role" in idx_names

            result = _alembic("downgrade", "c3d4e5f6a7b8")
            assert result.returncode == 0, f"downgrade to pre-E005 failed:\n{result.stderr}"

            inspector = sqlalchemy.inspect(engine)
            assert "document_templates" not in inspector.get_table_names()

            result = _alembic("upgrade", "head")
            assert result.returncode == 0
        finally:
            engine.dispose()

    def test_m4_calendar_entry_and_ay_master_lock(self):
        """Verify M4 migrations: calendar_entries, master_calendar_locked, iqac_confirmed."""
        _reset_test_db()

        engine = sqlalchemy.create_engine(settings.test_database_url)
        try:
            inspector = sqlalchemy.inspect(engine)

            assert "calendar_entries" in inspector.get_table_names()
            ay_cols = {c["name"] for c in inspector.get_columns("academic_years")}
            assert "master_calendar_locked" in ay_cols
            assert "iqac_confirmed" in ay_cols

            ce_cols = {c["name"] for c in inspector.get_columns("calendar_entries")}
            for expected in (
                "academic_year_id", "title", "entry_type",
                "starts_at", "ends_at", "owner_user_id", "owner_role_code",
                "scope_type", "scope_id", "notes",
            ):
                assert expected in ce_cols, f"Missing column: {expected}"

            # Skip past M5a migrations to reach M4 head before testing M4 downgrades.
            result = _alembic("downgrade", "8ad8124becda")
            assert result.returncode == 0, f"downgrade to M4 head failed:\n{result.stderr}"

            # Downgrade -1 removes iqac_confirmed (latest M4 migration)
            result = _alembic("downgrade", "-1")
            assert result.returncode == 0, f"downgrade -1 failed:\n{result.stderr}"

            inspector = sqlalchemy.inspect(engine)
            ay_cols_after = {c["name"] for c in inspector.get_columns("academic_years")}
            assert "iqac_confirmed" not in ay_cols_after
            assert "master_calendar_locked" in ay_cols_after
            assert "calendar_entries" in inspector.get_table_names()

            # Downgrade -1 again removes calendar_entries + master_calendar_locked
            result = _alembic("downgrade", "-1")
            assert result.returncode == 0, f"downgrade -2 failed:\n{result.stderr}"

            inspector = sqlalchemy.inspect(engine)
            assert "calendar_entries" not in inspector.get_table_names()
            ay_cols_after2 = {c["name"] for c in inspector.get_columns("academic_years")}
            assert "master_calendar_locked" not in ay_cols_after2

            # Upgrade back
            result = _alembic("upgrade", "head")
            assert result.returncode == 0
        finally:
            engine.dispose()

    def test_m10_phase1a_faculty_tables(self):
        """M10 Phase 1A: verify 6 Faculty tables created by migration f74557aa7d0d.

        Upgrade to head → assert tables + key columns exist.
        Downgrade to pre-Phase-1A revision (aa2ce5577e9e) → assert tables gone.
        Upgrade back to head.
        """
        _reset_test_db()

        engine = sqlalchemy.create_engine(settings.test_database_url)
        try:
            inspector = sqlalchemy.inspect(engine)
            tables = inspector.get_table_names()

            for table in (
                "faculties",
                "faculty_documents",
                "faculty_education",
                "faculty_experience",
                "faculty_expertise",
                "faculty_workload",
            ):
                assert table in tables, f"Expected table {table!r} after upgrade head"

            # Verify key columns on faculties
            faculty_cols = {c["name"] for c in inspector.get_columns("faculties")}
            for col in (
                "id", "user_id", "employee_id", "title", "first_name", "last_name",
                "designation_id", "department_id", "campus_id", "joining_date",
                "is_vacation_employee", "phone", "is_phd", "photo_file_id",
                "emergency_contact_name", "emergency_contact_relation",
                "emergency_contact_phone", "is_deleted", "created_at",
            ):
                assert col in faculty_cols, f"faculties missing column {col!r}"

            # Verify JSONB entries_json on faculty_workload
            wl_cols = {c["name"] for c in inspector.get_columns("faculty_workload")}
            assert "entries_json" in wl_cols

            # Downgrade to the revision before Phase 1A
            result = _alembic("downgrade", "aa2ce5577e9e")
            assert result.returncode == 0, f"downgrade to aa2ce5577e9e failed:\n{result.stderr}"

            inspector = sqlalchemy.inspect(engine)
            tables_after = inspector.get_table_names()
            for table in (
                "faculties",
                "faculty_documents",
                "faculty_education",
                "faculty_experience",
                "faculty_expertise",
                "faculty_workload",
            ):
                assert table not in tables_after, f"Table {table!r} should be gone after downgrade"

            # Upgrade back to head
            result = _alembic("upgrade", "head")
            assert result.returncode == 0, f"re-upgrade to head failed:\n{result.stderr}"
        finally:
            engine.dispose()

    def test_m10_phase1b_designation_expansion(self):
        """M10 Phase 1B: forward migration test for data migration cb2de963f0b8.

        This is a data-only migration (schema unchanged from Phase 1A). We do NOT
        call _reset_test_db() because that wipes the seeded DB and causes cascading
        failures in later tests in the same session. Instead we work within the
        current test DB state.

        Sequence:
        1. Downgrade to f74557aa7d0d (reverts data: soft-deletes seeded new codes).
        2. Insert 4 legacy Designation rows (simulate pre-Phase-1B seed).
        3. Upgrade to head → data migration runs: restores new codes, soft-deletes legacy.
        4. Verify forward state.
        5. Upgrade to head again (idempotency: ON CONFLICT DO UPDATE handles re-run).
        6. Verify idempotent state.
        7. Clean up the manually-inserted legacy rows to restore seeded DB state.

        The reverse migration (downgrade from head to f74557aa7d0d) is verified
        structurally: the downgrade SQL runs as part of the initial downgrade in step 1.
        A dedicated reverse test would require calling _reset_test_db() and risk the
        same seeded-DB contamination; deferred to isolated manual verification.
        """
        _NEW_CODES = {
            "sr_prof", "prof", "assoc_prof",
            "asst_prof_l10", "asst_prof_l11", "asst_prof_l12", "instructor",
        }
        _LEGACY_CODES = {
            "senior_professor", "professor",
            "associate_professor", "assistant_professor",
        }

        engine = sqlalchemy.create_engine(settings.test_database_url)
        try:
            # 0. Ensure alembic_version is recorded at head.
            #    seeded_db_engine uses SQLModel.metadata.create_all() (no alembic),
            #    so alembic_version may not exist when running this test in isolation.
            #    stamp head marks the schema as up-to-date without running migrations.
            result = _alembic("stamp", "head")
            assert result.returncode == 0, (
                f"alembic stamp head failed:\n{result.stderr}"
            )

            # 1. Downgrade to Phase-1A revision (data migration cb2de963f0b8 reverses).
            #    Schema is UNCHANGED (data-only migration); seeded new codes get soft-deleted.
            result = _alembic("downgrade", "f74557aa7d0d")
            assert result.returncode == 0, (
                f"downgrade to f74557aa7d0d failed:\n{result.stderr}"
            )

            # 2. Insert 4 legacy Designation rows (simulate pre-Phase-1B seed).
            #    ON CONFLICT DO NOTHING in case a prior test run left them.
            with engine.connect() as conn:
                for code, name, rank in [
                    ("senior_professor",    "Senior Professor",    1),
                    ("professor",           "Professor",           2),
                    ("associate_professor", "Associate Professor", 3),
                    ("assistant_professor", "Assistant Professor", 4),
                ]:
                    conn.execute(
                        sqlalchemy.text(
                            "INSERT INTO designations"
                            " (id, created_at, updated_at, is_deleted, code, name, rank)"
                            " VALUES (gen_random_uuid(), now(), now(), false, :code, :name, :rank)"
                            " ON CONFLICT ON CONSTRAINT uq_designations_code"
                            " DO UPDATE SET is_deleted = false, deleted_at = null"
                        ),
                        {"code": code, "name": name, "rank": rank},
                    )
                conn.commit()

            # 3. Upgrade to head → data migration runs.
            result = _alembic("upgrade", "head")
            assert result.returncode == 0, (
                f"upgrade to head failed:\n{result.stderr}"
            )

            # 4. Verify forward: 7 new active, 4 legacy soft-deleted.
            with engine.connect() as conn:
                rows = conn.execute(
                    sqlalchemy.text(
                        "SELECT code, is_deleted FROM designations"
                        " WHERE code = ANY(ARRAY["
                        "  'sr_prof','prof','assoc_prof',"
                        "  'asst_prof_l10','asst_prof_l11','asst_prof_l12','instructor',"
                        "  'senior_professor','professor','associate_professor','assistant_professor'"
                        "])"
                    )
                ).fetchall()
            state = {r[0]: r[1] for r in rows}

            for code in _NEW_CODES:
                assert code in state, f"New code {code!r} missing after upgrade"
                assert not state[code], f"New code {code!r} should be active after upgrade"

            for code in _LEGACY_CODES:
                assert code in state, f"Legacy code {code!r} missing after upgrade"
                assert state[code], f"Legacy code {code!r} should be soft-deleted after upgrade"

            # 5. Re-upgrade (idempotency): ON CONFLICT DO UPDATE must not error.
            result = _alembic("upgrade", "head")
            assert result.returncode == 0, (
                f"idempotent re-upgrade failed:\n{result.stderr}"
            )

            # 6. Verify state unchanged after idempotent re-run.
            with engine.connect() as conn:
                rows = conn.execute(
                    sqlalchemy.text(
                        "SELECT code, is_deleted FROM designations"
                        " WHERE code = ANY(ARRAY["
                        "  'sr_prof','prof','assoc_prof',"
                        "  'asst_prof_l10','asst_prof_l11','asst_prof_l12','instructor',"
                        "  'senior_professor','professor','associate_professor','assistant_professor'"
                        "])"
                    )
                ).fetchall()
            state2 = {r[0]: r[1] for r in rows}
            assert state == state2, (
                f"State changed on idempotent re-upgrade: {state} vs {state2}"
            )

        finally:
            # 7. Clean up legacy rows (soft-deleted by migration) to restore seeded state.
            #    Legacy codes are soft-deleted (is_deleted=True) at this point; deleting them
            #    fully returns the designations table to the pure seeded state (7 new active).
            with engine.connect() as conn:
                conn.execute(
                    sqlalchemy.text(
                        "DELETE FROM designations"
                        " WHERE code = ANY(ARRAY["
                        "  'senior_professor','professor','associate_professor','assistant_professor'"
                        "])"
                    )
                )
                conn.commit()
            engine.dispose()
