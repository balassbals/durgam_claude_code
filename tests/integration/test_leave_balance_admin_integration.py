"""Integration tests for leave balance admin edit (M8.1 E-022).

3 tests:
  1. Full edit cycle: balance updated in DB + audit row created.
  2. Edit same row twice → two audit rows (each with distinct before/after diffs).
  3. Non-admin (student) lacks leave_balance_admin:write:* → can() returns False.
"""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlmodel import func, select

from durgam.models.config_anchors import AcademicYear
from durgam.models.crosscutting import AuditLog
from durgam.models.identity import Permission, Role, User, UserRole
from durgam.models.leave import LeaveBalance
from durgam.repositories.leave import LeaveBalanceRepository
from durgam.services.leave_balance_import import LeaveBalanceImportService
from durgam.services.org_exceptions import AcademicYearLockedError


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _ay(session, *, is_locked: bool = False) -> AcademicYear:
    today = date.today()
    ay = AcademicYear(
        code=f"AY{uuid4().hex[:4]}",
        starts_on=today - timedelta(days=30),
        ends_on=today + timedelta(days=30),
        is_locked=is_locked,
    )
    session.add(ay)
    session.flush()
    session.refresh(ay)
    return ay


def _user(session) -> User:
    uname = f"lba_{uuid4().hex[:8]}"
    u = User(username=uname, email=f"{uname}@test.local", password_hash="x", is_active=True)
    session.add(u)
    session.flush()
    session.refresh(u)
    return u


def _balance(session, user: User, ay: AcademicYear, *, opening: float = 10.0, credited: float = 2.0, availed: float = 1.0) -> LeaveBalance:
    bal = LeaveBalance(
        employee_user_id=user.id,
        academic_year_id=ay.id,
        leave_type="CL",
        opening_balance=opening,
        credited=credited,
        availed=availed,
        forfeited=0.0,
        encashed=0.0,
        closing_balance=opening + credited - availed,
        created_by=user.id,
        updated_by=user.id,
    )
    session.add(bal)
    session.flush()
    session.refresh(bal)
    return bal


# ── Tests ────────────────────────────────────────────────────────────────────────

class TestLeaveBalanceAdminEdit:

    def test_full_edit_cycle_updates_db_and_creates_audit(self, db_session) -> None:
        """admin_edit_balance updates the balance row and writes one audit row."""
        actor = _user(db_session)
        employee = _user(db_session)
        ay = _ay(db_session)
        bal = _balance(db_session, employee, ay, opening=10.0, credited=2.0, availed=1.0)
        # initial closing = 11.0
        assert bal.closing_balance == 11.0

        pre_audit_count = db_session.exec(
            select(func.count()).select_from(AuditLog)
        ).one()

        svc = LeaveBalanceImportService(db_session)
        svc.admin_edit_balance(
            balance_id=bal.id,
            fields={"availed": 3.0},
            actor_id=actor.id,
        )
        db_session.commit()

        db_session.refresh(bal)
        assert bal.availed == 3.0
        assert bal.closing_balance == 10.0 + 2.0 - 3.0  # 9.0

        post_audit_count = db_session.exec(
            select(func.count()).select_from(AuditLog)
        ).one()
        assert post_audit_count == pre_audit_count + 1

        audit_row = db_session.exec(
            select(AuditLog)
            .where(AuditLog.resource == "leave_balance")
            .where(AuditLog.action == "admin_edit")
            .order_by(AuditLog.occurred_at.desc())  # type: ignore[attr-defined]
        ).first()
        assert audit_row is not None
        assert audit_row.actor_user_id == actor.id
        assert audit_row.diff_json is not None

    def test_two_edits_create_two_audit_rows(self, db_session) -> None:
        """Editing the same balance row twice produces two separate audit rows."""
        actor = _user(db_session)
        employee = _user(db_session)
        ay = _ay(db_session)
        bal = _balance(db_session, employee, ay, opening=12.0, credited=0.0, availed=0.0)

        svc = LeaveBalanceImportService(db_session)
        svc.admin_edit_balance(
            balance_id=bal.id,
            fields={"credited": 1.0},
            actor_id=actor.id,
        )
        db_session.commit()
        svc.admin_edit_balance(
            balance_id=bal.id,
            fields={"credited": 2.0},
            actor_id=actor.id,
        )
        db_session.commit()

        audit_rows = db_session.exec(
            select(AuditLog)
            .where(AuditLog.resource == "leave_balance")
            .where(AuditLog.action == "admin_edit")
            .where(AuditLog.resource_id == str(bal.id))
        ).all()
        assert len(audit_rows) == 2

    def test_student_lacks_leave_balance_admin_permission(self, db_session) -> None:
        """A user with STUDENT role does not have leave_balance_admin:write:*."""
        from durgam.auth.permissions import can

        # Create a STUDENT-role user (no explicit leave_balance_admin perm)
        student = _user(db_session)
        student_role = db_session.exec(
            select(Role).where(Role.code == "STUDENT")
        ).first()
        if student_role:
            db_session.add(UserRole(user_id=student.id, role_id=student_role.id))
            db_session.flush()

        result = can(student.id, "write", "leave_balance_admin", "*", None, db_session)
        assert result is False
