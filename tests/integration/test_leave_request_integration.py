"""Integration tests for LeaveRequestService + ApprovalRequestService (M8 engine extension).

All tests use db_session (clean DB, rollback per test) with all entities created inline.
No seeded_session — avoids session-pollution and seeded_db_engine initialization.

Pattern matches test_nrf_approve_flow.py exactly.
"""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlmodel import select

from durgam.models.campus import Campus
from durgam.models.config_anchors import AcademicYear, NonRegularFaculty
from durgam.models.crosscutting import ApprovalProcess, ApprovalRequest
from durgam.models.department import Department
from durgam.models.identity import Role, User, UserRole
from durgam.models.leave import LeaveBalance, LeaveSanctionAuthorityRule, LeaveRequest
from durgam.models.school import School
from durgam.repositories.leave import (
    LeaveBalanceRepository,
    LeaveSanctionRuleRepository,
    LeaveRepository,
)
from durgam.services.approval_request import ApprovalRequestService
from durgam.services.leave_request import LeaveRequestError, LeaveRequestService


# ---------------------------------------------------------------------------
# Shared helpers (same pattern as test_nrf_approve_flow.py)
# ---------------------------------------------------------------------------

def _user(session, *, username=None, joined_on=None, employee_type="regular_teaching") -> User:
    from durgam.services.password import hash_password
    u = User(
        username=username or f"t{uuid4().hex[:8]}",
        email=f"t{uuid4().hex[:8]}@test.local",
        full_name="Test User",
        password_hash=hash_password("Test_Pass1!XZ"),
        joined_on=joined_on or date(2018, 1, 1),
        employee_type=employee_type,
        is_active=True,
    )
    session.add(u)
    session.flush()
    session.refresh(u)
    return u


def _role(session, code: str) -> Role:
    r = Role(code=code, name=f"Test {code}", level=50)
    session.add(r)
    session.flush()
    session.refresh(r)
    return r


