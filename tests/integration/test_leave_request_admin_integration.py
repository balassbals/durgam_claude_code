"""Integration tests for Phase 8 leave request admin features (M8.1 E-022).

5 tests:
  1. Admin cancel submitted request: state changes + audit row written.
  2. Forbidden admin transition (rejected→approved) raises LeaveRequestError.
  3. is_post_facto flag persists in DB when set on a LeaveRequest row.
  4. _reverse_cl_forfeitures_for_postfacto reverses forfeiture in DB.
  5. Non-CL leave type is a no-op for _reverse_cl_forfeitures_for_postfacto.

All tests use db_session (clean DB, rollback per test).
Pattern matches test_leave_request_integration.py.
"""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlmodel import func, select

from durgam.models.config_anchors import AcademicYear
from durgam.models.crosscutting import ApprovalProcess, ApprovalRequest, AuditLog
from durgam.models.identity import Role, User, UserRole
from durgam.models.leave import LateAttendanceMarker, LeaveBalance, LeaveRequest
from durgam.repositories.leave import (
    LeaveBalanceRepository,
    LeaveSanctionRuleRepository,
    LeaveRepository,
)
from durgam.services.approval_request import ApprovalRequestService
from durgam.services.leave_request import LeaveRequestError, LeaveRequestService


# ── Shared inline helpers ──────────────────────────────────────────────────


def _user(session) -> User:
    from durgam.services.password import hash_password
    u = User(
        username=f"lra_{uuid4().hex[:8]}",
        email=f"lra_{uuid4().hex[:8]}@test.local",
        full_name="Leave Req Admin Test",
        password_hash=hash_password("Test_Pass1!XZ"),
        is_active=True,
    )
    session.add(u)
    session.flush()
    session.refresh(u)
    return u


def _role(session, code: str) -> Role:
    r = Role(code=code, name=f"Test {code}", level=10)
    session.add(r)
    session.flush()
    session.refresh(r)
    return r


def _assign_role(session, user: User, role: Role) -> None:
    ur = UserRole(user_id=user.id, role_id=role.id)
    session.add(ur)
    session.flush()


def _ay(session) -> AcademicYear:
    ay = AcademicYear(
        code=f"AY{uuid4().hex[:4]}",
        starts_on=date(2026, 1, 1),
        ends_on=date(2026, 12, 31),
        is_locked=False,
    )
    session.add(ay)
    session.flush()
    session.refresh(ay)
    return ay


def _process(session) -> ApprovalProcess:
    proc = ApprovalProcess(
        code=f"LRA_TEST_{uuid4().hex[:6]}",
        title="LRA Test Process",
        requestor_role_codes=[],
        channel_role_codes=None,
        requires_upward_attachments=False,
        max_upward_attachments=0,
        requires_downward_attachments=False,
        max_downward_attachments=0,
        is_finance=False,
    )
    session.add(proc)
    session.flush()
    session.refresh(proc)
    return proc


def _approval_request(session, process: ApprovalProcess, requestor: User, state: str = "submitted") -> ApprovalRequest:
    ar = ApprovalRequest(
        process_id=process.id,
        requestor_user_id=requestor.id,
        title=f"Test Leave Request {uuid4().hex[:6]}",
        state=state,
    )
    session.add(ar)
    session.flush()
    session.refresh(ar)
    return ar


def _leave_request(
    session,
    requestor: User,
    ay: AcademicYear,
    approval_req: ApprovalRequest,
    *,
    leave_type: str = "EL",
    state: str = "submitted",
    is_post_facto: bool = False,
    starts_on: date | None = None,
    ends_on: date | None = None,
) -> LeaveRequest:
    s = starts_on or (date.today() + timedelta(days=5))
    e = ends_on or (date.today() + timedelta(days=7))
    lr = LeaveRequest(
        requestor_user_id=requestor.id,
        academic_year_id=ay.id,
        leave_type=leave_type,
        starts_on=s,
        ends_on=e,
        chargeable_days=3.0,
        sanctioned_days=3.0,
        reason="Integration test leave request",
        state=state,
        half_day=False,
        approval_request_id=approval_req.id,
        is_post_facto=is_post_facto,
    )
    session.add(lr)
    session.flush()
    session.refresh(lr)
    return lr


