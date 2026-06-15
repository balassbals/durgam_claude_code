"""Integration tests for FacultyRequestService.reject_request + withdraw_request
(M10 Phase 5C2).

Coverage:
  Reject (9 tests):
  1  test_reject_or_set_hod_eligible — HoD rejects Stage 1; FacultyRequest → REJECTED,
     ApprovalRequest → rejected
  2  test_reject_or_set_ahod_eligible — AhoD rejects when HoD absent
  3  test_reject_or_set_non_pool_actor_raises_unauthorized
  4  test_reject_legacy_stage_unchanged — backward-compat: legacy process, M7 routing
  5  test_reject_empty_reason_raises
  6  test_reject_whitespace_reason_raises
  7  test_reject_long_reason_raises — > 1000 chars
  8  test_reject_when_not_submitted_raises
  9  test_reject_concurrent_stage_advance_raises — expected_stage_index mismatch

  Withdraw (6 tests):
  10 test_withdraw_by_faculty_succeeds — FacultyRequest → WITHDRAWN
  11 test_withdraw_by_non_faculty_raises_unauthorized_withdraw — HoD → error
  12 test_withdraw_by_different_faculty_user_raises_unauthorized
  13 test_withdraw_when_not_submitted_raises — DRAFT state rejected
  14 test_withdraw_when_no_approval_request_linked_raises
  15 test_withdraw_cancels_approval_request — ApprovalRequest.state → "withdrawn"

DB strategy: db_session (function-scoped, rolls back).
OR-set tests look up the seeded faculty_noc process (visible when smoke check
includes test_faculty_noc_seed.py first). Legacy and withdraw tests use synthetic
data only.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session, select

from durgam.models.campus import Campus
from durgam.models.config_anchors import Designation
from durgam.models.crosscutting import ApprovalProcess, ApprovalRequest
from durgam.models.department import Department
from durgam.models.faculty import Faculty
from durgam.models.faculty_request import (
    REQUEST_TYPE_NOC,
    STATUS_DRAFT,
    STATUS_REJECTED,
    STATUS_SUBMITTED,
    STATUS_WITHDRAWN,
    FacultyRequest,
)
from durgam.models.identity import Role, User, UserRole
from durgam.models.school import School
from durgam.services.faculty_request import (
    FacultyRequestNotFoundError,
    FacultyRequestService,
    InvalidRejectReasonError,
    InvalidRequestStatusTransitionError,
    StageAlreadyAdvancedError,
    UnauthorizedActorError,
    UnauthorizedWithdrawError,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(UTC)


def _make_dept_chain(session: Session) -> tuple[Campus, School, Designation, Department]:
    uid = uuid4().hex[:8]
    now = _now()

    campus = Campus(code=f"RC{uid[:4]}", name=f"RW Campus {uid}", created_at=now, updated_at=now)
    session.add(campus)
    session.flush()

    school = School(code=f"RS{uid[:4]}", name=f"RW School {uid}", created_at=now, updated_at=now)
    session.add(school)
    session.flush()

    desig = Designation(code=f"RD{uid[:4]}", name=f"RW Desig {uid}", rank=99, created_at=now, updated_at=now)
    session.add(desig)
    session.flush()

    dept = Department(
        code=f"RDP{uid[:3]}",
        name=f"RW Dept {uid}",
        school_id=school.id,
        main_campus_id=campus.id,
        created_at=now,
        updated_at=now,
    )
    session.add(dept)
    session.flush()

    return campus, school, desig, dept


def _make_user(session: Session, prefix: str = "u") -> User:
    uid = uuid4().hex[:8]
    now = _now()
    user = User(
        username=f"{prefix}_{uid}",
        email=f"{prefix}_{uid}@dev.local",
        password_hash="x",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    session.flush()
    return user


def _make_faculty_row(
    session: Session,
    user: User,
    dept: Department,
    campus: Campus,
    desig: Designation,
) -> Faculty:
    now = _now()
    faculty = Faculty(
        user_id=user.id,
        employee_id=f"EMP-{uuid4().hex[:8]}",
        title="Dr",
        first_name="Reject",
        last_name="Faculty",
        designation_id=desig.id,
        department_id=dept.id,
        campus_id=campus.id,
        joining_date=date(2021, 6, 1),
        phone="9000000099",
        emergency_contact_name="EC",
        emergency_contact_relation="Parent",
        emergency_contact_phone="9000000098",
        is_phd=False,
        created_at=now,
        updated_at=now,
    )
    session.add(faculty)
    session.flush()
    return faculty


def _get_or_create_role(session: Session, code: str, name: str, level: int = 50) -> Role:
    role = session.exec(
        select(Role).where(Role.code == code, Role.is_deleted == False)  # noqa: E712
    ).first()
    if role is None:
        now = _now()
        role = Role(code=code, name=name, level=level, created_at=now, updated_at=now)
        session.add(role)
        session.flush()
    return role


def _link_role_to_dept(session: Session, user: User, role: Role, dept: Department) -> UserRole:
    ur = UserRole(user_id=user.id, role_id=role.id, scope_type="department", scope_id=dept.id)
    session.add(ur)
    session.flush()
    return ur


def _link_role_universitywide(session: Session, user: User, role: Role) -> UserRole:
    ur = UserRole(user_id=user.id, role_id=role.id, scope_type=None, scope_id=None)
    session.add(ur)
    session.flush()
    return ur


def _make_submitted_pair(
    session: Session,
    requestor_faculty: Faculty,
    process: ApprovalProcess,
    *,
    fac_status: str = STATUS_SUBMITTED,
    approval_state: str = "submitted",
    current_stage: int = 1,
) -> tuple[FacultyRequest, ApprovalRequest]:
    actor_id = requestor_faculty.user_id
    now = _now()

    approval_req = ApprovalRequest(
        process_id=process.id,
        requestor_user_id=requestor_faculty.user_id,
        title="Test NOC Request",
        state=approval_state,
        current_stage=current_stage,
        created_by=actor_id,
        updated_by=actor_id,
        created_at=now,
        updated_at=now,
    )
    session.add(approval_req)
    session.flush()
    session.refresh(approval_req)

    fac_req = FacultyRequest(
        faculty_id=requestor_faculty.id,
        request_type=REQUEST_TYPE_NOC,
        status=fac_status,
        approval_request_id=approval_req.id,
        created_by=actor_id,
        updated_by=actor_id,
        created_at=now,
        updated_at=now,
    )
    session.add(fac_req)
    session.flush()
    session.refresh(fac_req)
    return fac_req, approval_req


def _get_seeded_noc_process(session: Session) -> ApprovalProcess:
    process = session.exec(
        select(ApprovalProcess).where(
            ApprovalProcess.code == "faculty_noc",
            ApprovalProcess.is_deleted == False,  # noqa: E712
        )
    ).first()
    if process is None:
        pytest.skip(
            "faculty_noc process not seeded — include test_faculty_noc_seed.py in smoke check"
        )
    return process


# ── Reject tests ──────────────────────────────────────────────────────────────


class TestRejectRequest:

    def test_reject_or_set_hod_eligible(self, db_session: Session) -> None:
        """HoD in OR-set pool can reject Stage 1; FacultyRequest → REJECTED,
        ApprovalRequest → rejected."""
        process = _get_seeded_noc_process(db_session)
        campus, school, desig, dept = _make_dept_chain(db_session)

        req_user = _make_user(db_session, "req")
        req_faculty = _make_faculty_row(db_session, req_user, dept, campus, desig)

        hod_role = _get_or_create_role(db_session, "HOD", "Head of Department", 50)
        hod_user = _make_user(db_session, "hod")
        _make_faculty_row(db_session, hod_user, dept, campus, desig)
        _link_role_to_dept(db_session, hod_user, hod_role, dept)

        fac_req, approval_req = _make_submitted_pair(db_session, req_faculty, process)

        svc = FacultyRequestService(db_session)
        result = svc.reject_request(fac_req.id, actor_id=hod_user.id, reason="Not suitable")

        assert result.status == STATUS_REJECTED
        db_session.refresh(approval_req)
        assert approval_req.state == "rejected"

    def test_reject_or_set_ahod_eligible(self, db_session: Session) -> None:
        """AhoD in OR-set pool rejects Stage 1 when HoD is absent (resolver fallback)."""
        process = _get_seeded_noc_process(db_session)
        campus, school, desig, dept = _make_dept_chain(db_session)

        req_user = _make_user(db_session, "req")
        req_faculty = _make_faculty_row(db_session, req_user, dept, campus, desig)

        ahod_role = _get_or_create_role(db_session, "AHOD", "Associate Head of Department", 45)
        ahod_user = _make_user(db_session, "ahod")
        _make_faculty_row(db_session, ahod_user, dept, campus, desig)
        _link_role_to_dept(db_session, ahod_user, ahod_role, dept)

        fac_req, approval_req = _make_submitted_pair(db_session, req_faculty, process)

        svc = FacultyRequestService(db_session)
        result = svc.reject_request(fac_req.id, actor_id=ahod_user.id, reason="Incomplete docs")

        assert result.status == STATUS_REJECTED
        db_session.refresh(approval_req)
        assert approval_req.state == "rejected"

    def test_reject_or_set_non_pool_actor_raises_unauthorized(self, db_session: Session) -> None:
        """Actor not in OR-set pool raises UnauthorizedActorError."""
        process = _get_seeded_noc_process(db_session)
        campus, school, desig, dept = _make_dept_chain(db_session)

        req_user = _make_user(db_session, "req")
        req_faculty = _make_faculty_row(db_session, req_user, dept, campus, desig)

        # No HOD/AHOD at this dept → OR-set pool empty → any actor unauthorized
        fac_req, _ = _make_submitted_pair(db_session, req_faculty, process)
        outsider = _make_user(db_session, "outsider")

        svc = FacultyRequestService(db_session)
        with pytest.raises(UnauthorizedActorError):
            svc.reject_request(fac_req.id, actor_id=outsider.id, reason="Rejected")

    def test_reject_legacy_stage_unchanged(self, db_session: Session) -> None:
        """Legacy process (no ApprovalStageOption rows) routes via M7 scope-chain for rejection."""
        now = _now()
        legacy_proc = ApprovalProcess(
            code="faculty_legacy_reject_test",
            title="Legacy Reject Test",
            requestor_role_codes=["FACULTY"],
            channel_role_codes=["HOD"],
            is_finance=False,
            stage_pick_modes_json=None,
            created_at=now,
            updated_at=now,
        )
        db_session.add(legacy_proc)
        db_session.flush()

        campus, school, desig, dept = _make_dept_chain(db_session)
        req_user = _make_user(db_session, "req")
        req_faculty = _make_faculty_row(db_session, req_user, dept, campus, desig)
        faculty_role = _get_or_create_role(db_session, "FACULTY", "Faculty", 30)
        _link_role_to_dept(db_session, req_user, faculty_role, dept)

        hod_role = _get_or_create_role(db_session, "HOD", "Head of Department", 50)
        hod_user = _make_user(db_session, "hod")
        _link_role_to_dept(db_session, hod_user, hod_role, dept)

        fac_req, approval_req = _make_submitted_pair(db_session, req_faculty, legacy_proc)

        svc = FacultyRequestService(db_session)
        result = svc.reject_request(fac_req.id, actor_id=hod_user.id, reason="Legacy rejection test")

        assert result.status == STATUS_REJECTED
        db_session.refresh(approval_req)
        assert approval_req.state == "rejected"

    def test_reject_empty_reason_raises(self, db_session: Session) -> None:
        svc = FacultyRequestService(db_session)
        with pytest.raises(InvalidRejectReasonError, match="non-empty"):
            svc.reject_request(uuid4(), actor_id=uuid4(), reason="")

    def test_reject_whitespace_reason_raises(self, db_session: Session) -> None:
        svc = FacultyRequestService(db_session)
        with pytest.raises(InvalidRejectReasonError, match="non-empty"):
            svc.reject_request(uuid4(), actor_id=uuid4(), reason="   ")

    def test_reject_long_reason_raises(self, db_session: Session) -> None:
        svc = FacultyRequestService(db_session)
        with pytest.raises(InvalidRejectReasonError, match="1000"):
            svc.reject_request(uuid4(), actor_id=uuid4(), reason="x" * 1001)

    def test_reject_when_not_submitted_raises(self, db_session: Session) -> None:
        """FacultyRequest in DRAFT raises InvalidRequestStatusTransitionError."""
        process = _get_seeded_noc_process(db_session)
        campus, school, desig, dept = _make_dept_chain(db_session)
        req_user = _make_user(db_session, "req")
        req_faculty = _make_faculty_row(db_session, req_user, dept, campus, desig)

        # Create FacultyRequest in DRAFT (not linked to any approval request)
        now = _now()
        fac_req = FacultyRequest(
            faculty_id=req_faculty.id,
            request_type=REQUEST_TYPE_NOC,
            status=STATUS_DRAFT,
            approval_request_id=None,
            created_by=req_user.id,
            updated_by=req_user.id,
            created_at=now,
            updated_at=now,
        )
        db_session.add(fac_req)
        db_session.flush()

        svc = FacultyRequestService(db_session)
        with pytest.raises(InvalidRequestStatusTransitionError, match="Cannot reject"):
            svc.reject_request(fac_req.id, actor_id=uuid4(), reason="Rejected")

    def test_reject_concurrent_stage_advance_raises(self, db_session: Session) -> None:
        """expected_stage_index mismatch raises StageAlreadyAdvancedError."""
        process = _get_seeded_noc_process(db_session)
        campus, school, desig, dept = _make_dept_chain(db_session)
        req_user = _make_user(db_session, "req")
        req_faculty = _make_faculty_row(db_session, req_user, dept, campus, desig)

        # Request is at stage 1; caller passes expected_stage_index=2 → mismatch
        fac_req, _ = _make_submitted_pair(db_session, req_faculty, process, current_stage=1)

        svc = FacultyRequestService(db_session)
        with pytest.raises(StageAlreadyAdvancedError):
            svc.reject_request(
                fac_req.id, actor_id=uuid4(), reason="Test", expected_stage_index=2
            )


# ── Withdraw tests ────────────────────────────────────────────────────────────


class TestWithdrawRequest:

    def test_withdraw_by_faculty_succeeds(self, db_session: Session) -> None:
        """Faculty's own User withdraws their request → FacultyRequest → WITHDRAWN."""
        process = _get_seeded_noc_process(db_session)
        campus, school, desig, dept = _make_dept_chain(db_session)
        req_user = _make_user(db_session, "req")
        req_faculty = _make_faculty_row(db_session, req_user, dept, campus, desig)

        fac_req, _ = _make_submitted_pair(db_session, req_faculty, process)

        svc = FacultyRequestService(db_session)
        result = svc.withdraw_request(fac_req.id, actor_id=req_user.id)

        assert result.status == STATUS_WITHDRAWN

    def test_withdraw_cancels_approval_request(self, db_session: Session) -> None:
        """Withdrawal delegates to engine; ApprovalRequest.state → 'withdrawn'."""
        process = _get_seeded_noc_process(db_session)
        campus, school, desig, dept = _make_dept_chain(db_session)
        req_user = _make_user(db_session, "req")
        req_faculty = _make_faculty_row(db_session, req_user, dept, campus, desig)

        fac_req, approval_req = _make_submitted_pair(db_session, req_faculty, process)

        svc = FacultyRequestService(db_session)
        svc.withdraw_request(fac_req.id, actor_id=req_user.id)

        db_session.refresh(approval_req)
        assert approval_req.state == "withdrawn"

    def test_withdraw_by_non_faculty_raises_unauthorized_withdraw(self, db_session: Session) -> None:
        """A user who is not the originating faculty raises UnauthorizedWithdrawError."""
        process = _get_seeded_noc_process(db_session)
        campus, school, desig, dept = _make_dept_chain(db_session)
        req_user = _make_user(db_session, "req")
        req_faculty = _make_faculty_row(db_session, req_user, dept, campus, desig)

        fac_req, _ = _make_submitted_pair(db_session, req_faculty, process)

        hod_role = _get_or_create_role(db_session, "HOD", "Head of Department", 50)
        hod_user = _make_user(db_session, "hod")
        _link_role_universitywide(db_session, hod_user, hod_role)

        svc = FacultyRequestService(db_session)
        with pytest.raises(UnauthorizedWithdrawError):
            svc.withdraw_request(fac_req.id, actor_id=hod_user.id)

    def test_withdraw_by_different_faculty_user_raises_unauthorized(self, db_session: Session) -> None:
        """Another faculty member's User cannot withdraw someone else's request."""
        process = _get_seeded_noc_process(db_session)
        campus, school, desig, dept = _make_dept_chain(db_session)

        req_user = _make_user(db_session, "req")
        req_faculty = _make_faculty_row(db_session, req_user, dept, campus, desig)

        other_user = _make_user(db_session, "other")
        _make_faculty_row(db_session, other_user, dept, campus, desig)

        fac_req, _ = _make_submitted_pair(db_session, req_faculty, process)

        svc = FacultyRequestService(db_session)
        with pytest.raises(UnauthorizedWithdrawError):
            svc.withdraw_request(fac_req.id, actor_id=other_user.id)

    def test_withdraw_when_not_submitted_raises(self, db_session: Session) -> None:
        """FacultyRequest in DRAFT raises InvalidRequestStatusTransitionError."""
        process = _get_seeded_noc_process(db_session)
        campus, school, desig, dept = _make_dept_chain(db_session)
        req_user = _make_user(db_session, "req")
        req_faculty = _make_faculty_row(db_session, req_user, dept, campus, desig)

        now = _now()
        fac_req = FacultyRequest(
            faculty_id=req_faculty.id,
            request_type=REQUEST_TYPE_NOC,
            status=STATUS_DRAFT,
            approval_request_id=None,
            created_by=req_user.id,
            updated_by=req_user.id,
            created_at=now,
            updated_at=now,
        )
        db_session.add(fac_req)
        db_session.flush()

        svc = FacultyRequestService(db_session)
        with pytest.raises(InvalidRequestStatusTransitionError, match="Cannot withdraw"):
            svc.withdraw_request(fac_req.id, actor_id=req_user.id)

    def test_withdraw_when_no_approval_request_linked_raises(self, db_session: Session) -> None:
        """FacultyRequest with no approval_request_id raises FacultyRequestNotFoundError."""
        process = _get_seeded_noc_process(db_session)
        campus, school, desig, dept = _make_dept_chain(db_session)
        req_user = _make_user(db_session, "req")
        req_faculty = _make_faculty_row(db_session, req_user, dept, campus, desig)

        now = _now()
        fac_req = FacultyRequest(
            faculty_id=req_faculty.id,
            request_type=REQUEST_TYPE_NOC,
            status=STATUS_SUBMITTED,
            approval_request_id=None,
            created_by=req_user.id,
            updated_by=req_user.id,
            created_at=now,
            updated_at=now,
        )
        db_session.add(fac_req)
        db_session.flush()

        svc = FacultyRequestService(db_session)
        with pytest.raises(FacultyRequestNotFoundError, match="not linked"):
            svc.withdraw_request(fac_req.id, actor_id=req_user.id)
