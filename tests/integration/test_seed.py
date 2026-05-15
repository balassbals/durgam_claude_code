"""Integration tests for scripts/seed.py — idempotency and expected row counts."""

from sqlmodel import Session, func, select

from durgam.models.config_anchors import AcademicYear
from durgam.models.identity import User


def _count(session, model):
    return session.exec(select(func.count()).select_from(model)).one()


class TestSeed:
    def test_first_run_inserts_expected_rows(self, db_session):
        from scripts.seed import seed

        counts = seed(db_session)
        db_session.commit()

        assert counts["academic_years"] == 1
        # M2 adds BASIC_USER role → 4 roles total.
        assert counts["roles"] == 4
        # M2 adds user:delete, role:read/write/delete, permission:read, audit_log:read → 13 total.
        assert counts["permissions"] == 13
        assert counts["users"] == 5  # 3 active + 1 inactive + 1 must_change (M1 E2E fixtures)
        assert counts["holidays"] == 2
        assert counts["role_emails"] == 1
        assert counts["student_category_counts"] == 1
        # SYSTEM_ADMIN=13, DEAN=3, STUDENT=1, BASIC_USER=0 → 17 total.
        assert counts["role_permissions"] == 17

    def test_second_run_inserts_zero_rows(self, db_engine):
        """Run seed twice on the same DB; second run should insert nothing for most tables.

        Users use ON CONFLICT DO UPDATE (to refresh bcrypt hashes), so they always
        return a row count. All other tables use ON CONFLICT DO NOTHING.
        """
        from scripts.seed import seed

        with Session(db_engine) as session:
            seed(session)
            session.commit()

        with Session(db_engine) as session:
            counts2 = seed(session)
            session.commit()

        non_user = {k: v for k, v in counts2.items() if k not in ("role_emails", "users")}
        assert all(v == 0 for v in non_user.values()), f"Non-zero on 2nd run: {counts2}"
        assert counts2["role_emails"] == 0

    def test_seed_creates_expected_active_and_inactive_users(self, seeded_session):
        all_users = seeded_session.exec(
            select(User).where(User.is_deleted == False)  # noqa: E712
        ).all()
        assert len(all_users) >= 5
        active = [u for u in all_users if u.is_active]
        inactive = [u for u in all_users if not u.is_active]
        must_change = [u for u in all_users if u.must_change_password]
        assert len(active) >= 4  # sys_admin, dean_sci, student_001, firstlogin_user
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