def _svc(session) -> LeaveRequestService:
    return LeaveRequestService(
        session=session,
        leave_repo=LeaveRepository(session),
        balance_repo=LeaveBalanceRepository(session),
        rule_repo=LeaveSanctionRuleRepository(session),
        approval_service=ApprovalRequestService(session),
    )


def _audit_row_count(session, resource: str, resource_id: str) -> int:
    return session.exec(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.resource == resource,
            AuditLog.resource_id == resource_id,
        )
    ).one()


# ── Test 1: Admin cancel submitted request ─────────────────────────────────


def test_admin_cancel_submitted_request(db_session) -> None:
    """admin_change_state submitted→cancelled updates state and writes audit row."""
    requestor = _user(db_session)
    admin = _user(db_session)
    sysadmin_role = _role(db_session, "SYSTEM_ADMIN")
    _assign_role(db_session, admin, sysadmin_role)

    ay = _ay(db_session)
    proc = _process(db_session)
    approval_req = _approval_request(db_session, proc, requestor, state="submitted")
    leave_req = _leave_request(db_session, requestor, ay, approval_req, state="submitted")
    db_session.flush()

    svc = _svc(db_session)
    result = svc.admin_change_state(
        leave_request_id=leave_req.id,
        new_state="cancelled",
        actor_user_id=admin.id,
        reason="Integration test: admin cancel",
    )
    db_session.flush()

    # State should be cancelled
    db_session.refresh(leave_req)
    assert leave_req.state == "cancelled", f"Expected 'cancelled', got '{leave_req.state}'"

    # Audit row written
    count = _audit_row_count(db_session, "leave_request", str(leave_req.id))
    assert count >= 1, f"Expected ≥1 audit row; got {count}"


# ── Test 2: Forbidden transition raises LeaveRequestError ─────────────────


def test_forbidden_transition_raises_leave_request_error(db_session) -> None:
    """admin_change_state rejected→approved raises LeaveRequestError (not allowed)."""
    requestor = _user(db_session)
    admin = _user(db_session)
    sysadmin_role = _role(db_session, "SYSTEM_ADMIN")
    _assign_role(db_session, admin, sysadmin_role)

    ay = _ay(db_session)
    proc = _process(db_session)
    approval_req = _approval_request(db_session, proc, requestor, state="cancelled")
    leave_req = _leave_request(db_session, requestor, ay, approval_req, state="rejected")
    db_session.flush()

    svc = _svc(db_session)
    with pytest.raises(LeaveRequestError, match="not allowed"):
        svc.admin_change_state(
            leave_request_id=leave_req.id,
            new_state="approved",
            actor_user_id=admin.id,
            reason="should be blocked",
        )


# ── Test 3: is_post_facto flag persists in DB ──────────────────────────────


def test_is_post_facto_flag_persisted_in_db(db_session) -> None:
    """LeaveRequest.is_post_facto=True is stored and retrieved correctly."""
    requestor = _user(db_session)
    ay = _ay(db_session)
    proc = _process(db_session)
    approval_req = _approval_request(db_session, proc, requestor, state="submitted")
    leave_req = _leave_request(
        db_session,
        requestor,
        ay,
        approval_req,
        is_post_facto=True,
        starts_on=date.today() - timedelta(days=10),
        ends_on=date.today() - timedelta(days=8),
    )
    db_session.flush()

    # Retrieve from session cache (verifies field is mapped)
    db_session.refresh(leave_req)
    assert leave_req.is_post_facto is True, "is_post_facto should be True after flush/refresh"

    # Verify default is False for a non-past-dated request
    proc2 = _process(db_session)
    approval_req2 = _approval_request(db_session, proc2, requestor, state="submitted")
    future_req = _leave_request(
        db_session,
        requestor,
        ay,
        approval_req2,
        is_post_facto=False,
    )
    db_session.flush()
    db_session.refresh(future_req)
    assert future_req.is_post_facto is False, "is_post_facto should default to False"


