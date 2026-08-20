"""Integration tests for FacultyRequestService.approve_request (M10 Phase 5C1).

Coverage:
  1  FacultyRequest not found → FacultyRequestNotFoundError
  2  ApprovalRequest in terminal state → ApprovalRequestError (re-raised from engine)
  3  Stage 1 of 2-stage NOC process approved → stage advances, FacultyRequest stays SUBMITTED
  4  Final-stage approval atomically sets ApprovalRequest.state=approved +
     FacultyRequest.status=STATUS_APPROVED
  5  Actor not in approver pool → UnauthorizedActorError
  6  FacultyRequest has no approval_request_id → FacultyRequestNotFoundError
  7  OR-set approver_pool: HoD at requestor's dept+campus is eligible
  8  OR-set AhoD fallback: AhoD eligible when HoD absent at that dept+campus
  9  OR-set non-pool actor → UnauthorizedActorError
 10  Legacy process (no ApprovalStageOption rows) → M7 routing unchanged
 11  expected_stage_index mismatch → StageAlreadyAdvancedError

DB strategy: db_session (function-scoped, rolls back).
OR-set tests 3–9, 11 look up the seeded faculty_noc process; they skip gracefully
when run without test_faculty_noc_seed.py listed first in the invocation.
Test 10 uses a fully synthetic legacy process (no OR-set options).
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
    STATUS_APPROVED,
    STATUS_SUBMITTED,
    FacultyRequest,
)
from durgam.models.identity import Role, User, UserRole
from durgam.models.school import School
from durgam.services.approval_request import ApprovalRequestError
from durgam.services.faculty_request import (
    FacultyRequestNotFoundError,
    FacultyRequestService,
    StageAlreadyAdvancedError,
    UnauthorizedActorError,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(UTC)


def _make_dept_chain(session: Session) -> tuple[Campus, School, Designation, Department]:
    uid = uuid4().hex[:8]
    now = _now()

    campus = Campus(code=f"AC{uid[:4]}", name=f"Approve Campus {uid}", created_at=now, updated_at=now)
    session.add(campus)
    session.flush()

    school = School(code=f"AS{uid[:4]}", name=f"Approve School {uid}", created_at=now, updated_at=now)
    session.add(school)
    session.flush()

    desig = Designation(code=f"AD{uid[:4]}", name=f"Approve Desig {uid}", rank=99, created_at=now, updated_at=now)
    session.add(desig)
    session.flush()

    dept = Department(
        code=f"ADP{uid[:3]}",
        name=f"Approve Dept {uid}",
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
        first_name="Approve",
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
    current_stage: int = 1,
    state: str = "submitted",
) -> tuple[FacultyRequest, ApprovalRequest]:
    """Create a linked FacultyRequest (SUBMITTED) + ApprovalRequest."""
    actor_id = requestor_faculty.user_id
    now = _now()

    approval_req = ApprovalRequest(
        process_id=process.id,
        requestor_user_id=requestor_faculty.user_id,
        title="Test NOC Request",
        state=state,
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
        status=STATUS_SUBMITTED,
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
            "faculty_noc process not seeded — include test_faculty_noc_seed.py in smoke check invocation"
        )
    return process


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestFacultyRequestApprove:

    def test_approve_rejects_not_found(self, db_session: Session) -> None:
        svc = FacultyRequestService(db_session)
        with pytest.raises(FacultyRequestNotFoundError):
            svc.approve_request(uuid4(), actor_id=uuid4())

    def test_approve_rejects_when_no_approval_request_linked(self, db_session: Session) -> None:
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
            svc.approve_request(fac_req.id, actor_id=req_user.id)

    def test_approve_rejects_in_terminal_state(self, db_session: Session) -> None:
        process = _get_seeded_noc_process(db_session)
        campus, school, desig, dept = _make_dept_chain(db_session)
        req_user = _make_user(db_session, "req")
        req_faculty = _make_faculty_row(db_session, req_user, dept, campus, desig)

        fac_req, _ = _make_submitted_pair(db_session, req_faculty, process, state="approved")

        svc = FacultyRequestService(db_session)
        with pytest.raises(ApprovalRequestError, match="already approved"):
            svc.approve_request(fac_req.id, actor_id=uuid4())

    def test_approve_or_set_hod_eligible(self, db_session: Session) -> None:
        """OR-set approver_pool: HoD at requestor's specific dept+campus can approve."""
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
        result = svc.approve_request(fac_req.id, actor_id=hod_user.id)

        assert result.status == STATUS_SUBMITTED, "Non-terminal: FacultyRequest stays SUBMITTED"
        db_session.refresh(approval_req)
        assert approval_req.current_stage == 2

    def test_approve_or_set_ahod_eligible(self, db_session: Session) -> None:
        """OR-set AhoD fallback: AhoD at requestor's dept+campus is eligible when HoD absent."""
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
        result = svc.approve_request(fac_req.id, actor_id=ahod_user.id)

        assert result.status == STATUS_SUBMITTED, "Non-terminal: FacultyRequest stays SUBMITTED"
        db_session.refresh(approval_req)
        assert approval_req.current_stage == 2

    def test_approve_or_set_non_pool_actor_raises_unauthorized(self, db_session: Session) -> None:
        """Actor not in the OR-set pool raises UnauthorizedActorError."""
        process = _get_seeded_noc_process(db_session)
        campus, school, desig, dept = _make_dept_chain(db_session)

        req_user = _make_user(db_session, "req")
        req_faculty = _make_faculty_row(db_session, req_user, dept, campus, desig)

        # No HOD/AHOD with a Faculty row at this dept+campus → OR-set pool is empty
        fac_req, _ = _make_submitted_pair(db_session, req_faculty, process)
        outsider = _make_user(db_session, "outsider")

        svc = FacultyRequestService(db_session)
        with pytest.raises(UnauthorizedActorError):
            svc.approve_request(fac_req.id, actor_id=outsider.id)

    def test_approve_advances_stage_midway(self, db_session: Session) -> None:
        """Stage 1 of 2-stage NOC process: approval_req advances, FacultyRequest stays SUBMITTED."""
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
        result = svc.approve_request(fac_req.id, actor_id=hod_user.id)

        assert result.status == STATUS_SUBMITTED, "Non-terminal: FacultyRequest stays SUBMITTED"
        db_session.refresh(approval_req)
        assert approval_req.state == "in_review"
        assert approval_req.current_stage == 2

    def test_approve_atomic_with_terminal_sync(self, db_session: Session) -> None:
        """Final-stage (REGISTRAR) approval sets approval_req=approved + fac_req=APPROVED."""
        process = _get_seeded_noc_process(db_session)
        campus, school, desig, dept = _make_dept_chain(db_session)

        req_user = _make_user(db_session, "req")
        req_faculty = _make_faculty_row(db_session, req_user, dept, campus, desig)

        # REGISTRAR is stage 2 of faculty_noc; no OR-set options for stage 2 →
        # falls through to M7 routing; a universitywide REGISTRAR satisfies it.
        registrar_role = _get_or_create_role(db_session, "REGISTRAR", "Registrar", 80)
        registrar_user = _make_user(db_session, "reg")
        _link_role_universitywide(db_session, registrar_user, registrar_role)

        # Start at stage 2 (stage 1 already approved in a prior step)
        fac_req, approval_req = _make_submitted_pair(
            db_session, req_faculty, process, current_stage=2, state="in_review"
        )

        svc = FacultyRequestService(db_session)
        result = svc.approve_request(fac_req.id, actor_id=registrar_user.id)

        assert result.status == STATUS_APPROVED, "Terminal: FacultyRequest.status → APPROVED"
        db_session.refresh(approval_req)
        assert approval_req.state == "approved"

    def test_approve_rejects_unauthorized_actor(self, db_session: Session) -> None:
        """When HOD is in the pool but a different user acts, UnauthorizedActorError is raised."""
        process = _get_seeded_noc_process(db_session)
        campus, school, desig, dept = _make_dept_chain(db_session)

        req_user = _make_user(db_session, "req")
        req_faculty = _make_faculty_row(db_session, req_user, dept, campus, desig)

        hod_role = _get_or_create_role(db_session, "HOD", "Head of Department", 50)
        hod_user = _make_user(db_session, "hod")
        _make_faculty_row(db_session, hod_user, dept, campus, desig)
        _link_role_to_dept(db_session, hod_user, hod_role, dept)

        fac_req, _ = _make_submitted_pair(db_session, req_faculty, process)
        unauthorized = _make_user(db_session, "unauth")

        svc = FacultyRequestService(db_session)
        with pytest.raises(UnauthorizedActorError):
            svc.approve_request(fac_req.id, actor_id=unauthorized.id)

    def test_existing_legacy_process_eligibility_unchanged(self, db_session: Session) -> None:
        """Legacy process (no ApprovalStageOption rows) routes via M7 scope-chain unchanged.

        _resolve_or_set_approvers returns None (empty options list) → M7 path used →
        HOD found via resolve_stage_approvers → approval succeeds.
        """
        now = _now()
        legacy_proc = ApprovalProcess(
            code="faculty_legacy_compat_test",
            title="Legacy Compat Test",
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
        result = svc.approve_request(fac_req.id, actor_id=hod_user.id)

        # Single-stage (HOD only) → terminal → both records updated
        assert result.status == STATUS_APPROVED
        db_session.refresh(approval_req)
        assert approval_req.state == "approved"

    def test_approve_rejects_already_advanced_stage(self, db_session: Session) -> None:
        """expected_stage_index mismatch after concurrent approval raises StageAlreadyAdvancedError."""
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
        # HoD approves stage 1 → stage advances to 2
        svc.approve_request(fac_req.id, actor_id=hod_user.id)
        db_session.refresh(approval_req)
        assert approval_req.current_stage == 2

        # Second call with stale expected_stage_index=1 → StageAlreadyAdvancedError
        with pytest.raises(StageAlreadyAdvancedError):
            svc.approve_request(fac_req.id, actor_id=hod_user.id, expected_stage_index=1)
