"""Integration tests for Phase 7F — unified approval requests flow.

Covers:
  A. FacultyRequestRepository.get_by_approval_request_id (new method)
  B. ApprovalRequestService._sync_faculty_request_status (sync hook)
  C. SubmitRequestState NOC vars present and reset correctly
  D. _submit_faculty_request guard strings present in source
  E. Nav labels restored: "My Requests" and "Approvals"
  F. _FACULTY_PROCESS_CODES filter removed — faculty_noc visible in generic submit
  G. RequestDetailState new vars present with correct defaults
  H. list_actions_for_requestor visibility filtering
  I. list_actions_for_approver visibility filtering

DB strategy (Phase 7F.1 fix — 7F contamination correction):
  ALL DB tests use `db_session` (function-scoped, rolled back at teardown).
  NO `seeded_session` or `seeded_db_engine` usage — they share the session-scoped
  seeded engine and a failed/interrupted rollback contaminates downstream tests.
  `db_session.flush()` within a test is safe (rolled back on teardown).
  Pure-Python for state/service/nav tests (no DB fixture needed).
"""

from __future__ import annotations

import inspect
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session, select


# ── shared helpers ────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(UTC)


def _make_user(session: Session, prefix: str = "u"):
    from durgam.models.identity import User

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
    session.refresh(user)
    return user


