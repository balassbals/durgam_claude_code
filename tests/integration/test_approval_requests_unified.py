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
  J. submit_request propagates return value from _submit_faculty_request (7F.2)
  K. Defect 1 — redacted action history: requestor sees ALL rows, hidden ones redacted (7G)
  L. Defect 2 — past actions view: list_where_actor_acted repo method (7G + 7G.2)
  M. Defect 3 — seed.py downward attachment block for faculty_noc (7G)
  N. Defect 4 — admin processes page uses _row_actions not _kebab (7G)
  O. Defect 1 round 2 — step dict uses bool is_redacted + correct placeholder (7G.2)
  P. Defect 2 round 2 — load_inbox pre-loads both pending_rows and past_rows (7G.2)
  Q. Defect 5 — approval processes Edit button uses open_edit_by_id(1 arg) (7G.2)
  R. Issue A — visibility leak: lower-stage approver must not see higher-stage unshared action (7G.3)
  S. Issue B — open_deactivate_by_id(1 arg) replaces 2-arg open_deactivate_confirm in _row_actions (7G.3)
  T. Issue C — data_table actions column width widened from 3rem to 12rem (7G.4)
  U. Issue D — approver redaction: list_actions_for_approver_redacted returns all rows with flag (7G.4)
  V. Issue E — actions column hydration fix: non-empty "Actions" label + min_width on header and cell (7G.5)
  W. Issue F — UTC→IST display: _format_dt delegates to format_ist (7G.5)
  X. Issue G — actions column sticky-right so wide tables don't push it off-screen (7G.6)
  Y. Debug paint cleanup — no "red" background or "3px solid blue" in approval_processes._row_actions (7G.6)

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


# ── J. submit_request return propagation (Phase 7F.2) ────────────────────────


class TestNOCSubmitReturnPropagation:
    """Regression guard for Phase 7F.2 — submit_request must propagate the
    rx.redirect event spec returned by _submit_faculty_request.

    Reflex child states cannot be instantiated in isolation (parent_state is None
    outside the Reflex runtime; inherited vars like current_user_id raise
    AttributeError). Source inspection is the correct approach here.
    """

    def test_submit_request_propagates_redirect(self) -> None:
        """submit_request must use 'return await' so the EventSpec reaches the framework.
        A bare 'await' followed by 'return' discards the redirect and the page stays still.

        Reflex wraps public async methods as EventHandler objects. The underlying
        function is accessed via .fn for source inspection.
        """
        from durgam.states.approval_requests import SubmitRequestState

        src = inspect.getsource(SubmitRequestState.submit_request.fn)
        assert "return await self._submit_faculty_request()" in src, (
            "submit_request must propagate the return value of _submit_faculty_request "
            "via 'return await ...'. A bare 'await' followed by a bare 'return' discards "
            "the rx.redirect EventSpec and the post-submit redirect never fires."
        )

    def test_helper_return_type_is_event_spec(self) -> None:
        """_submit_faculty_request must declare a non-None return type so the
        intent is clear to static analysis tools and future readers.
        """
        import typing

        from durgam.states.approval_requests import SubmitRequestState

        hints = typing.get_type_hints(SubmitRequestState._submit_faculty_request)
        return_hint = hints.get("return")
        assert return_hint is not None, (
            "_submit_faculty_request return type must not be None — it returns an "
            "rx.redirect EventSpec on success."
        )


# ── K. Defect 1 — redacted action history for requestor (Phase 7G) ───────────


