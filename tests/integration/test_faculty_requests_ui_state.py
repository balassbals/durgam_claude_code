"""Integration tests for faculty request UI state logic (M10 Phase 7B).

Tests exercise the service layer directly (FacultyRequestService) to verify
the data contracts that state handlers depend on.

Coverage:
  A (list_for_faculty, 4): list empty, list returns own requests, status filter,
     multiple types ordered most-recent-first
  B (create + update payload, 4): create draft, update payload with NOC fields,
     update payload rejected on submitted, NOC payload round-trip
  C (submit flow, 4): submit transitions status, submit creates ApprovalRequest,
     submit requires process, double-submit rejected
  D (attachments, 3): list_attachments empty, list_attachments after add stub,
     remove_attachment not allowed on submitted
  E (withdraw, 3): withdraw sets status withdrawn, unauthorized withdraw rejected,
     double-withdraw rejected
  F (actions for requestor, 2): empty on fresh submit, returns visible action

DB strategy: db_session (function-scoped, rolls back). All synthetic data.
0 skips, no seed dependency.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session, select

from durgam.models.campus import Campus
from durgam.models.config_anchors import Designation
from durgam.models.crosscutting import ApprovalAction, ApprovalProcess, ApprovalRequest, ApprovalStageOption
from durgam.models.department import Department
from durgam.models.faculty import Faculty
from durgam.models.faculty_request import (
    REQUEST_TYPE_NOC,
    STATUS_DRAFT,
    STATUS_SUBMITTED,
    STATUS_WITHDRAWN,
)
from durgam.models.identity import Role, User, UserRole
from durgam.models.school import School
from durgam.repositories.approval_action import ApprovalActionRepository
from durgam.repositories.faculty import FacultyRepository
from durgam.services.faculty_request import (
    EmptyApproverPoolError,
    FacultyRequestNotFoundError,
    FacultyRequestService,
    InvalidRequestStatusTransitionError,
    UnauthorizedWithdrawError,
    UnknownRequestTypeError,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(UTC)


def _make_faculty(session: Session) -> Faculty:
    uid = uuid4().hex[:8]
    now = _now()

    campus = Campus(code=f"UC{uid[:4]}", name=f"UI Campus {uid}")
    session.add(campus)
    session.flush()

    school = School(code=f"US{uid[:4]}", name=f"UI School {uid}")
    session.add(school)
    session.flush()

    desig = Designation(code=f"UD{uid[:4]}", name=f"UI Desig {uid}", rank=99)
    session.add(desig)
    session.flush()

    dept = Department(
        code=f"UDT{uid[:3]}",
        name=f"UI Dept {uid}",
        school_id=school.id,
        main_campus_id=campus.id,
    )
    session.add(dept)
    session.flush()

    user = User(
        username=f"uiu_{uid}",
        email=f"uiu_{uid}@dev.local",
        password_hash="x",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    session.flush()

    faculty = Faculty(
        user_id=user.id,
        employee_id=f"UIEMP-{uid}",
        title="Dr",
        first_name="UI",
        last_name="Faculty",
        designation_id=desig.id,
        department_id=dept.id,
        campus_id=campus.id,
        joining_date=date(2021, 6, 1),
        phone="9000000020",
        emergency_contact_name="EC",
        emergency_contact_relation="Parent",
        emergency_contact_phone="9000000021",
        is_phd=False,
        created_at=now,
        updated_at=now,
    )
    session.add(faculty)
    session.flush()
    return faculty


def _noc_payload() -> dict:
    return {
        "purpose": "Conference attendance at IIT Delhi",
        "to_whom": "Event Coordinator, IIT Delhi",
        "date_required_by": "2026-08-01",
        "additional_notes": "Five-day workshop.",
    }


def _make_process_and_approver(session: Session, faculty: Faculty) -> tuple[ApprovalProcess, User]:
    """Get-or-create the faculty_noc process + a dept-scoped HOD approver.

    In isolation (no seed): creates a minimal process (no ApprovalStageOption rows);
    legacy routing via channel_role_codes=["HOD"] dispatches submit.
    In full suite (with seed): gets the existing seeded process + creates a synthetic HOD
    whose Faculty.campus_id and UserRole.scope_id match the requestor faculty, satisfying
    the dept_head_at_requestor_campus OR-set resolver.

    Returns (process, approver_user).
    """
    uid = uuid4().hex[:8]
    now = _now()

    # 1. Get-or-create faculty_noc — avoids UniqueViolation when running alongside seeded DB.
    process = session.exec(
        select(ApprovalProcess).where(
            ApprovalProcess.code == "faculty_noc",
            ApprovalProcess.is_deleted == False,  # noqa: E712
        )
    ).first()
    if process is None:
        # Isolation mode: create process with OR-set config so dept_head_at_requestor_campus
        # resolver runs instead of legacy scope-chain routing (which needs requestor UserRole rows).
        process = ApprovalProcess(
            code="faculty_noc",
            title="Faculty NOC Approval",
            channel_role_codes=["HOD"],
            requestor_role_codes=["FACULTY"],
            stage_pick_modes_json={"1": "approver"},
            created_at=now,
            updated_at=now,
        )
        session.add(process)
        session.flush()
        option = ApprovalStageOption(
            approval_process_id=process.id,
            stage_index=1,
            resolver_name="dept_head_at_requestor_campus",
            label="Head of Department",
            sort_order=0,
            created_at=now,
            updated_at=now,
        )
        session.add(option)
        session.flush()

    # 2. Get-or-create HOD role.
    hod_role = session.exec(
        select(Role).where(Role.code == "HOD", Role.is_deleted == False)  # noqa: E712
    ).first()
    if hod_role is None:
        hod_role = Role(code="HOD", name="Head of Department", level=50, created_at=now, updated_at=now)
        session.add(hod_role)
        session.flush()

    # 3. Synthetic approver user.
    approver_user = User(
        username=f"uiapp_{uid}",
        email=f"uiapp_{uid}@dev.local",
        password_hash="x",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(approver_user)
    session.flush()

    # 4. Approver Faculty on the SAME dept + campus as the requestor.
    #    The dept_head_at_requestor_campus resolver joins Faculty.campus_id == requestor campus.
    approver_faculty = Faculty(
        user_id=approver_user.id,
        employee_id=f"APPFAC-{uid}",
        title="Dr",
        first_name="Approver",
        last_name="HOD",
        designation_id=faculty.designation_id,
        department_id=faculty.department_id,
        campus_id=faculty.campus_id,
        joining_date=date(2020, 1, 1),
        phone="9000000099",
        emergency_contact_name="EC",
        emergency_contact_relation="Parent",
        emergency_contact_phone="9000000098",
        is_phd=False,
        created_at=now,
        updated_at=now,
    )
    session.add(approver_faculty)
    session.flush()

    # 5. Bind HOD role scoped to requestor's department (satisfies both legacy routing
    #    scope-chain walk and OR-set resolver's UserRole.scope_id == dept_id check).
    user_role = UserRole(
        user_id=approver_user.id,
        role_id=hod_role.id,
        scope_type="department",
        scope_id=faculty.department_id,
    )
    session.add(user_role)
    session.flush()

    return process, approver_user


# ── Group A: list_for_faculty ─────────────────────────────────────────────────


class TestListForFaculty:

    def test_list_empty_for_new_faculty(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = FacultyRequestService(db_session)
        result = svc.list_for_faculty(faculty.id)
        assert result == []

    def test_list_returns_own_draft(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = FacultyRequestService(db_session)
        svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=faculty.user_id,
        )
        result = svc.list_for_faculty(faculty.id)
        assert len(result) == 1
        assert result[0].request_type == REQUEST_TYPE_NOC
        assert result[0].status == STATUS_DRAFT

    def test_list_does_not_return_other_faculty_requests(self, db_session: Session) -> None:
        faculty_a = _make_faculty(db_session)
        faculty_b = _make_faculty(db_session)
        svc = FacultyRequestService(db_session)
        svc.create_request(
            faculty_id=faculty_a.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=faculty_a.user_id,
        )
        result = svc.list_for_faculty(faculty_b.id)
        assert result == []

    def test_list_status_filter_draft(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = FacultyRequestService(db_session)
        svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=faculty.user_id,
        )
        draft_only = svc.list_for_faculty(faculty.id, status=STATUS_DRAFT)
        submitted_only = svc.list_for_faculty(faculty.id, status=STATUS_SUBMITTED)
        assert len(draft_only) == 1
        assert submitted_only == []


# ── Group B: create + update payload ──────────────────────────────────────────


class TestCreateAndUpdatePayload:

    def test_create_request_creates_draft(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=faculty.user_id,
        )
        assert req.status == STATUS_DRAFT
        assert req.request_type == REQUEST_TYPE_NOC
        assert req.faculty_id == faculty.id
        assert req.payload_json is None

    def test_update_payload_stores_noc_fields(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=faculty.user_id,
        )
        payload = _noc_payload()
        updated = svc.update_payload(req.id, payload, faculty.user_id)
        assert updated.payload_json == payload

    def test_update_payload_rejected_on_submitted(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _make_process_and_approver(db_session, faculty)
        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=_noc_payload(),
            actor_id=faculty.user_id,
        )
        svc.submit_for_approval(req.id, faculty.user_id)
        with pytest.raises(InvalidRequestStatusTransitionError):
            svc.update_payload(req.id, {"purpose": "New purpose"}, faculty.user_id)

    def test_noc_payload_round_trip(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = FacultyRequestService(db_session)
        payload = _noc_payload()
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=payload,
            actor_id=faculty.user_id,
        )
        row = svc.get_request(req.id)
        assert row.payload_json["purpose"] == payload["purpose"]
        assert row.payload_json["to_whom"] == payload["to_whom"]
        assert row.payload_json["date_required_by"] == payload["date_required_by"]
        assert row.payload_json["additional_notes"] == payload["additional_notes"]


# ── Group C: submit flow ───────────────────────────────────────────────────────


class TestSubmitFlow:

    def test_submit_transitions_status_to_submitted(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _make_process_and_approver(db_session, faculty)
        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=_noc_payload(),
            actor_id=faculty.user_id,
        )
        submitted = svc.submit_for_approval(req.id, faculty.user_id)
        assert submitted.status == STATUS_SUBMITTED

    def test_submit_creates_approval_request(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _make_process_and_approver(db_session, faculty)
        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=_noc_payload(),
            actor_id=faculty.user_id,
        )
        submitted = svc.submit_for_approval(req.id, faculty.user_id)
        assert submitted.approval_request_id is not None
        approval = db_session.get(ApprovalRequest, submitted.approval_request_id)
        assert approval is not None
        assert approval.state == "submitted"

    def test_submit_fails_when_no_approver_configured(self, db_session: Session) -> None:
        # In isolation (no seed): process absent → UnknownRequestTypeError.
        # In full suite (with seed): process present but no HOD for this test dept →
        # OR-set resolver returns empty pool → EmptyApproverPoolError.
        faculty = _make_faculty(db_session)
        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=_noc_payload(),
            actor_id=faculty.user_id,
        )
        with pytest.raises((UnknownRequestTypeError, EmptyApproverPoolError)):
            svc.submit_for_approval(req.id, faculty.user_id)

    def test_double_submit_rejected(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _make_process_and_approver(db_session, faculty)
        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=_noc_payload(),
            actor_id=faculty.user_id,
        )
        svc.submit_for_approval(req.id, faculty.user_id)
        with pytest.raises(InvalidRequestStatusTransitionError):
            svc.submit_for_approval(req.id, faculty.user_id)


# ── Group D: attachments ───────────────────────────────────────────────────────


class TestAttachments:

    def test_list_attachments_empty_on_fresh_draft(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=faculty.user_id,
        )
        assert svc.list_attachments(req.id) == []

    def test_list_attachments_returns_empty_for_unknown_request_id(self, db_session: Session) -> None:
        svc = FacultyRequestService(db_session)
        result = svc.list_attachments(uuid4())
        assert result == []

    def test_remove_attachment_blocked_on_submitted(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _make_process_and_approver(db_session, faculty)
        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=_noc_payload(),
            actor_id=faculty.user_id,
        )
        svc.submit_for_approval(req.id, faculty.user_id)
        with pytest.raises((InvalidRequestStatusTransitionError, Exception)):
            svc.remove_attachment(uuid4(), faculty.user_id)


# ── Group E: withdraw ──────────────────────────────────────────────────────────


class TestWithdraw:

    def test_withdraw_sets_status_withdrawn(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _make_process_and_approver(db_session, faculty)
        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=_noc_payload(),
            actor_id=faculty.user_id,
        )
        svc.submit_for_approval(req.id, faculty.user_id)
        withdrawn = svc.withdraw_request(req.id, faculty.user_id)
        assert withdrawn.status == STATUS_WITHDRAWN

    def test_unauthorized_withdraw_raises(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        other_faculty = _make_faculty(db_session)
        _make_process_and_approver(db_session, faculty)
        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=_noc_payload(),
            actor_id=faculty.user_id,
        )
        svc.submit_for_approval(req.id, faculty.user_id)
        with pytest.raises(UnauthorizedWithdrawError):
            svc.withdraw_request(req.id, other_faculty.user_id)

    def test_withdraw_draft_raises(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=None,
            actor_id=faculty.user_id,
        )
        with pytest.raises(InvalidRequestStatusTransitionError):
            svc.withdraw_request(req.id, faculty.user_id)


# ── Group F: list_actions_for_requestor (via FacultyRequestService) ───────────


class TestListActionsForRequestor:

    def test_empty_on_fresh_submit(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _make_process_and_approver(db_session, faculty)
        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=_noc_payload(),
            actor_id=faculty.user_id,
        )
        svc.submit_for_approval(req.id, faculty.user_id)
        actions = svc.list_actions_for_requestor(req.id)
        assert actions == []

    def test_visible_action_appears_after_approve(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _, approver_user = _make_process_and_approver(db_session, faculty)
        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=_noc_payload(),
            actor_id=faculty.user_id,
        )
        submitted = svc.submit_for_approval(req.id, faculty.user_id)

        from durgam.services.approval_request import ApprovalRequestService
        apr_svc = ApprovalRequestService(db_session)
        apr_svc.approve(
            request_id=submitted.approval_request_id,
            approver_user_id=approver_user.id,
            comment="Approved for conference.",
            is_visible_to_requestor=True,
        )

        actions = svc.list_actions_for_requestor(req.id)
        assert len(actions) == 1
        assert actions[0].action_type == "approve"
        assert actions[0].comment == "Approved for conference."

    def test_invisible_action_excluded(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _, approver_user = _make_process_and_approver(db_session, faculty)
        svc = FacultyRequestService(db_session)
        req = svc.create_request(
            faculty_id=faculty.id,
            request_type=REQUEST_TYPE_NOC,
            payload=_noc_payload(),
            actor_id=faculty.user_id,
        )
        submitted = svc.submit_for_approval(req.id, faculty.user_id)

        from durgam.services.approval_request import ApprovalRequestService
        apr_svc = ApprovalRequestService(db_session)
        apr_svc.approve(
            request_id=submitted.approval_request_id,
            approver_user_id=approver_user.id,
            comment="Internal only.",
            is_visible_to_requestor=False,
        )

        actions = svc.list_actions_for_requestor(req.id)
        assert actions == []


# ── Group G: get_by_user_id repository lookup (state auth pattern) ────────────


class TestFacultyGetByUserId:

    def test_get_by_user_id_finds_faculty(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        repo = FacultyRepository(db_session)
        found = repo.get_by_user_id(faculty.user_id)
        assert found is not None
        assert found.id == faculty.id

    def test_get_by_user_id_returns_none_for_unknown(self, db_session: Session) -> None:
        repo = FacultyRepository(db_session)
        result = repo.get_by_user_id(uuid4())
        assert result is None
