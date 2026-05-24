"""Integration tests for RoleEmail E-004 remediation.

Covers: bootstrap row survival after re-key, M4 calendar email lookup,
NULL-scope duplicate rejection at DB level, scoped duplicate rejection,
soft-deleted row excluded from unique constraint.
"""

from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlmodel import select

from durgam.models.config_anchors import RoleEmail
from durgam.models.identity import User
from durgam.repositories.role_email import RoleEmailRepository


def _user(session) -> User:
    u = User(
        username=f"re_{uuid4().hex[:8]}",
        email=f"re_{uuid4().hex[:8]}@example.dev",
        password_hash="not-a-real-hash",
    )
    session.add(u)
    session.flush()
    session.refresh(u)
    return u


def _role_email(session, role_code: str, email: str, **kwargs) -> RoleEmail:
    re = RoleEmail(role_code=role_code, email=email, **kwargs)
    session.add(re)
    session.flush()
    session.refresh(re)
    return re


class TestBootstrapSurvival:
    """Verify bootstrap rows from seed survive the int→UUID re-key."""

    def test_bootstrap_rows_queryable_by_role_code(self, seeded_session):
        rows = seeded_session.exec(
            select(RoleEmail).where(
                RoleEmail.role_code == "IQAC_COORDINATOR",
                RoleEmail.is_deleted == False,  # noqa: E712
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].email == "iqac@example.dev"
        assert rows[0].id is not None  # UUID, not int

    def test_all_six_bootstrap_rows_present(self, seeded_session):
        rows = seeded_session.exec(
            select(RoleEmail).where(
                RoleEmail.is_deleted == False,  # noqa: E712
            )
        ).all()
        codes = {r.role_code for r in rows}
        expected = {
            "SYSTEM_ADMIN", "IQAC_COORDINATOR", "REGISTRAR",
            "DIRECTOR", "DEAN_STUDENT_WELFARE", "HOD",
        }
        assert expected.issubset(codes)


class TestCalendarEmailLookupSurvival:
    """The M4 calendar email lookup must still work after re-key."""

    def test_get_role_emails_returns_expected(self, seeded_session):
        rows = seeded_session.exec(
            select(RoleEmail).where(
                RoleEmail.role_code.in_(["IQAC_COORDINATOR"]),  # type: ignore[union-attr]
                RoleEmail.is_deleted == False,  # noqa: E712
            )
        ).all()
        emails = list({r.email for r in rows})
        assert emails == ["iqac@example.dev"]

    def test_phase3_roles_return_emails(self, seeded_session):
        phase3_codes = {"DIRECTOR", "DEAN_STUDENT_WELFARE", "HOD"}
        rows = seeded_session.exec(
            select(RoleEmail).where(
                RoleEmail.role_code.in_(phase3_codes),  # type: ignore[union-attr]
                RoleEmail.is_deleted == False,  # noqa: E712
            )
        ).all()
        emails = {r.email for r in rows}
        assert "director@example.dev" in emails
        assert "dean.sw@example.dev" in emails
        assert "hod.office@example.dev" in emails


class TestNullScopeDuplicateRejection:
    """E-004 fix: partial unique index prevents two NULL-scope rows for same role_code."""

    def test_second_null_scope_same_role_raises_unique_violation(self, db_session):
        _role_email(db_session, "TEST_ROLE", "first@example.dev")
        with pytest.raises(sa.exc.IntegrityError, match="uq_role_emails_global"):
            _role_email(db_session, "TEST_ROLE", "second@example.dev")

    def test_different_role_codes_both_null_scope_ok(self, db_session):
        _role_email(db_session, "ROLE_A", "a@example.dev")
        _role_email(db_session, "ROLE_B", "b@example.dev")


class TestScopedDuplicateRejection:
    def test_same_role_same_scope_raises(self, db_session):
        dept_id = uuid4()
        _role_email(
            db_session, "HOD", "hod1@example.dev",
            scope_type="department", scope_id=dept_id,
        )
        with pytest.raises(sa.exc.IntegrityError, match="uq_role_emails_scoped"):
            _role_email(
                db_session, "HOD", "hod2@example.dev",
                scope_type="department", scope_id=dept_id,
            )

    def test_same_role_different_scope_ok(self, db_session):
        _role_email(
            db_session, "HOD", "hod1@example.dev",
            scope_type="department", scope_id=uuid4(),
        )
        _role_email(
            db_session, "HOD", "hod2@example.dev",
            scope_type="department", scope_id=uuid4(),
        )


class TestSoftDeleteExcludedFromUnique:
    """A soft-deleted row must not block a new row with the same key."""

    def test_soft_deleted_then_recreate_succeeds(self, db_session):
        user = _user(db_session)
        repo = RoleEmailRepository(db_session)
        row = _role_email(db_session, "REUSE_ROLE", "reuse@example.dev")
        repo.soft_delete(row, user.id)
        db_session.flush()
        new_row = _role_email(db_session, "REUSE_ROLE", "reuse2@example.dev")
        assert new_row.id != row.id