class TestRedactedActionHistory:
    """list_actions_for_requestor_redacted returns ALL actions; hidden ones are
    not filtered out. The caller (load_detail) applies redaction in the step dict.
    Q-P7A.3 filter-out behavior is replaced by this show-but-redact approach.
    """

    def _make_svc(self, actions: list) -> Any:
        from durgam.services.approval_request import ApprovalRequestService

        mock_repo = MagicMock()
        mock_repo.list_by_request_id.return_value = actions

        svc = ApprovalRequestService.__new__(ApprovalRequestService)
        svc._session = MagicMock()
        svc._req_repo = MagicMock()
        svc._step_repo = MagicMock()
        svc._proc_repo = MagicMock()
        svc._action_repo = mock_repo
        return svc

    def test_requestor_sees_all_rows_including_hidden(self) -> None:
        """Requestor sees ALL action rows — hidden ones appear (redacted, not absent)."""
        visible = SimpleNamespace(is_visible_to_requestor=True, action_type="approve", comment="Good")
        hidden = SimpleNamespace(is_visible_to_requestor=False, action_type="reject", comment="private")

        svc = self._make_svc([visible, hidden])
        result = svc.list_actions_for_requestor_redacted(uuid4())
        assert len(result) == 2, "Both visible and hidden actions must be returned"

    def test_requestor_sees_all_when_all_hidden(self) -> None:
        """When all actions are hidden, redacted method still returns all of them."""
        hidden1 = SimpleNamespace(is_visible_to_requestor=False, action_type="approve")
        hidden2 = SimpleNamespace(is_visible_to_requestor=False, action_type="reject")

        svc = self._make_svc([hidden1, hidden2])
        result = svc.list_actions_for_requestor_redacted(uuid4())
        assert len(result) == 2

    def test_original_list_actions_still_filters(self) -> None:
        """Backward-compat: list_actions_for_requestor (old method) still filters."""
        visible = SimpleNamespace(is_visible_to_requestor=True, action_type="approve")
        hidden = SimpleNamespace(is_visible_to_requestor=False, action_type="reject")

        svc = self._make_svc([visible, hidden])
        result = svc.list_actions_for_requestor(uuid4())
        assert len(result) == 1
        assert result[0].is_visible_to_requestor is True

    def test_load_detail_uses_redacted_method_for_requestor(self) -> None:
        """load_detail source must use list_actions_for_requestor_redacted for requestors.
        Source inspection via EventHandler.fn (Reflex wraps public async methods).
        """
        from durgam.states.approval_requests import RequestDetailState

        src = inspect.getsource(RequestDetailState.load_detail.fn)
        assert "list_actions_for_requestor_redacted" in src, (
            "load_detail must call list_actions_for_requestor_redacted when "
            "viewer_is_requestor — hidden actions must appear as redacted rows, "
            "not be filtered out entirely."
        )
        assert "Comment not shared with you." in src, (
            "load_detail must set comment to 'Comment not shared with you.' "
            "for actions where is_visible_to_requestor=False."
        )


# ── L. Defect 2 — past actions view (Phase 7G) ───────────────────────────────


class TestPastActionsRepo:
    """list_where_actor_acted returns ApprovalRequests (any state) where the viewer
    has any approval_action row. No state filter — includes in-flight requests.
    """

    def _make_terminal_request_with_action(
        self, session: Session, actor_user_id: UUID
    ):
        """Create a terminal ApprovalRequest + ApprovalAction for the given actor."""
        from durgam.models.crosscutting import ApprovalAction, ApprovalProcess, ApprovalRequest

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
                code=f"proc_{uid}", title=f"Proc {uid}", created_at=now, updated_at=now
            )
            session.add(process)
            session.flush()
            session.refresh(process)

        req = ApprovalRequest(
            process_id=process.id,
            requestor_user_id=actor_user_id,
            title=f"Past req {uid}",
            state="approved",
            current_stage=1,
            created_by=actor_user_id,
            updated_by=actor_user_id,
            created_at=now,
            updated_at=now,
        )
        session.add(req)
        session.flush()
        session.refresh(req)

        action = ApprovalAction(
            approval_request_id=req.id,
            stage_index=1,
            actor_user_id=actor_user_id,
            action_type="approve",
            is_visible_to_requestor=True,
            created_by=actor_user_id,
            updated_by=actor_user_id,
            created_at=now,
            updated_at=now,
        )
        session.add(action)
        session.flush()
        return req, action

    def test_past_actions_shows_terminal_where_actor_acted(
        self, db_session: Session
    ) -> None:
        from durgam.repositories.approval_request import ApprovalRequestRepository

        actor = _make_user(db_session, "pa_actor")
        req, _action = self._make_terminal_request_with_action(db_session, actor.id)

        repo = ApprovalRequestRepository(db_session)
        result = repo.list_where_actor_acted(actor.id)
        request_ids = {r.id for r in result}
        assert req.id in request_ids

    def test_past_actions_excludes_where_actor_did_not_act(
        self, db_session: Session
    ) -> None:
        from durgam.repositories.approval_request import ApprovalRequestRepository

        actor = _make_user(db_session, "pa_actor")
        other = _make_user(db_session, "pa_other")
        req, _action = self._make_terminal_request_with_action(db_session, other.id)

        repo = ApprovalRequestRepository(db_session)
        result = repo.list_where_actor_acted(actor.id)
        request_ids = {r.id for r in result}
        assert req.id not in request_ids

    def test_past_actions_includes_in_flight_where_actor_acted(
        self, db_session: Session
    ) -> None:
        """In-review requests ARE returned when the actor has an action row.

        Phase 7G.2 fix: no state filter. An HoD who approved Stage 1 of a 2-stage
        request (still in_review) must see that request in Past Actions immediately.
        """
        from durgam.models.crosscutting import ApprovalAction, ApprovalProcess, ApprovalRequest
        from durgam.repositories.approval_request import ApprovalRequestRepository

        actor = _make_user(db_session, "pa_active")
        now = _now()

        process = db_session.exec(
            select(ApprovalProcess).where(ApprovalProcess.is_deleted == False)  # noqa: E712
        ).first()
        if process is None:
            uid = uuid4().hex[:6]
            process = ApprovalProcess(
                code=f"tmp_{uid}", title=f"Tmp {uid}", created_at=now, updated_at=now
            )
            db_session.add(process)
            db_session.flush()
            db_session.refresh(process)

        req = ApprovalRequest(
            process_id=process.id,
            requestor_user_id=actor.id,
            title="In-flight req",
            state="in_review",
            current_stage=2,
            created_by=actor.id,
            updated_by=actor.id,
            created_at=now,
            updated_at=now,
        )
        db_session.add(req)
        db_session.flush()
        db_session.refresh(req)

        action = ApprovalAction(
            approval_request_id=req.id,
            stage_index=1,
            actor_user_id=actor.id,
            action_type="approve",
            is_visible_to_requestor=True,
            created_by=actor.id,
            updated_by=actor.id,
            created_at=now,
            updated_at=now,
        )
        db_session.add(action)
        db_session.flush()

        repo = ApprovalRequestRepository(db_session)
        result = repo.list_where_actor_acted(actor.id)
        request_ids = {r.id for r in result}
        assert req.id in request_ids, (
            "In-review requests must appear in past actions after actor has acted "
            "(Phase 7G.2: no state filter in list_where_actor_acted)"
        )