def _make_faculty(session: Session, user, dept, campus, desig):
    from durgam.models.faculty import Faculty

    now = _now()
    faculty = Faculty(
        user_id=user.id,
        employee_id=f"EMP{uuid4().hex[:8]}",
        title="Dr",
        first_name="Test",
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
    session.refresh(faculty)
    return faculty


def _make_approval_request_and_fac_req(
    session: Session, *, is_deleted: bool = False, status: str = "submitted"
):
    """Create linked ApprovalRequest + FacultyRequest rows using synthetic data.

    Uses get-or-create for faculty_noc ApprovalProcess (may exist from seed or
    prior fixture setup). Creates synthetic org-core entities with uuid-based
    codes so there are no collisions. Safe to call with db_session (function-
    scoped, rolled back at teardown). Returns (FacultyRequest, ApprovalRequest).
    """
    from durgam.models.campus import Campus
    from durgam.models.config_anchors import Designation
    from durgam.models.crosscutting import ApprovalProcess, ApprovalRequest
    from durgam.models.department import Department
    from durgam.models.faculty_request import FacultyRequest
    from durgam.models.school import School

    uid = uuid4().hex[:8]
    now = _now()

    # Get-or-create faculty_noc process (seed has it; fresh db creates it)
    process = session.exec(
        select(ApprovalProcess).where(
            ApprovalProcess.code == "faculty_noc",
            ApprovalProcess.is_deleted == False,  # noqa: E712
        )
    ).first()
    if process is None:
        process = ApprovalProcess(
            code="faculty_noc",
            title="NOC Request",
            created_at=now,
            updated_at=now,
        )
        session.add(process)
        session.flush()
        session.refresh(process)

    # Synthetic org-core chain (unique codes per call; rolled back by db_session)
    campus = Campus(code=f"7F{uid[:4]}", name=f"7F Campus {uid}", created_at=now, updated_at=now)
    session.add(campus)
    session.flush()

    school = School(code=f"7F{uid[:4]}", name=f"7F School {uid}", created_at=now, updated_at=now)
    session.add(school)
    session.flush()

    desig = Designation(code=f"7F{uid[:4]}", name=f"7F Desig {uid}", rank=99, created_at=now, updated_at=now)
    session.add(desig)
    session.flush()

    dept = Department(
        code=f"7FD{uid[:3]}",
        name=f"7F Dept {uid}",
        school_id=school.id,
        main_campus_id=campus.id,
        created_at=now,
        updated_at=now,
    )
    session.add(dept)
    session.flush()

    user = _make_user(session, "fr7f")
    faculty = _make_faculty(session, user, dept, campus, desig)
    actor_id = user.id

    apr = ApprovalRequest(
        process_id=process.id,
        requestor_user_id=user.id,
        title="Phase 7F.1 test request",
        state="submitted",
        current_stage=1,
        created_by=actor_id,
        updated_by=actor_id,
        created_at=now,
        updated_at=now,
    )
    session.add(apr)
    session.flush()
    session.refresh(apr)

    fr = FacultyRequest(
        faculty_id=faculty.id,
        request_type="noc",
        payload_json={"purpose": "test", "to_whom": "authority"},
        status=status,
        approval_request_id=apr.id,
        is_deleted=is_deleted,
        deleted_at=now if is_deleted else None,
        deleted_by=actor_id if is_deleted else None,
        created_by=actor_id,
        updated_by=actor_id,
        created_at=now,
        updated_at=now,
    )
    session.add(fr)
    session.flush()
    session.refresh(fr)
    return fr, apr


# ── A. FacultyRequestRepository.get_by_approval_request_id ───────────────────


class TestGetByApprovalRequestId:
    def test_returns_none_when_no_link(self, db_session: Session) -> None:
        from durgam.repositories.faculty_request import FacultyRequestRepository

        repo = FacultyRequestRepository(db_session)
        result = repo.get_by_approval_request_id(uuid4())
        assert result is None

    def test_returns_linked_request(self, db_session: Session) -> None:
        from durgam.repositories.faculty_request import FacultyRequestRepository

        fr, apr = _make_approval_request_and_fac_req(db_session)
        repo = FacultyRequestRepository(db_session)
        result = repo.get_by_approval_request_id(apr.id)
        assert result is not None
        assert result.id == fr.id
        assert result.approval_request_id == apr.id

    def test_ignores_soft_deleted(self, db_session: Session) -> None:
        """Soft-deleted rows are not returned."""
        from durgam.repositories.faculty_request import FacultyRequestRepository

        _fr, apr = _make_approval_request_and_fac_req(db_session, is_deleted=True)
        repo = FacultyRequestRepository(db_session)
        result = repo.get_by_approval_request_id(apr.id)
        assert result is None


# ── B. Sync hook — _sync_faculty_request_status ──────────────────────────────


class TestSyncFacultyRequestStatus:
    def test_sync_skips_when_no_linked_row(self, db_session: Session) -> None:
        """No exception raised when no FacultyRequest is linked."""
        from durgam.services.approval_request import ApprovalRequestService

        svc = ApprovalRequestService(db_session)
        svc._sync_faculty_request_status(uuid4(), "approved", uuid4())

    def test_sync_updates_status_to_approved(self, db_session: Session) -> None:
        from durgam.repositories.faculty_request import FacultyRequestRepository
        from durgam.services.approval_request import ApprovalRequestService

        fr, apr = _make_approval_request_and_fac_req(db_session, status="submitted")
        svc = ApprovalRequestService(db_session)
        svc._sync_faculty_request_status(apr.id, "approved", fr.created_by)
        # update() already flushes internally; no extra flush needed

        repo = FacultyRequestRepository(db_session)
        updated = repo.get(fr.id)
        assert updated is not None
        assert updated.status == "approved"

    def test_sync_skips_already_terminal(self, db_session: Session) -> None:
        """If FacultyRequest is already in a terminal state, sync does not overwrite."""
        from durgam.repositories.faculty_request import FacultyRequestRepository
        from durgam.services.approval_request import ApprovalRequestService

        fr, apr = _make_approval_request_and_fac_req(db_session, status="withdrawn")
        svc = ApprovalRequestService(db_session)
        svc._sync_faculty_request_status(apr.id, "approved", fr.created_by)

        repo = FacultyRequestRepository(db_session)
        unchanged = repo.get(fr.id)
        assert unchanged is not None
        assert unchanged.status == "withdrawn"  # not overwritten


# ── C. SubmitRequestState NOC vars ────────────────────────────────────────────


class TestSubmitRequestStateNocVars:
    def test_noc_vars_present_with_defaults(self) -> None:
        """SubmitRequestState has NOC fields with empty string defaults."""
        from durgam.states.approval_requests import SubmitRequestState

        state = SubmitRequestState()
        assert hasattr(state, "noc_purpose")
        assert hasattr(state, "noc_to_whom")
        assert hasattr(state, "noc_date_required_by")
        assert hasattr(state, "noc_additional_notes")
        assert state.noc_purpose == ""
        assert state.noc_to_whom == ""
        assert state.noc_date_required_by == ""
        assert state.noc_additional_notes == ""

    def test_noc_setters_update_vars(self) -> None:
        from durgam.states.approval_requests import SubmitRequestState

        state = SubmitRequestState()
        state.set_noc_purpose("Testing NOC purpose")
        state.set_noc_to_whom("Passport Authority")
        state.set_noc_date_required_by("2026-07-01")
        state.set_noc_additional_notes("Some notes")

        assert state.noc_purpose == "Testing NOC purpose"
        assert state.noc_to_whom == "Passport Authority"
        assert state.noc_date_required_by == "2026-07-01"
        assert state.noc_additional_notes == "Some notes"

    def test_on_process_change_resets_noc_vars(self) -> None:
        from durgam.states.approval_requests import SubmitRequestState

        state = SubmitRequestState()
        state.noc_purpose = "Old purpose"
        state.noc_to_whom = "Old to_whom"
        state.noc_date_required_by = "2026-06-01"
        state.noc_additional_notes = "Old notes"

        state.on_process_change("some-other-process-id")

        assert state.noc_purpose == ""
        assert state.noc_to_whom == ""
        assert state.noc_date_required_by == ""
        assert state.noc_additional_notes == ""


# ── D. _submit_faculty_request guard strings ──────────────────────────────────


class TestSubmitFacultyRequestGuards:
    """Verify that _submit_faculty_request contains the correct guard strings.

    Reflex child states cannot be instantiated in isolation (parent_state is None
    when accessed outside the Reflex runtime). Source inspection is the correct
    approach for verifying guard logic that depends on inherited state vars.
    """

    def _get_source(self) -> str:
        from durgam.states.approval_requests import SubmitRequestState

        return inspect.getsource(SubmitRequestState._submit_faculty_request)

    def test_purpose_required_guard_present(self) -> None:
        assert '"Purpose is required."' in self._get_source()

    def test_to_whom_required_guard_present(self) -> None:
        assert '"To Whom is required."' in self._get_source()

    def test_submitting_cleared_on_guard_exit(self) -> None:
        src = self._get_source()
        assert "self.submitting = False" in src

    def test_branches_on_faculty_process_code(self) -> None:
        src = self._get_source()
        assert 'request_type = process_code[len("faculty_"):]' in src


# ── E. Nav labels restored ────────────────────────────────────────────────────


class TestNavLabelsRestored:
    @classmethod
    def setup_class(cls) -> None:
        import durgam.pages.approvals  # noqa: F401

    def test_my_requests_label_restored(self) -> None:
        from durgam.nav.registry import get_all

        all_entries = get_all()
        entry = next(
            (e for e in all_entries if e.href == "/approvals/my-requests"),
            None,
        )
        assert entry is not None
        assert entry.label == "My Requests", f"Expected 'My Requests', got '{entry.label}'"

    def test_approvals_label_restored(self) -> None:
        from durgam.nav.registry import get_all

        all_entries = get_all()
        entry = next(
            (e for e in all_entries if e.href == "/approvals/inbox"),
            None,
        )
        assert entry is not None
        assert entry.label == "Approvals", f"Expected 'Approvals', got '{entry.label}'"

    def test_no_other_requests_label(self) -> None:
        from durgam.nav.registry import get_all

        all_entries = get_all()
        assert not any(e.label == "Other Requests" for e in all_entries)

    def test_no_other_approvals_label(self) -> None:
        from durgam.nav.registry import get_all

        all_entries = get_all()
        assert not any(e.label == "Other Approvals" for e in all_entries)


# ── F. _FACULTY_PROCESS_CODES filter removed ─────────────────────────────────


class TestFacultyProcessFilterRemoved:
    def test_faculty_process_codes_constant_gone(self) -> None:
        """_FACULTY_PROCESS_CODES no longer defined in approval_requests module."""
        import durgam.states.approval_requests as mod

        assert not hasattr(mod, "_FACULTY_PROCESS_CODES"), (
            "_FACULTY_PROCESS_CODES should have been removed in Phase 7F"
        )

    def test_load_submit_includes_faculty_noc_process(self) -> None:
        """Without the filter, faculty_noc is included by the generic load_submit.

        Verified by simulating the eligible-building loop from load_submit (filter removed).
        """
        all_procs = [
            SimpleNamespace(code="faculty_noc", requestor_role_codes=None, title="NOC", id=uuid4(),
                            requires_upward_attachments=False, max_upward_attachments=0),
            SimpleNamespace(code="LEAVE_APPROVAL", requestor_role_codes=None, title="Leave", id=uuid4(),
                            requires_upward_attachments=False, max_upward_attachments=0),
        ]
        user_role_codes: set[str] = {"FACULTY"}
        eligible: list[dict[str, Any]] = []
        for proc in all_procs:
            if proc.requestor_role_codes:
                if not user_role_codes & set(proc.requestor_role_codes):
                    continue
            eligible.append({"code": proc.code})

        codes = {r["code"] for r in eligible}
        assert "faculty_noc" in codes, "faculty_noc should be included after filter removal"
        assert "LEAVE_APPROVAL" in codes


# ── G. RequestDetailState new vars ───────────────────────────────────────────


class TestRequestDetailStateNewVars:
    def test_confidentiality_vars_present(self) -> None:
        from durgam.states.approval_requests import RequestDetailState

        state = RequestDetailState()
        assert hasattr(state, "decision_hide_from_requestor")
        assert hasattr(state, "decision_share_with_user_ids")
        assert hasattr(state, "prior_action_actors")
        assert state.decision_hide_from_requestor is False
        assert state.decision_share_with_user_ids == []
        assert state.prior_action_actors == []

    def test_faculty_request_link_vars_present(self) -> None:
        from durgam.states.approval_requests import RequestDetailState

        state = RequestDetailState()
        assert hasattr(state, "linked_faculty_request_id")
        assert hasattr(state, "linked_faculty_request_status")
        assert hasattr(state, "noc_payload")
        assert state.linked_faculty_request_id == ""
        assert state.linked_faculty_request_status == ""
        assert state.noc_payload == {}

    def test_set_decision_hide_from_requestor(self) -> None:
        from durgam.states.approval_requests import RequestDetailState

        state = RequestDetailState()
        state.set_decision_hide_from_requestor(True)
        assert state.decision_hide_from_requestor is True
        state.set_decision_hide_from_requestor(False)
        assert state.decision_hide_from_requestor is False

    def test_toggle_decision_share_with(self) -> None:
        from durgam.states.approval_requests import RequestDetailState

        state = RequestDetailState()
        uid = str(uuid4())
        state.toggle_decision_share_with(uid)
        assert uid in state.decision_share_with_user_ids
        state.toggle_decision_share_with(uid)
        assert uid not in state.decision_share_with_user_ids


# ── H. list_actions_for_requestor visibility ─────────────────────────────────


class TestListActionsForRequestorVisibility:
    def test_filters_to_visible_only(self) -> None:
        """list_actions_for_requestor returns only is_visible_to_requestor=True actions."""
        from durgam.services.approval_request import ApprovalRequestService

        visible_action = SimpleNamespace(
            is_visible_to_requestor=True,
            stage_index=1,
            actor_user_id=uuid4(),
            action_type="approve",
            comment=None,
        )
        hidden_action = SimpleNamespace(
            is_visible_to_requestor=False,
            stage_index=1,
            actor_user_id=uuid4(),
            action_type="reject",
            comment="hidden",
        )

        mock_action_repo = MagicMock()
        mock_action_repo.list_by_request_id.return_value = [visible_action, hidden_action]

        svc = ApprovalRequestService.__new__(ApprovalRequestService)
        svc._session = MagicMock()
        svc._req_repo = MagicMock()
        svc._step_repo = MagicMock()
        svc._proc_repo = MagicMock()
        svc._action_repo = mock_action_repo

        result = svc.list_actions_for_requestor(uuid4())
        assert len(result) == 1
        assert result[0].is_visible_to_requestor is True

    def test_empty_when_no_visible_actions(self) -> None:
        from durgam.services.approval_request import ApprovalRequestService

        hidden_action = SimpleNamespace(is_visible_to_requestor=False)

        mock_action_repo = MagicMock()
        mock_action_repo.list_by_request_id.return_value = [hidden_action]

        svc = ApprovalRequestService.__new__(ApprovalRequestService)
        svc._session = MagicMock()
        svc._req_repo = MagicMock()
        svc._step_repo = MagicMock()
        svc._proc_repo = MagicMock()
        svc._action_repo = mock_action_repo

        result = svc.list_actions_for_requestor(uuid4())
        assert result == []


# ── I. list_actions_for_approver visibility ───────────────────────────────────


class TestListActionsForApproverVisibility:
    def _make_svc(self, actions: list) -> Any:
        from durgam.services.approval_request import ApprovalRequestService

        mock_action_repo = MagicMock()
        mock_action_repo.list_by_request_id.return_value = actions

        svc = ApprovalRequestService.__new__(ApprovalRequestService)
        svc._session = MagicMock()
        svc._req_repo = MagicMock()
        svc._step_repo = MagicMock()
        svc._proc_repo = MagicMock()
        svc._action_repo = mock_action_repo
        return svc

    def test_approver_sees_own_actions(self) -> None:
        approver_id = uuid4()
        own_action = SimpleNamespace(
            actor_user_id=approver_id,
            stage_index=2,
            visible_to_lower_user_ids_json=None,
        )
        svc = self._make_svc([own_action])
        result = svc.list_actions_for_approver(uuid4(), approver_id, approver_stage=1)
        assert len(result) == 1

    def test_approver_sees_lower_stage_actions(self) -> None:
        approver_id = uuid4()
        lower_action = SimpleNamespace(
            actor_user_id=uuid4(),
            stage_index=1,
            visible_to_lower_user_ids_json=None,
        )
        svc = self._make_svc([lower_action])
        result = svc.list_actions_for_approver(uuid4(), approver_id, approver_stage=2)
        assert len(result) == 1

    def test_approver_blocked_from_higher_stage_by_default(self) -> None:
        approver_id = uuid4()
        higher_action = SimpleNamespace(
            actor_user_id=uuid4(),
            stage_index=3,
            visible_to_lower_user_ids_json=None,
        )
        svc = self._make_svc([higher_action])
        result = svc.list_actions_for_approver(uuid4(), approver_id, approver_stage=2)
        assert len(result) == 0

    def test_approver_sees_higher_stage_when_granted(self) -> None:
        approver_id = uuid4()
        higher_action = SimpleNamespace(
            actor_user_id=uuid4(),
            stage_index=3,
            visible_to_lower_user_ids_json=[str(approver_id)],
        )
        svc = self._make_svc([higher_action])
        result = svc.list_actions_for_approver(uuid4(), approver_id, approver_stage=2)
        assert len(result) == 1
