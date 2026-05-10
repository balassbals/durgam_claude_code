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
        assert counts["roles"] == 3
        assert counts["permissions"] == 7
        assert counts["users"] == 3
        assert counts["holidays"] == 2
        assert counts["role_emails"] == 1
        assert counts["student_category_counts"] == 1
        assert counts["role_permissions"] == 11

    def test_second_run_inserts_zero_rows(self, db_engine):
        """Run seed twice on the same DB; second run should insert nothing."""
        from scripts.seed import seed

        with Session(db_engine) as session:
            seed(session)
            session.commit()

        with Session(db_engine) as session:
            counts2 = seed(session)
            session.commit()

        insertable = {k: v for k, v in counts2.items() if k != "role_emails"}
        assert all(v == 0 for v in insertable.values()), f"Non-zero on 2nd run: {counts2}"
        assert counts2["role_emails"] == 0

    def test_seed_creates_active_records_only(self, seeded_session):
        users = seeded_session.exec(
            select(User).where(User.is_deleted == False)  # noqa: E712
        ).all()
        assert len(users) >= 3
        assert all(u.is_active for u in users)

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