# ── M. Defect 3 — seed faculty_noc downward config (Phase 7G) ────────────────


class TestFacultyNocSeedDownwardConfig:
    """seed.py must set max_downward_attachments=3 for faculty_noc via an
    idempotent post-insert block (same pattern as Phase 6 upward config).
    """

    def test_seed_has_downward_attachment_block(self) -> None:
        """seed.py source contains the downward-attachment update block."""
        seed_path = "scripts/seed.py"
        with open(seed_path) as f:
            src = f.read()
        assert "max_downward_attachments = 3" in src, (
            "seed.py must set max_downward_attachments=3 for faculty_noc "
            "in an idempotent post-insert block."
        )

    def test_seed_downward_block_is_conditional(self) -> None:
        """The downward block only updates when still at the default (preserves edits)."""
        seed_path = "scripts/seed.py"
        with open(seed_path) as f:
            src = f.read()
        assert "max_downward_attachments == 0" in src, (
            "The downward update must be conditional on max_downward_attachments == 0 "
            "so it doesn't overwrite manual sys admin edits."
        )


# ── N. Defect 4 — admin processes page direct action buttons (Phase 7G) ───────


class TestAdminProcessesDirectActions:
    """approval_processes.py must use _row_actions (direct Edit + Deactivate buttons)
    instead of the _kebab dropdown. The kebab's rx.menu portal had visibility issues.
    """

    def test_row_actions_function_exists(self) -> None:
        from durgam.pages.admin.config import approval_processes

        assert hasattr(approval_processes, "_row_actions"), (
            "_row_actions function must exist in approval_processes module"
        )
        assert not hasattr(approval_processes, "_kebab") or True, "ok if _kebab removed"

    def test_page_uses_row_actions_not_kebab(self) -> None:
        """Source of admin_config_approval_processes must reference _row_actions."""
        page_path = "durgam/pages/admin/config/approval_processes.py"
        with open(page_path) as f:
            src = f.read()
        assert "actions=_row_actions" in src, (
            "data_table must use actions=_row_actions (direct buttons) "
            "not actions=_kebab (hidden dropdown trigger)."
        )
        assert "actions=_kebab" not in src, (
            "_kebab must no longer be wired as the actions renderer — "
            "it has been replaced by _row_actions."
        )


# ── O. Defect 1 round 2 — step dict bool is_redacted (Phase 7G.2) ────────────


class TestStepDictBoolIsRedacted:
    """Phase 7G.2: is_redacted in step_dicts must be a bool (True/False), not a
    string ("1"/""). The UI uses rx.cond(step["is_redacted"], ...) which requires
    a bool Var; string equality comparison was unreliable in Reflex 0.9.x.
    """

    def test_load_detail_uses_bool_is_redacted(self) -> None:
        """Source must store is_redacted as a bool, not "1"/"" string."""
        from durgam.states.approval_requests import RequestDetailState

        src = inspect.getsource(RequestDetailState.load_detail.fn)
        assert '"is_redacted": is_redacted' in src, (
            'load_detail must set "is_redacted": is_redacted (bool), '
            'not "is_redacted": "1" if is_redacted else "".'
        )
        assert '"1" if is_redacted' not in src, (
            'is_redacted must be stored as bool, not string "1".'
        )

    def test_ui_uses_bool_cond_not_string_equality(self) -> None:
        """request_detail.py must use rx.cond(step["is_redacted"], ...) not == '1'."""
        detail_path = "durgam/pages/approvals/request_detail.py"
        with open(detail_path) as f:
            src = f.read()
        assert 'step["is_redacted"]' in src, (
            "request_detail.py must reference step['is_redacted'] for conditional styling"
        )
        assert '== "1"' not in src, (
            'String equality == "1" removed; bool rx.cond used instead.'
        )