# ── Test 4: _reverse_cl_forfeitures_for_postfacto modifies DB ─────────────


def test_reverse_cl_forfeiture_with_real_db(db_session) -> None:
    """Calling _reverse_cl_forfeitures_for_postfacto reverses one forfeited CL month."""
    employee = _user(db_session)
    ay = _ay(db_session)

    # Insert a CL balance with one forfeited month "2026-05"
    target_month = "2026-05"
    balance = LeaveBalance(
        employee_user_id=employee.id,
        academic_year_id=ay.id,
        leave_type="CL",
        opening_balance=12.0,
        credited=0.0,
        availed=0.0,
        forfeited=1.0,
        encashed=0.0,
        closing_balance=11.0,
        forfeiture_applied_for=[target_month],
        created_by=employee.id,
        updated_by=employee.id,
    )
    db_session.add(balance)
    db_session.flush()

    # Insert a LateAttendanceMarker in that month
    marker = LateAttendanceMarker(
        employee_user_id=employee.id,
        occurred_on=date(2026, 5, 15),
        recorded_by=employee.id,
    )
    db_session.add(marker)
    db_session.flush()

    # Build a minimal post-facto CL LeaveRequest covering that month
    proc = _process(db_session)
    approval_req = _approval_request(db_session, proc, employee, state="approved")
    leave_req = _leave_request(
        db_session,
        employee,
        ay,
        approval_req,
        leave_type="CL",
        state="approved",
        is_post_facto=True,
        starts_on=date(2026, 5, 10),
        ends_on=date(2026, 5, 20),
    )
    db_session.flush()

    # Call reversal
    LeaveRequestService._reverse_cl_forfeitures_for_postfacto(db_session, leave_req)
    db_session.flush()

    # Verify forfeiture was reversed
    db_session.refresh(balance)
    assert balance.forfeited == 0.0, f"Expected forfeited=0.0; got {balance.forfeited}"
    assert target_month not in (balance.forfeiture_applied_for or []), (
        f"Expected {target_month} removed from forfeiture_applied_for; "
        f"got {balance.forfeiture_applied_for}"
    )

    # Audit row written for the reversal
    count = _audit_row_count(db_session, "leave_balance", str(balance.id))
    assert count >= 1, f"Expected ≥1 audit row for the reversal; got {count}"


# ── Test 5: Non-CL leave type is a no-op ──────────────────────────────────


def test_non_cl_reverse_forfeiture_is_noop(db_session) -> None:
    """_reverse_cl_forfeitures_for_postfacto is a no-op for non-CL leave types."""
    employee = _user(db_session)
    ay = _ay(db_session)

    # EL balance with a forfeited entry (should not be touched)
    balance = LeaveBalance(
        employee_user_id=employee.id,
        academic_year_id=ay.id,
        leave_type="EL",
        opening_balance=10.0,
        credited=0.0,
        availed=0.0,
        forfeited=1.0,
        encashed=0.0,
        closing_balance=9.0,
        forfeiture_applied_for=["2026-05"],
        created_by=employee.id,
        updated_by=employee.id,
    )
    db_session.add(balance)
    db_session.flush()

    proc = _process(db_session)
    approval_req = _approval_request(db_session, proc, employee, state="approved")
    leave_req = _leave_request(
        db_session,
        employee,
        ay,
        approval_req,
        leave_type="EL",  # ← not CL
        state="approved",
        is_post_facto=True,
        starts_on=date(2026, 5, 10),
        ends_on=date(2026, 5, 20),
    )
    db_session.flush()

    before_forfeited = balance.forfeited

    LeaveRequestService._reverse_cl_forfeitures_for_postfacto(db_session, leave_req)
    db_session.flush()

    db_session.refresh(balance)
    assert balance.forfeited == before_forfeited, (
        f"Non-CL type: forfeited must remain unchanged; "
        f"expected {before_forfeited}, got {balance.forfeited}"
    )
    # No audit rows from the reversal
    count = _audit_row_count(db_session, "leave_balance", str(balance.id))
    assert count == 0, f"Non-CL type: expected 0 audit rows; got {count}"
