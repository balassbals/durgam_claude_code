"""Integration tests for scripts/seed.py — idempotency and expected row counts.

Note: test_first_run_inserts_expected_rows asserts total row counts after seeding,
not insert-count deltas. This is necessary because the seeded_db_engine fixture
(session-scoped) may have already committed seed data to the test DB before this
test runs, making the INSERT counts unreliable. Total counts are stable regardless.
"""

from sqlmodel import Session, func, select

from durgam.models.config_anchors import AcademicYear
from durgam.models.identity import Permission, Role, RolePermission, User


def _count(session, model):
    return session.exec(select(func.count()).select_from(model)).one()


class TestSeed:
    def test_first_run_inserts_expected_rows(self, db_session):
        from scripts.seed import seed

        seed(db_session)
        db_session.commit()

        # Assert TOTAL row counts after seed (stable regardless of pre-existing data).
        # M8 Phase 4: 32 roles (30 prior + PROFESSOR, ASSOC_PROFESSOR).
        assert _count(db_session, Role) == 32, "Expected 32 seeded roles at M8 Phase 4"
        # M8.1: 118 triples (117 prior + 1 new: leave_balance_import:write:*).
        assert _count(db_session, Permission) == 118, "Expected 118 seeded permission triples at M8.1 Phase 3"
        assert _count(db_session, User) >= 25, "Expected at least 25 seeded users"
        assert _count(db_session, RolePermission) >= 100, "Expected at least 100 role→permission rows"
        ay = db_session.exec(select(AcademicYear).where(AcademicYear.code == "2025-26")).first()
        assert ay is not None, "AcademicYear 2025-26 must exist after seeding"
        ay_prev = db_session.exec(select(AcademicYear).where(AcademicYear.code == "2024-25")).first()
        assert ay_prev is not None, "AcademicYear 2024-25 must exist after seeding"
        assert ay_prev.is_locked is True, "AcademicYear 2024-25 must be locked"

    def test_second_run_inserts_zero_rows(self, db_engine):
        """Run seed twice on the same DB; second run should insert nothing for most tables.

        Users and roles use ON CONFLICT DO UPDATE so they always return a row count
        (password re-hash for users; level updates for roles). All other tables
        use ON CONFLICT DO NOTHING.
        """
        from scripts.seed import seed

        with Session(db_engine) as session:
            seed(session)
            session.commit()

        with Session(db_engine) as session:
            counts2 = seed(session)
            session.commit()

        # Exclude roles (on_conflict_do_update counts all processed rows),
        # users (password re-hash on every run), role_emails (select-guard),
        # and approval_processes (on_conflict_do_update for channel changes).
        non_upsert = {
            k: v
            for k, v in counts2.items()
            if k not in ("role_emails", "users", "roles", "approval_processes")
        }
        assert all(v == 0 for v in non_upsert.values()), (
            f"Non-zero on 2nd run: {counts2}"
        )
        assert counts2["role_emails"] == 0

    def test_seed_creates_expected_active_and_inactive_users(self, seeded_session):
        all_users = seeded_session.exec(
            select(User).where(User.is_deleted == False)  # noqa: E712
        ).all()
        assert len(all_users) >= 25
        active = [u for u in all_users if u.is_active]
        inactive = [u for u in all_users if not u.is_active]
        must_change = [u for u in all_users if u.must_change_password]
        assert len(active) >= 24  # all except inactive_user
        assert len(inactive) >= 1  # inactive_user
        assert len(must_change) >= 1  # firstlogin_user

    def test_academic_year_is_not_locked(self, seeded_session):
        ay = seeded_session.exec(select(AcademicYear).where(AcademicYear.code == "2025-26")).first()
        assert ay is not None
        assert ay.is_locked is False

    def test_no_real_personal_data_in_seed(self, seeded_session):
        """Verify that seeded emails are institutional placeholders, not real addresses."""
        users = seeded_session.exec(select(User)).all()
        for user in users:
            assert user.email.endswith("@sssihl.edu.in") or user.email.endswith("@test.com"), (
                f"User {user.username!r} has unexpected email domain: {user.email!r}"
            )