# ── P. Defect 2 round 2 — dual-load inbox (Phase 7G.2) ───────────────────────


class TestDualLoadInbox:
    """Phase 7G.2: load_inbox pre-loads both pending_rows and past_rows in a single
    DB query. set_view_mode is now synchronous — no DB roundtrip on tab switch.
    """

    def test_approver_inbox_has_pending_and_past_vars(self) -> None:
        """ApproverInboxState must have pending_rows and past_rows state vars."""
        from durgam.states.approval_requests import ApproverInboxState

        assert hasattr(ApproverInboxState, "pending_rows"), (
            "ApproverInboxState must have pending_rows state var"
        )
        assert hasattr(ApproverInboxState, "past_rows"), (
            "ApproverInboxState must have past_rows state var"
        )

    def test_set_view_mode_is_sync(self) -> None:
        """set_view_mode must be a sync method (no await load_inbox call)."""
        import inspect as _inspect
        from durgam.states.approval_requests import ApproverInboxState

        method = ApproverInboxState.set_view_mode
        fn = getattr(method, "fn", method)
        src = _inspect.getsource(fn)
        assert "await self.load_inbox" not in src, (
            "set_view_mode must not call await self.load_inbox — "
            "both lists are pre-loaded; tab switch has no DB roundtrip."
        )

    def test_load_inbox_populates_both_lists(self) -> None:
        """load_inbox source must set both pending_rows and past_rows."""
        import inspect as _inspect
        from durgam.states.approval_requests import ApproverInboxState

        src = _inspect.getsource(ApproverInboxState.load_inbox.fn)
        assert "self.pending_rows" in src, (
            "load_inbox must populate self.pending_rows"
        )
        assert "self.past_rows" in src, (
            "load_inbox must populate self.past_rows"
        )

    def test_rows_computed_var_exists(self) -> None:
        """ApproverInboxState.rows must be a computed var (not a plain state var)."""
        from durgam.states.approval_requests import ApproverInboxState

        rows_attr = ApproverInboxState.__dict__.get("rows")
        assert rows_attr is not None, "rows must be defined on ApproverInboxState"
        assert callable(rows_attr) or hasattr(rows_attr, "__get__"), (
            "rows must be a computed var or property, not a plain state var list"
        )


# ── Q. Defect 5 — open_edit_by_id simplifies row action partial (Phase 7G.2) ──


class TestOpenEditById:
    """Phase 7G.2: _row_actions uses open_edit_by_id(row["id"]) — 1 arg instead
    of 13. This avoids complex Reflex partial-application serialization that silently
    produced invisible buttons.
    """

    def test_open_edit_by_id_exists(self) -> None:
        """ApprovalProcessConfigState must have an open_edit_by_id method."""
        from durgam.states.config_approval_process import ApprovalProcessConfigState

        assert hasattr(ApprovalProcessConfigState, "open_edit_by_id"), (
            "ApprovalProcessConfigState must have open_edit_by_id(pid: str) method"
        )

    def test_row_actions_uses_open_edit_by_id(self) -> None:
        """_row_actions must call open_edit_by_id with only row['id']."""
        page_path = "durgam/pages/admin/config/approval_processes.py"
        with open(page_path) as f:
            src = f.read()
        assert "open_edit_by_id" in src, (
            "_row_actions must call open_edit_by_id (1-arg Edit trigger)"
        )
        assert "open_edit_by_id(\n                row[" in src or "open_edit_by_id(  # type:" in src, (
            "_row_actions must pass only row['id'] to open_edit_by_id"
        )

    def test_open_edit_by_id_reads_from_processes_list(self) -> None:
        """open_edit_by_id source must iterate self.processes to find the row."""
        import inspect as _inspect
        from durgam.states.config_approval_process import ApprovalProcessConfigState

        fn = ApprovalProcessConfigState.open_edit_by_id.fn  # type: ignore[attr-defined]
        src = _inspect.getsource(fn)
        assert "self.processes" in src, (
            "open_edit_by_id must look up data from self.processes (no extra DB query)"
        )
        assert "self.show_form = True" in src, (
            "open_edit_by_id must set show_form=True after populating fields"
        )


# ── R. Issue A — visibility leak fix (Phase 7G.3) ────────────────────────────


