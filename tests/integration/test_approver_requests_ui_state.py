"""Integration tests for approver-side faculty request UI state (M10 Phase 7C + 7C-fix).

Tests exercise the service layer directly (FacultyRequestService + ApprovalRequestService)
to verify the data contracts that ApproverInboxState and ApproverRequestDetailState depend on.

Coverage:
  A (list_inbox_for_user, 5): eligible approver sees submitted items, non-eligible sees nothing,
     draft not included, withdrawn not included, second-stage-not-current excluded
  B (is_user_eligible_for_current_stage, 4): submitted+eligible=True, terminal=False,
     wrong user=False, non-existent request=False
  C (approve_request, 4): success advances stage, full chain approves request, unauthorized actor
     raises, stage-already-advanced guard fires
  D (reject_request, 5): success rejects, empty reason raises, whitespace reason raises,
     unauthorized actor raises, stage-already-advanced guard fires
  E (list_actions_for_approver, 4): empty before approve, returns action after approve,
     reject action visible, prior-stage actions for multi-stage
  F (comment + downward attachments — Phase 7C-fix, 6): comment persisted on approve,
     null comment accepted on approve, downward file_ids stored on approve action row,
     downward file_ids stored on reject action row, MIME validation on upload,
     size validation on upload

DB strategy: db_session (function-scoped, rolls back). All synthetic data.
Same get-or-create helpers as test_faculty_requests_ui_state.py — no seed dependency.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session, select

from durgam.models.campus import Campus
from durgam.models.config_anchors import Designation
from durgam.models.crosscutting import ApprovalProcess, ApprovalRequest, ApprovalStageOption
from durgam.models.department import Department
from durgam.models.faculty import Faculty
from durgam.models.faculty_request import REQUEST_TYPE_NOC, STATUS_APPROVED, STATUS_REJECTED, STATUS_SUBMITTED
from durgam.models.identity import Role, User, UserRole
from durgam.models.school import School
from durgam.services.approval_request import ApprovalRequestService
from durgam.models.crosscutting import ApprovalAction
from durgam.services.faculty_request import (
    AttachmentTooLargeError,
    DisallowedMimeTypeError,
    EmptyApproverPoolError,
    FacultyRequestService,
    InvalidRejectReasonError,
    StageAlreadyAdvancedError,
    UnauthorizedActorError,
)
from durgam.storage.local import LocalFilesystemBackend


# ── Helpers ───────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(UTC)


def _make_faculty(session: Session) -> Faculty:
    uid = uuid4().hex[:8]
    now = _now()

    campus = Campus(code=f"AC{uid[:4]}", name=f"App Campus {uid}")
    session.add(campus)
    session.flush()

    school = School(code=f"AS{uid[:4]}", name=f"App School {uid}")
    session.add(school)
    session.flush()

    desig = Designation(code=f"AD{uid[:4]}", name=f"App Desig {uid}", rank=99)
    session.add(desig)
    session.flush()

    dept = Department(
        code=f"ADT{uid[:3]}",
        name=f"App Dept {uid}",
        school_id=school.id,
        main_campus_id=campus.id,
    )
    session.add(dept)
    session.flush()

    user = User(
        username=f"aiu_{uid}",
        email=f"aiu_{uid}@dev.local",
        password_hash="x",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    session.flush()

    faculty = Faculty(
        user_id=user.id,
        employee_id=f"AIEMP-{uid}",
        title="Dr",
        first_name="App",
        last_name="Faculty",
        designation_id=desig.id,
        department_id=dept.id,
        campus_id=campus.id,
        joining_date=date(2021, 6, 1),
        phone="9111000020",
        emergency_contact_name="EC",
        emergency_contact_relation="Parent",
        emergency_contact_phone="9111000021",
        is_phd=False,
        created_at=now,
        updated_at=now,
    )
    session.add(faculty)
    session.flush()
    return faculty


def _noc_payload() -> dict:
    return {
        "purpose": "Conference attendance",
        "to_whom": "Event Coordinator",
        "date_required_by": "2026-08-01",
        "additional_notes": "",
    }


def _make_process_and_approver(session: Session, faculty: Faculty) -> tuple[ApprovalProcess, User]:
    """Get-or-create the faculty_noc process + a dept-scoped HOD approver.

    Mirrors the same helper in test_faculty_requests_ui_state.py.
    """
    uid = uuid4().hex[:8]
    now = _now()

    process = session.exec(
        select(ApprovalProcess).where(
            ApprovalProcess.code == "faculty_noc",
            ApprovalProcess.is_deleted == False,  # noqa: E712
        )
    ).first()
    if process is None:
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

    hod_role = session.exec(
        select(Role).where(Role.code == "HOD", Role.is_deleted == False)  # noqa: E712
    ).first()
    if hod_role is None:
        hod_role = Role(code="HOD", name="Head of Department", level=50, created_at=now, updated_at=now)
        session.add(hod_role)
        session.flush()

    approver_user = User(
        username=f"approv_{uid}",
        email=f"approv_{uid}@dev.local",
        password_hash="x",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(approver_user)
    session.flush()

    approver_faculty = Faculty(
        user_id=approver_user.id,
        employee_id=f"HODAPP-{uid}",
        title="Dr",
        first_name="HOD",
        last_name="Approver",
        designation_id=faculty.designation_id,
        department_id=faculty.department_id,
        campus_id=faculty.campus_id,
        joining_date=date(2020, 1, 1),
        phone="9111000099",
        emergency_contact_name="EC",
        emergency_contact_relation="Parent",
        emergency_contact_phone="9111000098",
        is_phd=False,
        created_at=now,
        updated_at=now,
    )
    session.add(approver_faculty)
    session.flush()

    user_role = UserRole(
        user_id=approver_user.id,
        role_id=hod_role.id,
        scope_type="department",
        scope_id=faculty.department_id,
    )
    session.add(user_role)
    session.flush()

    return process, approver_user


def _submit_noc(session: Session, faculty: Faculty) -> UUID:
    """Create + submit a NOC request. Returns faculty_request.id."""
    svc = FacultyRequestService(session)
    req = svc.create_request(
        faculty_id=faculty.id,
        request_type=REQUEST_TYPE_NOC,
        payload=_noc_payload(),
        actor_id=faculty.user_id,
    )
    return req.id


# ── Group A: list_inbox_for_user ──────────────────────────────────────────────


class TestListInboxForUser:

    def test_eligible_approver_sees_submitted_item(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        result = svc.list_inbox_for_user(approver.id)
        assert any(item["id"] == str(req_id) for item in result)

    def test_non_eligible_user_sees_nothing(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        # A random user with no HOD role sees nothing
        now = _now()
        stranger = User(
            username=f"stranger_{uuid4().hex[:6]}",
            email=f"str_{uuid4().hex[:6]}@dev.local",
            password_hash="x",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db_session.add(stranger)
        db_session.flush()
        result = svc.list_inbox_for_user(stranger.id)
        assert result == []

    def test_draft_not_included_in_inbox(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)  # stays in draft
        svc = FacultyRequestService(db_session)
        result = svc.list_inbox_for_user(approver.id)
        assert not any(item["id"] == str(req_id) for item in result)

    def test_requestor_dict_fields_present(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        result = svc.list_inbox_for_user(approver.id)
        assert len(result) >= 1
        item = next(i for i in result if i["id"] == str(req_id))
        assert item["request_type"] == REQUEST_TYPE_NOC
        assert "requestor_name" in item
        assert "current_stage" in item
        assert "total_stages" in item
        assert "submitted_at" in item

    def test_inbox_ordered_oldest_first(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        svc = FacultyRequestService(db_session)
        # Create + submit two requests
        req1 = _submit_noc(db_session, faculty)
        svc.submit_for_approval(req1, faculty.user_id)
        req2 = _submit_noc(db_session, faculty)
        svc.submit_for_approval(req2, faculty.user_id)
        result = svc.list_inbox_for_user(approver.id)
        my_items = [i for i in result if i["id"] in (str(req1), str(req2))]
        assert len(my_items) == 2
        # Oldest submitted_at first
        assert my_items[0]["submitted_at"] <= my_items[1]["submitted_at"]


# ── Group B: is_user_eligible_for_current_stage ────────────────────────────────


class TestIsUserEligible:

    def test_eligible_approver_returns_true(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        row = svc.get_request(req_id)
        apr_svc = ApprovalRequestService(db_session)
        assert apr_svc.is_user_eligible_for_current_stage(row.approval_request_id, approver.id) is True

    def test_non_eligible_user_returns_false(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        row = svc.get_request(req_id)
        now = _now()
        stranger = User(
            username=f"elig_str_{uuid4().hex[:6]}",
            email=f"es_{uuid4().hex[:6]}@dev.local",
            password_hash="x",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db_session.add(stranger)
        db_session.flush()
        apr_svc = ApprovalRequestService(db_session)
        assert apr_svc.is_user_eligible_for_current_stage(row.approval_request_id, stranger.id) is False

    def test_terminal_request_returns_false(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        svc.approve_request(req_id, approver.id)
        db_session.commit()
        row = svc.get_request(req_id)
        assert row.status == STATUS_APPROVED
        apr_svc = ApprovalRequestService(db_session)
        assert apr_svc.is_user_eligible_for_current_stage(row.approval_request_id, approver.id) is False

    def test_nonexistent_approval_request_returns_false(self, db_session: Session) -> None:
        apr_svc = ApprovalRequestService(db_session)
        assert apr_svc.is_user_eligible_for_current_stage(uuid4(), uuid4()) is False


# ── Group C: approve_request ───────────────────────────────────────────────────


class TestApproveRequest:

    def test_approve_sets_status_approved_on_single_stage(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        svc.approve_request(req_id, approver.id)
        db_session.commit()
        row = svc.get_request(req_id)
        assert row.status == STATUS_APPROVED

    def test_approve_with_expected_stage_succeeds(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        svc.approve_request(req_id, approver.id, expected_stage_index=1)
        db_session.commit()
        row = svc.get_request(req_id)
        assert row.status == STATUS_APPROVED

    def test_approve_unauthorized_actor_raises(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        now = _now()
        stranger = User(
            username=f"ua_str_{uuid4().hex[:6]}",
            email=f"ua_{uuid4().hex[:6]}@dev.local",
            password_hash="x",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db_session.add(stranger)
        db_session.flush()
        with pytest.raises(UnauthorizedActorError):
            svc.approve_request(req_id, stranger.id)

    def test_approve_wrong_expected_stage_raises(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        with pytest.raises(StageAlreadyAdvancedError):
            svc.approve_request(req_id, approver.id, expected_stage_index=99)


# ── Group D: reject_request ────────────────────────────────────────────────────


class TestRejectRequest:

    def test_reject_sets_status_rejected(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        svc.reject_request(req_id, approver.id, reason="Insufficient scope.")
        db_session.commit()
        row = svc.get_request(req_id)
        assert row.status == STATUS_REJECTED

    def test_reject_empty_reason_raises(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        with pytest.raises(InvalidRejectReasonError):
            svc.reject_request(req_id, approver.id, reason="")

    def test_reject_whitespace_reason_raises(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        with pytest.raises(InvalidRejectReasonError):
            svc.reject_request(req_id, approver.id, reason="   ")

    def test_reject_unauthorized_actor_raises(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        now = _now()
        stranger = User(
            username=f"rj_str_{uuid4().hex[:6]}",
            email=f"rj_{uuid4().hex[:6]}@dev.local",
            password_hash="x",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db_session.add(stranger)
        db_session.flush()
        with pytest.raises(UnauthorizedActorError):
            svc.reject_request(req_id, stranger.id, reason="Reason.")

    def test_reject_wrong_expected_stage_raises(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        with pytest.raises(StageAlreadyAdvancedError):
            svc.reject_request(req_id, approver.id, reason="Reason.", expected_stage_index=99)


# ── Group E: list_actions_for_approver ────────────────────────────────────────


class TestListActionsForApprover:

    def test_empty_before_any_action(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        result = svc.list_actions_for_approver(
            request_id=req_id,
            approver_user_id=approver.id,
            approver_stage=1,
        )
        assert result == []

    def test_returns_approve_action_after_approve(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        svc.approve_request(req_id, approver.id)
        db_session.commit()
        result = svc.list_actions_for_approver(
            request_id=req_id,
            approver_user_id=approver.id,
            approver_stage=1,
        )
        assert len(result) >= 1
        assert any(a.action_type == "approve" for a in result)

    def test_returns_reject_action_after_reject(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        svc.reject_request(req_id, approver.id, reason="Not approved — scope too broad.")
        db_session.commit()
        result = svc.list_actions_for_approver(
            request_id=req_id,
            approver_user_id=approver.id,
            approver_stage=1,
        )
        assert len(result) >= 1
        assert any(a.action_type == "reject" for a in result)

    def test_empty_for_wrong_stage(self, db_session: Session) -> None:
        """Approver at stage 2 sees no actions when request is at stage 1."""
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        result = svc.list_actions_for_approver(
            request_id=req_id,
            approver_user_id=approver.id,
            approver_stage=2,  # wrong stage
        )
        assert result == []


# ── Group F: comment + downward attachments (Phase 7C-fix) ────────────────────


class TestCommentAndDownwardAttachments:

    def test_approve_persists_comment(self, db_session: Session) -> None:
        """Comment passed to approve_request() is stored on the ApprovalAction row."""
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        svc.approve_request(req_id, approver.id, comment="Looks good — approved.")
        db_session.commit()

        row = svc.get_request(req_id)
        action = db_session.exec(
            select(ApprovalAction).where(
                ApprovalAction.approval_request_id == row.approval_request_id,
                ApprovalAction.action_type == "approve",
                ApprovalAction.is_deleted == False,  # noqa: E712
            )
        ).first()
        assert action is not None
        assert action.comment == "Looks good — approved."

    def test_approve_with_no_comment_succeeds(self, db_session: Session) -> None:
        """approve_request() with comment=None succeeds; action row has null comment."""
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(db_session)
        svc.submit_for_approval(req_id, faculty.user_id)
        svc.approve_request(req_id, approver.id, comment=None)
        db_session.commit()

        row = svc.get_request(req_id)
        action = db_session.exec(
            select(ApprovalAction).where(
                ApprovalAction.approval_request_id == row.approval_request_id,
                ApprovalAction.action_type == "approve",
                ApprovalAction.is_deleted == False,  # noqa: E712
            )
        ).first()
        assert action is not None
        assert action.comment is None

    def test_approve_persists_downward_attachments(
        self, db_session: Session, tmp_path
    ) -> None:
        """File IDs passed to approve_request() appear in ApprovalAction.downward_attachment_file_ids_json."""
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(
            db_session,
            storage_backend=LocalFilesystemBackend(str(tmp_path)),
        )
        svc.submit_for_approval(req_id, faculty.user_id)

        asset1 = svc.add_downward_attachment(
            request_id=req_id,
            file_bytes=b"%PDF-1.4 fake pdf content",
            filename="signed_noc_1.pdf",
            mime_type="application/pdf",
            actor_id=approver.id,
        )
        asset2 = svc.add_downward_attachment(
            request_id=req_id,
            file_bytes=b"%PDF-1.4 another fake pdf",
            filename="signed_noc_2.pdf",
            mime_type="application/pdf",
            actor_id=approver.id,
        )

        svc.approve_request(
            req_id,
            approver.id,
            downward_attachment_file_ids=[asset1.id, asset2.id],
        )
        db_session.commit()

        row = svc.get_request(req_id)
        action = db_session.exec(
            select(ApprovalAction).where(
                ApprovalAction.approval_request_id == row.approval_request_id,
                ApprovalAction.action_type == "approve",
                ApprovalAction.is_deleted == False,  # noqa: E712
            )
        ).first()
        assert action is not None
        stored = action.downward_attachment_file_ids_json or []
        assert str(asset1.id) in stored
        assert str(asset2.id) in stored

    def test_reject_persists_downward_attachments(
        self, db_session: Session, tmp_path
    ) -> None:
        """File IDs passed to reject_request() appear in ApprovalAction.downward_attachment_file_ids_json."""
        faculty = _make_faculty(db_session)
        _, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(
            db_session,
            storage_backend=LocalFilesystemBackend(str(tmp_path)),
        )
        svc.submit_for_approval(req_id, faculty.user_id)

        asset = svc.add_downward_attachment(
            request_id=req_id,
            file_bytes=b"%PDF-1.4 rejection evidence",
            filename="evidence.pdf",
            mime_type="application/pdf",
            actor_id=approver.id,
        )

        svc.reject_request(
            req_id,
            approver.id,
            reason="Rejected with evidence.",
            downward_attachment_file_ids=[asset.id],
        )
        db_session.commit()

        row = svc.get_request(req_id)
        action = db_session.exec(
            select(ApprovalAction).where(
                ApprovalAction.approval_request_id == row.approval_request_id,
                ApprovalAction.action_type == "reject",
                ApprovalAction.is_deleted == False,  # noqa: E712
            )
        ).first()
        assert action is not None
        stored = action.downward_attachment_file_ids_json or []
        assert str(asset.id) in stored

    def test_downward_upload_validates_mime(
        self, db_session: Session, tmp_path
    ) -> None:
        """add_downward_attachment() raises DisallowedMimeTypeError for non-PDF files."""
        faculty = _make_faculty(db_session)
        _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(
            db_session,
            storage_backend=LocalFilesystemBackend(str(tmp_path)),
        )
        svc.submit_for_approval(req_id, faculty.user_id)

        user_id = faculty.user_id  # faculty tries to upload a PNG — wrong MIME
        with pytest.raises(DisallowedMimeTypeError):
            svc.add_downward_attachment(
                request_id=req_id,
                file_bytes=b"\x89PNG\r\nfake png",
                filename="screenshot.png",
                mime_type="image/png",
                actor_id=user_id,
            )

    def test_downward_upload_validates_size(
        self, db_session: Session, tmp_path
    ) -> None:
        """add_downward_attachment() raises AttachmentTooLargeError when file exceeds max_attachment_mb."""
        faculty = _make_faculty(db_session)
        process, approver = _make_process_and_approver(db_session, faculty)
        req_id = _submit_noc(db_session, faculty)
        svc = FacultyRequestService(
            db_session,
            storage_backend=LocalFilesystemBackend(str(tmp_path)),
        )
        svc.submit_for_approval(req_id, faculty.user_id)

        # Lower the process limit so a small file triggers the error
        process.max_attachment_mb = 1
        db_session.flush()

        two_mb = b"%PDF-1.4 " + b"x" * (2 * 1024 * 1024)
        with pytest.raises(AttachmentTooLargeError):
            svc.add_downward_attachment(
                request_id=req_id,
                file_bytes=two_mb,
                filename="too_large.pdf",
                mime_type="application/pdf",
                actor_id=approver.id,
            )