def _assign_role(session, user: User, role: Role, *, scope_type=None, scope_id=None) -> None:
    ur = UserRole(
        user_id=user.id,
        role_id=role.id,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    session.add(ur)
    session.flush()


def _campus(session) -> Campus:
    c = Campus(code=f"C{uuid4().hex[:4]}", name="Test Campus", address="Addr")
    session.add(c)
    session.flush()
    session.refresh(c)
    return c


def _school(session) -> School:
    s = School(code=f"S{uuid4().hex[:4]}", name="Test School")
    session.add(s)
    session.flush()
    session.refresh(s)
    return s


def _dept(session, school: School, campus: Campus) -> Department:
    d = Department(
        code=f"D{uuid4().hex[:4]}",
        name="Test Dept",
        school_id=school.id,
        main_campus_id=campus.id,
    )
    session.add(d)
    session.flush()
    session.refresh(d)
    return d


def _ay(session) -> AcademicYear:
    ay = AcademicYear(
        code=f"AY{uuid4().hex[:4]}",
        starts_on=date(2026, 6, 1),
        ends_on=date(2027, 5, 31),
        is_locked=False,
    )
    session.add(ay)
    session.flush()
    session.refresh(ay)
    return ay


def _leave_process(session) -> ApprovalProcess:
    proc = ApprovalProcess(
        code="LEAVE_APPROVAL",
        title="Leave Approval",
        requestor_role_codes=[],       # empty = no role restriction on requestor
        channel_role_codes=None,       # M8 path: channel comes from resolved_channel_json
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


def _rule(
    session,
    *,
    leave_type: str,
    applicant_role_code: str,
    sanctioner_role_code: str,
    recommend_via_role_code: str | None = None,
    requires_in_charge: bool = False,
    priority: int = 10,
) -> LeaveSanctionAuthorityRule:
    r = LeaveSanctionAuthorityRule(
        leave_type=leave_type,
        applicant_role_code=applicant_role_code,
        sanctioner_role_code=sanctioner_role_code,
        recommend_via_role_code=recommend_via_role_code,
        requires_in_charge=requires_in_charge,
        priority=priority,
    )
    session.add(r)
    session.flush()
    session.refresh(r)
    return r


def _balance(
    session,
    user_id,
    ay_id,
    leave_type: str,
    opening_balance: float = 15.0,
) -> LeaveBalance:
    """Pre-seed a leave balance so check_balance doesn't reject the request."""
    b = LeaveBalance(
        employee_user_id=user_id,
        leave_type=leave_type,
        academic_year_id=ay_id,
        opening_balance=opening_balance,
        closing_balance=opening_balance,
    )
    session.add(b)
    session.flush()
    session.refresh(b)
    return b


def _svc(session) -> LeaveRequestService:
    """Return a wired LeaveRequestService using real repos and approval engine."""
    return LeaveRequestService(
        session=session,
        leave_repo=LeaveRepository(session),
        balance_repo=LeaveBalanceRepository(session),
        rule_repo=LeaveSanctionRuleRepository(session),
        approval_service=ApprovalRequestService(session),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLeaveRequestIntegration:

    def test_submit_cl_faculty_creates_approval_request_with_director_channel(
        self, db_session
    ):
        """Submitting CL for FACULTY creates an ApprovalRequest with resolved_channel_json
        containing a single DIRECTOR terminal stage.
        """
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        ay = _ay(db_session)
        process = _leave_process(db_session)

        faculty_role = _role(db_session, "FACULTY")
        director_role = _role(db_session, "DIRECTOR")

        requestor = _user(db_session)
        director_user = _user(db_session)
        _assign_role(db_session, requestor, faculty_role, scope_type="department", scope_id=dept.id)
        _assign_role(db_session, director_user, director_role, scope_type="department", scope_id=dept.id)

        _rule(db_session, leave_type="CL", applicant_role_code="FACULTY",
              sanctioner_role_code="DIRECTOR")
        _balance(db_session, requestor.id, ay.id, "CL")

        result = _svc(db_session).submit(
            requestor_user_id=requestor.id,
            leave_type="CL",
            starts_on=date(2026, 7, 1),
            ends_on=date(2026, 7, 2),
            academic_year_id=ay.id,
            reason="Personal",
        )

        assert result.id is not None
        assert result.leave_type == "CL"
        assert result.state == "submitted"
        assert result.approval_request_id is not None

        # Verify the ApprovalRequest was created with resolved_channel_json
        ar = db_session.get(ApprovalRequest, result.approval_request_id)
        assert ar is not None
        assert ar.resolved_channel_json is not None
        assert len(ar.resolved_channel_json) == 1
        assert ar.resolved_channel_json[0]["role_code"] == "DIRECTOR"
        assert ar.resolved_channel_json[0]["recommend_only"] is False

        # Verify payload carries leave_request_id
        assert ar.payload_json.get("leave_request_id") == str(result.id)

    def test_approve_through_terminal_debits_balance(self, db_session):
        """Terminal approval of CL debits the CL balance by chargeable_days."""
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        ay = _ay(db_session)
        _leave_process(db_session)

        faculty_role = _role(db_session, "FACULTY")
        director_role = _role(db_session, "DIRECTOR")

        requestor = _user(db_session)
        director_user = _user(db_session)
        _assign_role(db_session, requestor, faculty_role, scope_type="department", scope_id=dept.id)
        _assign_role(db_session, director_user, director_role, scope_type="department", scope_id=dept.id)
        _rule(db_session, leave_type="CL", applicant_role_code="FACULTY",
              sanctioner_role_code="DIRECTOR")
        _balance(db_session, requestor.id, ay.id, "CL")

        svc = _svc(db_session)
        leave_req = svc.submit(
            requestor_user_id=requestor.id,
            leave_type="CL",
            starts_on=date(2026, 7, 1),
            ends_on=date(2026, 7, 2),
            academic_year_id=ay.id,
            reason="Personal",
        )
        chargeable_days = leave_req.chargeable_days

        approval_svc = ApprovalRequestService(db_session)
        approval_svc.approve(
            request_id=leave_req.approval_request_id,
            approver_user_id=director_user.id,
            comment="Approved",
        )

        # leave_request.state must now be "approved"
        db_session.refresh(leave_req)
        assert leave_req.state == "approved"
        assert leave_req.sanctioned_days == chargeable_days

        # CL balance.availed must equal chargeable_days
        balance = db_session.exec(
            select(LeaveBalance).where(
                LeaveBalance.employee_user_id == requestor.id,
                LeaveBalance.leave_type == "CL",
                LeaveBalance.academic_year_id == ay.id,
            )
        ).first()
        assert balance is not None
        assert balance.availed == chargeable_days

    def test_cml_terminal_debits_hpl_balance_at_2x(self, db_session):
        """Terminal approval of CML debits HPL balance at 2× chargeable_days (§11.6.d)."""
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        ay = _ay(db_session)
        _leave_process(db_session)

        faculty_role = _role(db_session, "FACULTY")
        director_role = _role(db_session, "DIRECTOR")

        requestor = _user(db_session)
        director_user = _user(db_session)
        _assign_role(db_session, requestor, faculty_role, scope_type="department", scope_id=dept.id)
        _assign_role(db_session, director_user, director_role, scope_type="department", scope_id=dept.id)
        _rule(db_session, leave_type="CML", applicant_role_code="FACULTY",
              sanctioner_role_code="DIRECTOR")

        # Pre-seed HPL balance. CML debits HPL at 2× so closing must be ≥ 2× chargeable_days.
        hpl_balance = LeaveBalance(
            employee_user_id=requestor.id,
            leave_type="HPL",
            academic_year_id=ay.id,
            opening_balance=20.0,
            closing_balance=20.0,  # must be set; default is 0.0
        )
        db_session.add(hpl_balance)
        db_session.flush()

        svc = _svc(db_session)
        leave_req = svc.submit(
            requestor_user_id=requestor.id,
            leave_type="CML",
            starts_on=date(2026, 7, 1),
            ends_on=date(2026, 7, 2),
            academic_year_id=ay.id,
            reason="Medical",
            has_medical_cert=True,
        )
        chargeable_days = leave_req.chargeable_days

        approval_svc = ApprovalRequestService(db_session)
        approval_svc.approve(
            request_id=leave_req.approval_request_id,
            approver_user_id=director_user.id,
            comment="Approved",
        )

        db_session.refresh(leave_req)
        assert leave_req.state == "approved"

        db_session.refresh(hpl_balance)
        # CML debits HPL at 2×
        assert hpl_balance.availed == chargeable_days * 2.0

    def test_reject_at_stage_1_sets_leave_rejected_no_balance_change(self, db_session):
        """Rejection at stage 1 sets leave_request.state='rejected', no balance debited."""
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        ay = _ay(db_session)
        _leave_process(db_session)

        faculty_role = _role(db_session, "FACULTY")
        director_role = _role(db_session, "DIRECTOR")

        requestor = _user(db_session)
        director_user = _user(db_session)
        _assign_role(db_session, requestor, faculty_role, scope_type="department", scope_id=dept.id)
        _assign_role(db_session, director_user, director_role, scope_type="department", scope_id=dept.id)
        _rule(db_session, leave_type="CL", applicant_role_code="FACULTY",
              sanctioner_role_code="DIRECTOR")
        _balance(db_session, requestor.id, ay.id, "CL")

        svc = _svc(db_session)
        leave_req = svc.submit(
            requestor_user_id=requestor.id,
            leave_type="CL",
            starts_on=date(2026, 7, 1),
            ends_on=date(2026, 7, 2),
            academic_year_id=ay.id,
            reason="Personal",
        )

        approval_svc = ApprovalRequestService(db_session)
        approval_svc.reject(
            request_id=leave_req.approval_request_id,
            approver_user_id=director_user.id,
            comment="Not approved",
        )

        db_session.refresh(leave_req)
        assert leave_req.state == "rejected"

        # No CL balance should have been debited
        balance = db_session.exec(
            select(LeaveBalance).where(
                LeaveBalance.employee_user_id == requestor.id,
                LeaveBalance.leave_type == "CL",
                LeaveBalance.academic_year_id == ay.id,
            )
        ).first()
        # Either no balance row, or availed == 0
        assert balance is None or balance.availed == 0.0

    def test_scl_director_recommends_then_vc_approves(self, db_session):
        """SCL 2-stage: DIRECTOR recommends (leave stays in_review), VC approves (leave approved)."""
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        ay = _ay(db_session)
        _leave_process(db_session)

        faculty_role = _role(db_session, "FACULTY")
        director_role = _role(db_session, "DIRECTOR")
        vc_role = _role(db_session, "VC")

        requestor = _user(db_session)
        director_user = _user(db_session)
        vc_user = _user(db_session)
        _assign_role(db_session, requestor, faculty_role, scope_type="department", scope_id=dept.id)
        _assign_role(db_session, director_user, director_role, scope_type="department", scope_id=dept.id)
        _assign_role(db_session, vc_user, vc_role)  # universitywide (no scope)

        # SCL rule: DIRECTOR recommends, VC is terminal sanctioner
        _rule(db_session, leave_type="SCL", applicant_role_code="FACULTY",
              sanctioner_role_code="VC", recommend_via_role_code="DIRECTOR")
        _balance(db_session, requestor.id, ay.id, "SCL")

        svc = _svc(db_session)
        leave_req = svc.submit(
            requestor_user_id=requestor.id,
            leave_type="SCL",
            starts_on=date(2026, 7, 1),
            ends_on=date(2026, 7, 5),
            academic_year_id=ay.id,
            reason="Special casual",
        )
        chargeable_days = leave_req.chargeable_days

        # Verify channel has 2 stages: DIRECTOR (recommend_only) → VC (terminal)
        ar = db_session.get(ApprovalRequest, leave_req.approval_request_id)
        assert len(ar.resolved_channel_json) == 2
        assert ar.resolved_channel_json[0]["recommend_only"] is True
        assert ar.resolved_channel_json[0]["role_code"] == "DIRECTOR"
        assert ar.resolved_channel_json[1]["recommend_only"] is False
        assert ar.resolved_channel_json[1]["role_code"] == "VC"

        approval_svc = ApprovalRequestService(db_session)

        # Stage 1: DIRECTOR recommends — request stays in_review, leave NOT approved
        approval_svc.approve(
            request_id=leave_req.approval_request_id,
            approver_user_id=director_user.id,
            comment="Recommend",
        )
        db_session.refresh(leave_req)
        assert leave_req.state == "submitted"  # not yet approved; callback not triggered

        # Stage 2: VC approves — request is terminal, leave approved, balance debited
        approval_svc.approve(
            request_id=leave_req.approval_request_id,
            approver_user_id=vc_user.id,
            comment="Approved",
        )
        db_session.refresh(leave_req)
        assert leave_req.state == "approved"

        # SCL balance debited (not EOL/SL)
        balance = db_session.exec(
            select(LeaveBalance).where(
                LeaveBalance.employee_user_id == requestor.id,
                LeaveBalance.leave_type == "SCL",
                LeaveBalance.academic_year_id == ay.id,
            )
        ).first()
        assert balance is not None
        assert balance.availed == chargeable_days

    def test_skip_self_director_own_leave(self, db_session):
        """When the requestor is the sole DIRECTOR at their scope, stage is auto-skipped.

        Requestor holds FACULTY + DIRECTOR roles. CL goes via DIRECTOR (terminal).
        Since the requestor IS the DIRECTOR, the stage is skipped → auto-approved.
        """
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        ay = _ay(db_session)
        _leave_process(db_session)

        faculty_role = _role(db_session, "FACULTY")
        director_role = _role(db_session, "DIRECTOR")

        # Requestor is both FACULTY (scoped to dept) and DIRECTOR (scoped to dept)
        requestor = _user(db_session)
        _assign_role(db_session, requestor, faculty_role, scope_type="department", scope_id=dept.id)
        _assign_role(db_session, requestor, director_role, scope_type="department", scope_id=dept.id)

        _rule(db_session, leave_type="CL", applicant_role_code="FACULTY",
              sanctioner_role_code="DIRECTOR")
        _balance(db_session, requestor.id, ay.id, "CL")

        svc = _svc(db_session)
        leave_req = svc.submit(
            requestor_user_id=requestor.id,
            leave_type="CL",
            starts_on=date(2026, 7, 1),
            ends_on=date(2026, 7, 2),
            academic_year_id=ay.id,
            reason="Personal",
        )

        # The single-stage DIRECTOR channel was auto-skipped — request immediately approved
        ar = db_session.get(ApprovalRequest, leave_req.approval_request_id)
        assert ar.state == "approved"

        db_session.refresh(leave_req)
        assert leave_req.state == "approved"

        # Balance must have been debited
        chargeable_days = leave_req.chargeable_days
        balance = db_session.exec(
            select(LeaveBalance).where(
                LeaveBalance.employee_user_id == requestor.id,
                LeaveBalance.leave_type == "CL",
                LeaveBalance.academic_year_id == ay.id,
            )
        ).first()
        assert balance is not None
        assert balance.availed == chargeable_days

    def test_nrf_approval_unaffected_by_engine_extension(self, db_session):
        """NRF_APPROVAL (M7, no resolved_channel) still routes and creates NRF record.

        Regression test: confirms M7 path in _resolve_approvers / approve() is intact.
        """
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)

        requestor = _user(db_session)
        approver = _user(db_session)

        hod_role = _role(db_session, "HOD")
        dean_role = _role(db_session, "DEAN")
        _assign_role(db_session, requestor, hod_role, scope_type="department", scope_id=dept.id)
        _assign_role(db_session, approver, dean_role)

        proc = ApprovalProcess(
            code="NRF_APPROVAL",
            title="NRF Approval",
            requestor_role_codes=["HOD"],
            channel_role_codes=["DEAN"],
            requires_upward_attachments=False,
            max_upward_attachments=5,
            requires_downward_attachments=False,
            max_downward_attachments=3,
            is_finance=False,
        )
        db_session.add(proc)
        db_session.flush()
        db_session.refresh(proc)

        svc = ApprovalRequestService(db_session)
        payload = {
            "description": "NRF regression test",
            "nrf_data": {
                "department_id": str(dept.id),
                "name": "Dr. Regression",
                "designation": "Professor",
                "organization": "Test Org",
                "expertise": "Testing",
                "available_from": "2026-07-01",
                "available_to": "2026-12-31",
                "non_regular_type": "visiting",
            },
        }

        request = svc.submit(
            process_id=proc.id,
            requestor_user_id=requestor.id,
            title="NRF Regression Test",
            payload=payload,
        )
        assert request.state == "submitted"
        assert request.resolved_channel_json is None  # M7 path: no resolved_channel

        result = svc.approve(
            request_id=request.id,
            approver_user_id=approver.id,
            comment="Approved",
        )
        assert result.state == "approved"

        nrf = db_session.exec(
            select(NonRegularFaculty).where(
                NonRegularFaculty.approval_request_id == request.id
            )
        ).first()
        assert nrf is not None
        assert nrf.name == "Dr. Regression"
        assert nrf.is_admin_approved is True