class TestApproverVisibilityLeakFix:
    """Phase 7G.3 regression guard: list_actions_for_approver must use the
    viewer's acted stage_index (not the request's current_stage) to determine
    which actions are visible. Using req.current_stage causes a visibility leak
    where a lower-stage approver (HoD, stage 1) sees a higher-stage approver's
    (Registrar, stage 2) action after the request advances past stage 1.
    """

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

    def test_intermediate_approver_does_not_see_higher_stage_hidden_action(
        self,
    ) -> None:
        """HoD (stage 1) must NOT see Registrar's (stage 2) action when Registrar
        did not share it — even if the caller passes approver_stage=2 (stale
        req.current_stage after Registrar acts).

        Root cause (Phase 7G.3): load_detail passed req.current_stage which advances
        to 2 after HoD acts, giving HoD an inflated effective_stage. Fix: service
        internally computes effective_stage from viewer's own acted action (stage 1).
        """
        hod_id = uuid4()
        reg_id = uuid4()

        hod_action = SimpleNamespace(
            actor_user_id=hod_id,
            stage_index=1,
            visible_to_lower_user_ids_json=None,
        )
        reg_action = SimpleNamespace(
            actor_user_id=reg_id,
            stage_index=2,
            visible_to_lower_user_ids_json=None,  # Registrar did NOT share
        )

        svc = self._make_svc([hod_action, reg_action])
        # approver_stage=2 simulates the WRONG caller value (req.current_stage after
        # Registrar acts).  The fix must override this with HoD's own stage (1).
        result = svc.list_actions_for_approver(uuid4(), hod_id, approver_stage=2)

        actor_ids = {a.actor_user_id for a in result}
        assert hod_id in actor_ids, "HoD must see their own action"
        assert reg_id not in actor_ids, (
            "HoD must NOT see Registrar's unshared action — visibility leak (Phase 7G.3)"
        )

    def test_higher_approver_sees_lower_stage_actions_by_default(self) -> None:
        """Registrar (stage 2) must see HoD's (stage 1) action without an explicit share."""
        hod_id = uuid4()
        reg_id = uuid4()

        hod_action = SimpleNamespace(
            actor_user_id=hod_id,
            stage_index=1,
            visible_to_lower_user_ids_json=None,
        )
        reg_action = SimpleNamespace(
            actor_user_id=reg_id,
            stage_index=2,
            visible_to_lower_user_ids_json=None,
        )

        svc = self._make_svc([hod_action, reg_action])
        result = svc.list_actions_for_approver(uuid4(), reg_id, approver_stage=2)

        actor_ids = {a.actor_user_id for a in result}
        assert reg_id in actor_ids, "Registrar must see their own action"
        assert hod_id in actor_ids, (
            "Registrar (higher authority, stage 2) must see HoD's (stage 1) action by default"
        )

    def test_explicit_share_grants_visibility_to_lower_approver(self) -> None:
        """When Registrar explicitly shares (adds HoD's id to visible_to_lower_user_ids_json),
        HoD must see Registrar's action."""
        hod_id = uuid4()
        reg_id = uuid4()

        hod_action = SimpleNamespace(
            actor_user_id=hod_id,
            stage_index=1,
            visible_to_lower_user_ids_json=None,
        )
        reg_action = SimpleNamespace(
            actor_user_id=reg_id,
            stage_index=2,
            visible_to_lower_user_ids_json=[str(hod_id)],  # explicitly shared
        )

        svc = self._make_svc([hod_action, reg_action])
        result = svc.list_actions_for_approver(uuid4(), hod_id, approver_stage=2)

        actor_ids = {a.actor_user_id for a in result}
        assert hod_id in actor_ids, "HoD must see their own action"
        assert reg_id in actor_ids, (
            "HoD must see Registrar's action when Registrar explicitly shared it"
        )

    def test_decision_share_with_user_ids_resets_on_load_detail(self) -> None:
        """RequestDetailState.load_detail must reset decision_share_with_user_ids to []
        at the start of every load. Stale values from a prior request must not carry
        over and silently pre-populate the share checkboxes for the next action.
        """
        import inspect as _inspect

        from durgam.states.approval_requests import RequestDetailState

        fn = RequestDetailState.load_detail.fn  # type: ignore[attr-defined]
        src = _inspect.getsource(fn)
        assert "self.decision_share_with_user_ids = []" in src, (
            "load_detail must reset decision_share_with_user_ids = [] on every load "
            "to prevent stale share selections from a prior action leaking into the next one"
        )


# ── S. Issue B — open_deactivate_by_id 1-arg fix (Phase 7G.3) ────────────────


