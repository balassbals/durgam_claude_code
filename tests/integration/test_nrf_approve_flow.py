"""Integration test: NRF_APPROVAL submit → approve → NRF record creation.

Exercises the full post-approval callback with a real database to catch
exception-type mismatches (NonRegularFacultyError vs ApprovalRequestError)
and payload shape discrepancies.
"""

from datetime import date
from uuid import uuid4

import pytest

from durgam.models.campus import Campus
from durgam.models.config_anchors import NonRegularFaculty
from durgam.models.crosscutting import ApprovalProcess, ApprovalRequest
from durgam.models.department import Department
from durgam.models.identity import Role, User, UserRole
from durgam.models.school import School
from durgam.services.approval_request import ApprovalRequestError, ApprovalRequestService


def _user(session, *, username=None) -> User:
    from durgam.services.password import hash_password

    u = User(
        username=username or f"t{uuid4().hex[:8]}",
        email=f"t{uuid4().hex[:8]}@test.com",
        full_name="Test User",
        password_hash=hash_password("Test_Pass1!XZ"),
    )
    session.add(u)
    session.flush()
    session.refresh(u)
    return u


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


def _nrf_process(session) -> ApprovalProcess:
    proc = ApprovalProcess(
        code=f"NRF_APPROVAL_{uuid4().hex[:6]}",
        title="NRF Approval Test",
        requestor_role_codes=["HOD"],
        channel_role_codes=["DEAN"],
        requires_upward_attachments=False,
        max_upward_attachments=5,
        requires_downward_attachments=False,
        max_downward_attachments=3,
        is_finance=False,
    )
    proc.code = "NRF_APPROVAL"
    session.add(proc)
    session.flush()
    session.refresh(proc)
    return proc


class TestNrfApproveFlow:
    def test_terminal_approve_creates_nrf_record(self, db_session):
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        requestor = _user(db_session)
        approver = _user(db_session)

        hod_role = _role(db_session, "HOD")
        dean_role = _role(db_session, "DEAN")
        _assign_role(db_session, requestor, hod_role, scope_type="department", scope_id=dept.id)
        _assign_role(db_session, approver, dean_role)

        proc = _nrf_process(db_session)
        svc = ApprovalRequestService(db_session)

        payload = {
            "description": "NRF test submission",
            "nrf_data": {
                "department_id": str(dept.id),
                "name": "Dr. Integration Test",
                "designation": "Professor",
                "organization": "Test University",
                "expertise": "Testing",
                "available_from": "2026-07-01",
                "available_to": "2026-12-31",
                "non_regular_type": "visiting",
            },
        }

        request = svc.submit(
            process_id=proc.id,
            requestor_user_id=requestor.id,
            title="NRF Test Request",
            payload=payload,
        )
        assert request.state == "submitted"

        result = svc.approve(
            request_id=request.id,
            approver_user_id=approver.id,
            comment="Approved for testing",
        )
        assert result.state == "approved"

        from sqlmodel import select

        nrf = db_session.exec(
            select(NonRegularFaculty).where(
                NonRegularFaculty.approval_request_id == request.id,
            )
        ).first()
        assert nrf is not None
        assert nrf.name == "Dr. Integration Test"
        assert nrf.designation == "Professor"
        assert nrf.organization == "Test University"
        assert nrf.is_admin_approved is True
        assert nrf.approved_by_user_id == approver.id
        assert nrf.department_id == dept.id
        assert nrf.available_from == date(2026, 7, 1)
        assert nrf.available_to == date(2026, 12, 31)

    def test_nrf_validation_error_surfaces_as_approval_request_error(self, db_session):
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        requestor = _user(db_session)
        approver = _user(db_session)

        hod_role = _role(db_session, "HOD")
        dean_role = _role(db_session, "DEAN")
        _assign_role(db_session, requestor, hod_role, scope_type="department", scope_id=dept.id)
        _assign_role(db_session, approver, dean_role)

        proc = _nrf_process(db_session)
        svc = ApprovalRequestService(db_session)

        payload = {
            "nrf_data": {
                "department_id": str(dept.id),
                "name": "Dr. Bad Dates",
                "designation": "Professor",
                "organization": "Test Org",
                "expertise": "Testing",
                "available_from": "2026-12-31",
                "available_to": "2026-07-01",
                "non_regular_type": "visiting",
            },
        }

        request = svc.submit(
            process_id=proc.id,
            requestor_user_id=requestor.id,
            title="NRF Bad Dates Request",
            payload=payload,
        )

        with pytest.raises(ApprovalRequestError, match="Cannot create NRF record"):
            svc.approve(
                request_id=request.id,
                approver_user_id=approver.id,
            )
