"""Integration tests for M9 Phase 10.2 — scope-aware composer label + IST formatting.

5 tests:
1. DEAN role with campus scope → "Dean, <campus_name>"
2. HOD role with department scope → "Head of Department, <dept_name>"
3. FINANCE_OFFICER with no scope → "Finance Officer"
4. DEAN_STUDENT_WELFARE with no scope → "Dean of Student Welfare"
5. format_ist formats a UTC datetime correctly with Asia/Kolkata offset + "IST" label
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlmodel import Session

from durgam.models.campus import Campus
from durgam.models.department import Department
from durgam.models.identity import Role, User, UserRole
from durgam.models.school import School
from durgam.services.announcement import _resolve_composer_scope_label
from durgam.services.password import hash_password
from durgam.utils.ist_format import format_ist


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _user(session: Session) -> User:
    tag = uuid4().hex[:8]
    u = User(
        username=f"lbl_{tag}",
        email=f"lbl_{tag}@test.local",
        full_name="Label Test",
        password_hash=hash_password("Test_Dev1!XZ"),
        is_active=True,
    )
    session.add(u)
    session.flush()
    return u


def _role(session: Session, code: str, name: str) -> Role:
    from sqlmodel import select
    existing = session.exec(select(Role).where(Role.code == code)).first()
    if existing:
        return existing
    r = Role(code=code, name=name, level=50)
    session.add(r)
    session.flush()
    return r


def _assign_role(
    session: Session,
    user_id,
    role_id,
    scope_type: str | None = None,
    scope_id=None,
) -> None:
    ur = UserRole(
        user_id=user_id,
        role_id=role_id,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    session.add(ur)
    session.flush()


def _campus(session: Session, code: str, name: str) -> Campus:
    c = Campus(code=code, name=name)
    session.add(c)
    session.flush()
    return c


def _school(session: Session, code: str, name: str) -> School:
    from sqlmodel import select as _select
    existing = session.exec(_select(School).where(School.code == code)).first()
    if existing:
        return existing
    s = School(code=code, name=name)
    session.add(s)
    session.flush()
    return s


def _dept(session: Session, code: str, name: str, campus_id, school_id) -> Department:
    d = Department(code=code, name=name, main_campus_id=campus_id, school_id=school_id)
    session.add(d)
    session.flush()
    return d


# ---------------------------------------------------------------------------
# Test 1: DEAN with campus scope → "Dean, <campus_name>"
# ---------------------------------------------------------------------------

class TestComposerScopeLabelResolution:

    def test_resolve_composer_label_for_dean_with_campus_scope(
        self, db_session: Session
    ) -> None:
        """User with DEAN role bound to a campus scope → 'Dean, <campus name>'."""
        campus = _campus(db_session, "TST_CAM", "Test Campus")
        dean_role = _role(db_session, "DEAN_TST", "Dean")
        user = _user(db_session)
        _assign_role(db_session, user.id, dean_role.id,
                     scope_type="campus", scope_id=campus.id)

        label = _resolve_composer_scope_label(user.id, "DEAN_TST", db_session)

        assert label == f"Dean, {campus.name}", (
            f"Expected 'Dean, {campus.name}' but got '{label}'"
        )

    def test_resolve_composer_label_for_hod_with_department_scope(
        self, db_session: Session
    ) -> None:
        """User with HOD role bound to a department → 'Head of Department, <dept name>'."""
        campus = _campus(db_session, "TST_CAM2", "Test Campus 2")
        school = _school(db_session, "TST_SCH", "Test School")
        dept = _dept(db_session, "TST_DEPT", "Test Department", campus.id, school.id)
        hod_role = _role(db_session, "HOD_TST", "Head of Department")
        user = _user(db_session)
        _assign_role(db_session, user.id, hod_role.id,
                     scope_type="department", scope_id=dept.id)

        label = _resolve_composer_scope_label(user.id, "HOD_TST", db_session)

        assert label == f"Head of Department, {dept.name}", (
            f"Expected 'Head of Department, {dept.name}' but got '{label}'"
        )

    def test_resolve_composer_label_for_finance_officer_no_scope(
        self, db_session: Session
    ) -> None:
        """User with FINANCE_OFFICER role (no scope) → just 'Finance Officer'."""
        fin_role = _role(db_session, "FIN_OFF_TST", "Finance Officer")
        user = _user(db_session)
        _assign_role(db_session, user.id, fin_role.id)

        label = _resolve_composer_scope_label(user.id, "FIN_OFF_TST", db_session)

        assert label == "Finance Officer", (
            f"Expected 'Finance Officer' but got '{label}'"
        )

    def test_resolve_composer_label_for_dean_student_welfare(
        self, db_session: Session
    ) -> None:
        """DEAN_STUDENT_WELFARE has no scope restriction; label is just the role name."""
        dsw_role = _role(db_session, "DSW_TST", "Dean of Student Welfare")
        user = _user(db_session)
        _assign_role(db_session, user.id, dsw_role.id)

        label = _resolve_composer_scope_label(user.id, "DSW_TST", db_session)

        assert label == "Dean of Student Welfare", (
            f"Expected 'Dean of Student Welfare' but got '{label}'"
        )


# ---------------------------------------------------------------------------
# Test 5: IST formatter
# ---------------------------------------------------------------------------

class TestFormatIst:

    def test_format_ist_uses_asia_kolkata_offset_and_label(self) -> None:
        """2026-01-01 00:00 UTC → 2026-01-01 05:30 IST (UTC+5:30)."""
        utc_dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        result = format_ist(utc_dt)

        assert "IST" in result, f"Expected 'IST' in output but got: {result!r}"
        # 00:00 UTC → 05:30 IST
        assert "5:30" in result, (
            f"Expected 05:30 AM IST offset but got: {result!r}"
        )
        assert "Jan 2026" in result or "1 Jan 2026" in result, (
            f"Expected Jan 2026 in output but got: {result!r}"
        )