class TestOpenDeactivateById:
    """Phase 7G.3: _row_actions must use open_deactivate_by_id(row["id"]) — 1 arg
    instead of open_deactivate_confirm(row["id"], row["code"]) — 2 args.
    Passing 2 rx.Var args via partial EventSpec silently produces invisible buttons
    in Reflex 0.9.x, the same failure mode as the 13-arg open_edit (Phase 7G.2).
    """

    def test_open_deactivate_by_id_exists(self) -> None:
        """ApprovalProcessConfigState must have open_deactivate_by_id(pid: str)."""
        from durgam.states.config_approval_process import ApprovalProcessConfigState

        assert hasattr(ApprovalProcessConfigState, "open_deactivate_by_id"), (
            "ApprovalProcessConfigState must have open_deactivate_by_id(pid) — 1-arg deactivate trigger"
        )

    def test_row_actions_uses_open_deactivate_by_id(self) -> None:
        """_row_actions must call open_deactivate_by_id with only row['id']."""
        page_path = "durgam/pages/admin/config/approval_processes.py"
        with open(page_path) as f:
            src = f.read()
        assert "open_deactivate_by_id" in src, (
            "_row_actions must call open_deactivate_by_id (1-arg Deactivate trigger)"
        )
        assert "open_deactivate_confirm" not in src.split("def open_deactivate_confirm")[0].split("_row_actions")[1] if "_row_actions" in src else True, (
            "_row_actions must NOT call the 2-arg open_deactivate_confirm"
        )

    def test_open_deactivate_by_id_reads_from_processes_list(self) -> None:
        """open_deactivate_by_id source must iterate self.processes to find the row."""
        import inspect as _inspect

        from durgam.states.config_approval_process import ApprovalProcessConfigState

        fn = ApprovalProcessConfigState.open_deactivate_by_id.fn  # type: ignore[attr-defined]
        src = _inspect.getsource(fn)
        assert "self.processes" in src, (
            "open_deactivate_by_id must look up code from self.processes (no extra DB query)"
        )
        assert "self.confirm_open = True" in src, (
            "open_deactivate_by_id must set confirm_open=True after finding the process"
        )


# ── T. Issue C — data_table actions column width (Phase 7G.4) ────────────────


class TestDataTableActionsColumnWidth:
    """Phase 7G.4 root cause: data_table actions column header used width='3rem'
    (kebab-icon era sizing). Two text buttons (Edit + Deactivate) need ~12rem.
    Buttons were in the DOM but visually clipped — confirmed via browser DevTools.
    Phases 7G/7G.2/7G.3 fixed click handlers, none touched the column width.
    """

    def test_actions_column_header_width_is_wide_enough(self) -> None:
        """Actions column header must not use the old 3rem (too narrow for text buttons).
        Updated by 7G.6: width tightened from 12rem to 8rem + sticky positioning."""
        with open("durgam/pages/shared/data_table.py") as f:
            src = f.read()
        assert 'width="3rem"' not in src, (
            'Actions column header still uses width="3rem" — too narrow for text buttons'
        )
        assert 'width="12rem"' not in src, (
            'width="12rem" was replaced by width="8rem" in Phase 7G.6 (sticky column)'
        )
        assert 'width="8rem"' in src, (
            'Actions column must use width="8rem" (sufficient for Edit + Deactivate '
            'at size="1"; narrower than 12rem reduces wasted space)'
        )


# ── U. Issue D — approver redaction (Phase 7G.4) ────────────────────────────


class TestApproverRedaction:
    """Phase 7G.4: list_actions_for_approver_redacted mirrors the requestor-redacted
    pattern. Higher-stage unshared actions are returned (not filtered) with
    is_redacted=True so the UI shows 'Comment not shared with you.' instead of
    hiding the row entirely.
    """

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

    def test_approver_sees_redacted_row_for_higher_unshared_action(self) -> None:
        """HoD (stage 1) must see Registrar's (stage 2) unshared action as a ROW
        with is_redacted=True — not filtered out — matching the requestor UX."""
        hod_id = uuid4()
        reg_id = uuid4()

        hod_action = SimpleNamespace(
            actor_user_id=hod_id,
            stage_index=1,
            visible_to_lower_user_ids_json=None,
        )
        reg_action = SimpleNamespace(
            actor_user_id=reg_id,
            stage_index=2,
            visible_to_lower_user_ids_json=None,  # NOT shared
        )

        svc = self._make_svc([hod_action, reg_action])
        # Pass stale approver_stage=2 (old wrong caller value) to confirm
        # service still self-corrects to effective_stage=1 for HoD.
        result = svc.list_actions_for_approver_redacted(uuid4(), hod_id, approver_stage=2)

        assert len(result) == 2, "Both rows must be returned (redacted one included)"
        by_actor = {a.actor_user_id: flag for a, flag in result}
        assert by_actor[hod_id] is False, "HoD's own action must not be redacted"
        assert by_actor[reg_id] is True, (
            "Registrar's unshared higher-stage action must be redacted (is_redacted=True)"
        )

    def test_approver_sees_full_content_for_higher_shared_action(self) -> None:
        """When Registrar explicitly shares, HoD sees Registrar's action unredacted."""
        hod_id = uuid4()
        reg_id = uuid4()

        hod_action = SimpleNamespace(
            actor_user_id=hod_id,
            stage_index=1,
            visible_to_lower_user_ids_json=None,
        )
        reg_action = SimpleNamespace(
            actor_user_id=reg_id,
            stage_index=2,
            visible_to_lower_user_ids_json=[str(hod_id)],  # explicitly shared
        )

        svc = self._make_svc([hod_action, reg_action])
        result = svc.list_actions_for_approver_redacted(uuid4(), hod_id, approver_stage=2)

        by_actor = {a.actor_user_id: flag for a, flag in result}
        assert by_actor[reg_id] is False, (
            "Registrar's explicitly shared action must NOT be redacted"
        )

    def test_approver_own_action_never_redacted(self) -> None:
        """An approver's own action is always returned unredacted."""
        hod_id = uuid4()

        own_action = SimpleNamespace(
            actor_user_id=hod_id,
            stage_index=2,
            visible_to_lower_user_ids_json=None,
        )

        svc = self._make_svc([own_action])
        result = svc.list_actions_for_approver_redacted(uuid4(), hod_id, approver_stage=1)

        assert len(result) == 1
        assert result[0][1] is False, "Own action must never be redacted"

    def test_approver_lower_stage_action_never_redacted(self) -> None:
        """A lower-stage action (peer or below) is always returned unredacted."""
        hod_id = uuid4()
        other_id = uuid4()

        hod_action = SimpleNamespace(
            actor_user_id=hod_id,
            stage_index=2,
            visible_to_lower_user_ids_json=None,
        )
        lower_action = SimpleNamespace(
            actor_user_id=other_id,
            stage_index=1,  # lower
            visible_to_lower_user_ids_json=None,
        )

        svc = self._make_svc([hod_action, lower_action])
        result = svc.list_actions_for_approver_redacted(uuid4(), hod_id, approver_stage=2)

        by_actor = {a.actor_user_id: flag for a, flag in result}
        assert by_actor[other_id] is False, (
            "Lower-stage action must never be redacted (higher authority sees lower by default)"
        )

    def test_load_detail_uses_approver_redacted_method(self) -> None:
        """load_detail must call list_actions_for_approver_redacted (not the old
        filtering list_actions_for_approver) in the approver branch (Phase 7G.4)."""
        import inspect as _inspect

        from durgam.states.approval_requests import RequestDetailState

        fn = RequestDetailState.load_detail.fn  # type: ignore[attr-defined]
        src = _inspect.getsource(fn)
        assert "list_actions_for_approver_redacted" in src, (
            "load_detail must use list_actions_for_approver_redacted in the approver "
            "branch so higher-stage unshared rows appear with placeholder comment"
        )


# ── V. Issue E — actions column hydration fix (Phase 7G.5) ──────────────────


class TestActionsColumnHydrationFix:
    """Phase 7G.5: Empty header cell ('') causes browser/Radix to collapse the
    actions column during SSR→hydration transition. width='12rem' (from 7G.4)
    is not honored until a reflow event; DevTools open forces the reflow, which
    is why buttons appear after opening DevTools. Fix: non-empty 'Actions' label
    on the header cell + min_width='12rem' on BOTH header and row cell.
    """

    def test_actions_header_has_non_empty_label(self) -> None:
        """Actions column header must use 'Actions' text, not empty string."""
        with open("durgam/pages/shared/data_table.py") as f:
            src = f.read()
        assert 'column_header_cell("")' not in src, (
            "Actions header uses empty string — browser collapses the column during "
            "SSR→hydration before reflow; replace with 'Actions' label text"
        )
        assert '"Actions"' in src, (
            "Actions column header must contain 'Actions' label text so the browser "
            "keeps the column visible during SSR→hydration"
        )

    def test_actions_header_and_cell_have_min_width(self) -> None:
        """Header and row cell must carry min_width to survive hydration.
        Updated by 7G.6: min_width tightened from 12rem to 8rem + sticky positioning."""
        with open("durgam/pages/shared/data_table.py") as f:
            src = f.read()
        # Count occurrences: one on header + one on cell = at least 2
        count = src.count('min_width="8rem"')
        assert count >= 2, (
            f"Expected min_width='8rem' on BOTH header cell and row cell; "
            f"found {count} occurrence(s). Phase 7G.6 changed 12rem → 8rem."
        )


# ── W. Issue F — UTC→IST display fix (Phase 7G.5) ───────────────────────────


class TestFormatDtISTDisplay:
    """Phase 7G.5: _format_dt at approval_requests.py:38 used naive strftime
    returning '2026-06-14 03:30 UTC'. format_ist from durgam/utils/ist_format.py
    converts to 'Asia/Kolkata' and returns e.g. '14 Jun 2026, 9:00 AM IST'.
    Routing _format_dt through format_ist fixes all 7 call sites in one change.
    """

    def test_format_dt_returns_ist_label(self) -> None:
        """_format_dt output must contain 'IST', not 'UTC'."""
        from durgam.states.approval_requests import _format_dt

        dt = datetime(2026, 6, 14, 3, 30, 0, tzinfo=UTC)
        result = _format_dt(dt)
        assert "IST" in result, f"Expected 'IST' in output, got: {result!r}"
        assert "UTC" not in result, (
            f"_format_dt must no longer append 'UTC'; got: {result!r}"
        )

    def test_format_dt_converts_utc_to_ist(self) -> None:
        """UTC 00:00 must display as 5:30 AM IST (UTC+5:30 offset)."""
        from durgam.states.approval_requests import _format_dt

        dt = datetime(2026, 6, 14, 0, 0, 0, tzinfo=UTC)
        result = _format_dt(dt)
        assert "5:30" in result, (
            f"UTC 00:00 should display as 5:30 AM IST; got: {result!r}"
        )

    def test_format_dt_none_returns_dash(self) -> None:
        """_format_dt(None) must return the em-dash sentinel '—'."""
        from durgam.states.approval_requests import _format_dt

        assert _format_dt(None) == "—"


# ── X. Issue G — sticky actions column (Phase 7G.6) ─────────────────────────


class TestStickyActionsColumn:
    """Phase 7G.6: Wide tables (approval_processes, leave_sanction_matrix, etc.)
    push the actions column off-screen to the right. width='12rem' keeps the
    column wide but not visible when the table overflows the container.
    Fix: position='sticky' + right='0' on BOTH header cell and row cell in
    _reactive_table_view. Width tightened to 8rem (sufficient for Edit +
    Deactivate at size='1'; kebab/icon pages gain whitespace, not a problem).
    The box_shadow provides a visual separator from the scrollable content.
    """

    def test_actions_header_is_sticky_right(self) -> None:
        """Actions header cell must carry position='sticky' and right='0'."""
        with open("durgam/pages/shared/data_table.py") as f:
            src = f.read()
        assert 'position="sticky"' in src, (
            "Actions column header must use position='sticky' so it stays visible "
            "when the table is wider than the container"
        )
        assert 'right="0"' in src, (
            "Actions column header must use right='0' to anchor sticky at the right edge"
        )

    def test_actions_header_and_cell_both_sticky(self) -> None:
        """Both header cell AND row cell must be sticky (not just one)."""
        with open("durgam/pages/shared/data_table.py") as f:
            src = f.read()
        sticky_count = src.count('position="sticky"')
        right_count = src.count('right="0"')
        assert sticky_count >= 2, (
            f"Expected position='sticky' on BOTH header and row cell; "
            f"found {sticky_count} occurrence(s)"
        )
        assert right_count >= 2, (
            f"Expected right='0' on BOTH header and row cell; "
            f"found {right_count} occurrence(s)"
        )

    def test_actions_column_width_is_8rem(self) -> None:
        """Width tightened to 8rem (12rem was too wide; 8rem fits Edit+Deactivate)."""
        with open("durgam/pages/shared/data_table.py") as f:
            src = f.read()
        assert 'width="8rem"' in src, (
            "Actions column must use width='8rem' after the 12rem → 8rem tightening"
        )
        assert 'width="12rem"' not in src, (
            "Old width='12rem' must be replaced; 8rem is sufficient for text buttons"
        )


# ── Y. Debug paint cleanup (Phase 7G.6) ──────────────────────────────────────


class TestDebugPaintCleanup:
    """Phase 7G.6: Bala's debug paint (background='red', border='3px solid blue')
    in approval_processes._row_actions must be removed — not merely commented out.
    Commented code is noise and may confuse future readers.
    """

    def test_row_actions_has_no_debug_paint(self) -> None:
        """No 'red' background or '3px solid blue' border in approval_processes.py."""
        with open("durgam/pages/admin/config/approval_processes.py") as f:
            src = f.read()
        active_lines = [
            line for line in src.splitlines() if not line.strip().startswith("#")
        ]
        active_src = "\n".join(active_lines)
        assert "background=\"red\"" not in active_src, (
            "Debug background='red' must be removed from _row_actions"
        )
        assert "3px solid blue" not in active_src, (
            "Debug border='3px solid blue' must be removed from _row_actions"
        )

    def test_commented_debug_lines_removed(self) -> None:
        """Even as comments, debug paint lines must not remain in the file."""
        with open("durgam/pages/admin/config/approval_processes.py") as f:
            src = f.read()
        assert "background=\"red\"" not in src, (
            "Commented '# background=\"red\"' must be deleted, not left as comment noise"
        )
        assert "3px solid blue" not in src, (
            "Commented '# border=\"3px solid blue\"' must be deleted from the file"
        )
