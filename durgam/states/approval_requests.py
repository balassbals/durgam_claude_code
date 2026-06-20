"""States for approval pages (M7 Phases 2–3).

Accessible to all authenticated users. No admin permission required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import reflex as rx
import structlog

from durgam.db import open_session
from durgam.states.base import BaseState
from durgam.utils.ist_format import format_ist

log = structlog.get_logger(__name__)

_STATE_OPTIONS: list[dict[str, str]] = [
    {"value": "all", "label": "All states"},
    {"value": "submitted", "label": "Submitted"},
    {"value": "in_review", "label": "In Review"},
    {"value": "approved", "label": "Approved"},
    {"value": "rejected", "label": "Rejected"},
    {"value": "withdrawn", "label": "Withdrawn"},
    {"value": "cancelled", "label": "Cancelled"},
]


def _resolve_or_redirect(state: BaseState):
    state._resolve_session()
    if not state.current_user_id:
        return rx.redirect("/login")
    return None


def _format_dt(dt: datetime | None) -> str:
    return format_ist(dt)


def _stage_label(current_stage: int, channel_len: int, state: str) -> str:
    if state in ("approved", "rejected", "withdrawn", "cancelled"):
        return state.capitalize()
    return f"Stage {current_stage} of {channel_len}"


# ── My Requests list ───────────────────────────────────────────────────


class MyRequestsState(BaseState):
    rows: list[dict[str, Any]] = []
    state_filter: str = "all"
    loading: bool = True

    @rx.var
    def empty_message(self) -> str:
        if self.state_filter == "all":
            return "You have not submitted any approval requests yet."
        return f"You have no {self.state_filter.replace('_', ' ')} requests."

    async def load_my_requests(self) -> None:
        redirect = _resolve_or_redirect(self)
        if redirect is not None:
            return redirect

        self.loading = True
        self.rows = []

        from durgam.repositories.approval_process import ApprovalProcessRepository
        from durgam.repositories.approval_request import ApprovalRequestRepository

        with open_session() as session:
            req_repo = ApprovalRequestRepository(session)
            proc_repo = ApprovalProcessRepository(session)

            user_id = UUID(self.current_user_id)
            sf = None if self.state_filter == "all" else self.state_filter
            requests = req_repo.list_for_requestor(user_id, state_filter=sf)

            proc_cache: dict[UUID, Any] = {}
            enriched: list[dict[str, Any]] = []
            for r in requests:
                if r.process_id not in proc_cache:
                    proc_cache[r.process_id] = proc_repo.get_by_id(r.process_id)
                proc = proc_cache[r.process_id]
                channel_len = len(proc.channel_role_codes) if proc and proc.channel_role_codes else 0
                if r.resolved_channel_json:
                    channel_len = len(r.resolved_channel_json)
                enriched.append({
                    "id": str(r.id),
                    "title": r.title,
                    "process_code": proc.code if proc else "—",
                    "process_title": proc.title if proc else "—",
                    "state": r.state,
                    "current_stage_label": _stage_label(r.current_stage, channel_len, r.state),
                    "submitted_at_display": _format_dt(r.created_at),
                    "decided_at_display": _format_dt(r.decided_at),
                })
            # Phase 8B: optional ?type=faculty deep-link filter (Faculty Requests
            # overlay). Absent/other values leave the full list unchanged.
            if self.router.page.params.get("type", "") == "faculty":
                enriched = [
                    e for e in enriched if e["process_code"].startswith("faculty_")
                ]
            self.rows = enriched

        self.loading = False
        self._load_nav_entries()

    async def change_state_filter(self, value: str) -> None:
        self.state_filter = value
        await self.load_my_requests()

    def open_detail(self, request_id: str) -> rx.Component:
        return rx.redirect(f"/approvals/request/{request_id}")


# ── Approver Inbox ────────────────────────────────────────────────────


class ApproverInboxState(BaseState):
    pending_rows: list[dict[str, Any]] = []
    past_rows: list[dict[str, Any]] = []
    loading: bool = True
    view_mode: str = "pending"  # "pending" | "past"

    @rx.var
    def rows(self) -> list[dict[str, Any]]:
        """Reactive selector — returns the active list; no DB query on tab switch."""
        if self.view_mode == "past":
            return self.past_rows
        return self.pending_rows

    def set_view_mode(self, mode: str | list[str]) -> None:
        """Switch view. Both lists are pre-loaded by load_inbox; no DB roundtrip here."""
        self.view_mode = mode if isinstance(mode, str) else (mode[0] if mode else "pending")

    def _potential_approver_guard(self) -> rx.Component | None:
        """Route guard: redirect if user cannot possibly be an approver."""
        self._resolve_session()
        if not self.current_user_id:
            return rx.redirect("/login")
        from durgam.auth.permissions import can as can_perm
        from durgam.pages.approvals import is_channel_approver

        user_id = UUID(self.current_user_id)
        with open_session() as session:
            has_static = can_perm(
                user_id, "approve", "approval_request", None, None, session,
            )
            if not has_static and not is_channel_approver(user_id, session):
                self.flash = "You do not have access to the approvals inbox."
                self.flash_type = "error"
                return rx.redirect("/")
        self.admin_authorized = True
        return None

    async def load_inbox(self) -> None:
        guard = self._potential_approver_guard()
        if guard is not None:
            return guard

        self.loading = True
        self.pending_rows = []
        self.past_rows = []

        from durgam.models.identity import User
        from durgam.repositories.approval_process import ApprovalProcessRepository
        from durgam.repositories.approval_request import ApprovalRequestRepository
        from durgam.services.approval_routing import resolve_stage_approvers

        with open_session() as session:
            req_repo = ApprovalRequestRepository(session)
            proc_repo = ApprovalProcessRepository(session)

            viewer_id = UUID(self.current_user_id)
            proc_cache: dict[UUID, Any] = {}

            # ── Past Actions: all requests the viewer acted on, any state ──────
            past_enriched: list[dict[str, Any]] = []
            past_requests = req_repo.list_where_actor_acted(viewer_id)
            for r in past_requests:
                if r.process_id not in proc_cache:
                    proc_cache[r.process_id] = proc_repo.get_by_id(r.process_id)
                proc = proc_cache[r.process_id]
                if proc is None:
                    continue
                channel_len = len(proc.channel_role_codes) if proc.channel_role_codes else 0
                if r.resolved_channel_json:
                    channel_len = len(r.resolved_channel_json)
                requestor = session.get(User, r.requestor_user_id)
                requestor_display = (
                    (requestor.full_name or requestor.username) if requestor else "Unknown"
                )
                past_enriched.append({
                    "id": str(r.id),
                    "title": r.title,
                    "process_code": proc.code,
                    "process_title": proc.title,
                    "requestor_display": requestor_display,
                    "current_stage_label": _stage_label(r.current_stage, channel_len, r.state),
                    "submitted_at_display": _format_dt(r.created_at),
                    "state": r.state,
                })
            # Phase 8B: optional ?type=faculty deep-link filter (Faculty Requests
            # overlay). Absent/other values leave the full list unchanged.
            if self.router.page.params.get("type", "") == "faculty":
                past_enriched = [
                    e for e in past_enriched
                    if e["process_code"].startswith("faculty_")
                ]
            self.past_rows = past_enriched

            # ── Pending: active requests awaiting the viewer's decision ────────
            pending_enriched: list[dict[str, Any]] = []
            pending = req_repo.list_by_states(["submitted", "in_review"])
            for r in pending:
                if r.process_id not in proc_cache:
                    proc_cache[r.process_id] = proc_repo.get_by_id(r.process_id)
                proc = proc_cache[r.process_id]
                if proc is None:
                    continue

                try:
                    approvers = resolve_stage_approvers(
                        request=r, process=proc, session=session,
                    )
                except Exception:
                    continue

                approver_ids = {u.id for u in approvers}
                if viewer_id not in approver_ids:
                    continue

                channel_len = len(proc.channel_role_codes) if proc.channel_role_codes else 0
                if r.resolved_channel_json:
                    channel_len = len(r.resolved_channel_json)
                requestor = session.get(User, r.requestor_user_id)
                requestor_display = (
                    (requestor.full_name or requestor.username) if requestor else "Unknown"
                )
                pending_enriched.append({
                    "id": str(r.id),
                    "title": r.title,
                    "process_code": proc.code,
                    "process_title": proc.title,
                    "requestor_display": requestor_display,
                    "current_stage_label": _stage_label(r.current_stage, channel_len, r.state),
                    "submitted_at_display": _format_dt(r.created_at),
                    "state": r.state,
                })
            # Phase 8B: optional ?type=faculty deep-link filter (Faculty Requests
            # overlay). Absent/other values leave the full list unchanged.
            if self.router.page.params.get("type", "") == "faculty":
                pending_enriched = [
                    e for e in pending_enriched
                    if e["process_code"].startswith("faculty_")
                ]
            self.pending_rows = pending_enriched

        self.loading = False
        self._load_nav_entries()

    def open_request(self, request_id: str) -> rx.Component:
        return rx.redirect(f"/approvals/request/{request_id}")


# ── Submit Request ─────────────────────────────────────────────────────


class SubmitRequestState(BaseState):
    process_options: list[dict[str, Any]] = []
    selected_process_id: str = "none"
    title: str = ""
    description: str = ""
    uploaded_file_ids: list[str] = []
    submitting: bool = False
    error: str = ""

    # NRF-specific fields (conditionally shown when process is NRF_APPROVAL)
    nrf_name: str = ""
    nrf_designation: str = ""
    nrf_organization: str = ""
    nrf_expertise: str = ""
    nrf_available_from: str = ""
    nrf_available_to: str = ""
    nrf_type: str = "visiting"

    def set_nrf_name(self, v: str) -> None:
        self.nrf_name = v

    def set_nrf_designation(self, v: str) -> None:
        self.nrf_designation = v

    def set_nrf_organization(self, v: str) -> None:
        self.nrf_organization = v

    def set_nrf_expertise(self, v: str) -> None:
        self.nrf_expertise = v

    def set_nrf_available_from(self, v: str) -> None:
        self.nrf_available_from = v

    def set_nrf_available_to(self, v: str) -> None:
        self.nrf_available_to = v

    def set_nrf_type(self, v: str) -> None:
        self.nrf_type = v

    # NOC-specific fields (conditionally shown when process is faculty_noc)
    noc_purpose: str = ""
    noc_to_whom: str = ""
    noc_date_required_by: str = ""
    noc_additional_notes: str = ""

    def set_noc_purpose(self, v: str) -> None:
        self.noc_purpose = v

    def set_noc_to_whom(self, v: str) -> None:
        self.noc_to_whom = v

    def set_noc_date_required_by(self, v: str) -> None:
        self.noc_date_required_by = v

    def set_noc_additional_notes(self, v: str) -> None:
        self.noc_additional_notes = v

    @rx.var
    def selected_process(self) -> dict[str, Any]:
        for p in self.process_options:
            if p["id"] == self.selected_process_id:
                return p
        return {}

    @rx.var
    def selected_process_code(self) -> str:
        return str(self.selected_process.get("code", ""))

    @rx.var
    def requires_upward(self) -> bool:
        return bool(self.selected_process.get("requires_upward", False))

    @rx.var
    def max_upward(self) -> int:
        return int(self.selected_process.get("max_upward", 0))

    @rx.var
    def submit_disabled(self) -> bool:
        if self.selected_process_id == "none" or not self.title.strip():
            return True
        if self.requires_upward and len(self.uploaded_file_ids) < 1:
            return True
        if self.max_upward > 0 and len(self.uploaded_file_ids) > self.max_upward:
            return True
        if self.selected_process_code == "NRF_APPROVAL":
            if not all([
                self.nrf_name.strip(),
                self.nrf_designation.strip(),
                self.nrf_organization.strip(),
                self.nrf_expertise.strip(),
                self.nrf_available_from,
                self.nrf_available_to,
            ]):
                return True
            if self.nrf_available_from and self.nrf_available_to:
                if self.nrf_available_to < self.nrf_available_from:
                    return True
        if self.selected_process_code == "faculty_noc":
            if not self.noc_purpose.strip() or not self.noc_to_whom.strip():
                return True
        return self.submitting

    @rx.var
    def nrf_date_range_error(self) -> str:
        if (
            self.nrf_available_from
            and self.nrf_available_to
            and self.nrf_available_to < self.nrf_available_from
        ):
            return "'Available To' must be on or after 'Available From'."
        return ""

    async def load_submit(self) -> None:
        redirect = _resolve_or_redirect(self)
        if redirect is not None:
            return redirect

        self.selected_process_id = "none"
        self.title = ""
        self.description = ""
        self.uploaded_file_ids = []
        self.error = ""
        self.submitting = False
        self.nrf_name = ""
        self.nrf_designation = ""
        self.nrf_organization = ""
        self.nrf_expertise = ""
        self.nrf_available_from = ""
        self.nrf_available_to = ""
        self.nrf_type = "visiting"
        self.noc_purpose = ""
        self.noc_to_whom = ""
        self.noc_date_required_by = ""
        self.noc_additional_notes = ""

        from durgam.repositories.approval_process import ApprovalProcessRepository
        from durgam.repositories.user_role import UserRoleRepository

        with open_session() as session:
            proc_repo = ApprovalProcessRepository(session)
            ur_repo = UserRoleRepository(session)

            user_id = UUID(self.current_user_id)
            user_role_pairs = ur_repo.get_user_roles_with_role(user_id)
            user_role_codes = {role.code for _, role in user_role_pairs}

            all_procs = proc_repo.list_all_active()
            eligible: list[dict[str, Any]] = []
            for proc in all_procs:
                if proc.requestor_role_codes:
                    if not user_role_codes & set(proc.requestor_role_codes):
                        continue
                eligible.append({
                    "id": str(proc.id),
                    "code": proc.code,
                    "title": proc.title,
                    "requires_upward": proc.requires_upward_attachments,
                    "max_upward": proc.max_upward_attachments,
                })
            self.process_options = eligible

        # Phase 6: optional deep-link pre-selection via ?process=<code>
        # (e.g. /approvals/submit?process=faculty_fdp). Falls through to the
        # default "none" when the param is absent or matches no eligible process,
        # preserving the unchanged manual-selection behaviour.
        requested_code = self.router.page.params.get("process", "")
        if requested_code:
            for opt in self.process_options:
                if opt["code"] == requested_code:
                    self.selected_process_id = opt["id"]
                    break

        self._load_nav_entries()

    def on_process_change(self, value: str) -> None:
        self.selected_process_id = value
        self.uploaded_file_ids = []
        self.error = ""
        self.nrf_name = ""
        self.nrf_designation = ""
        self.nrf_organization = ""
        self.nrf_expertise = ""
        self.nrf_available_from = ""
        self.nrf_available_to = ""
        self.nrf_type = "visiting"
        self.noc_purpose = ""
        self.noc_to_whom = ""
        self.noc_date_required_by = ""
        self.noc_additional_notes = ""

    def set_title(self, value: str) -> None:
        self.title = value

    def set_description(self, value: str) -> None:
        self.description = value

    async def handle_upload(self, files: list[rx.UploadFile]) -> None:
        from durgam.repositories.file_asset import FileAssetRepository
        from durgam.services.upload import UploadService
        from durgam.storage import get_storage_backend

        if not files:
            return

        with open_session() as session:
            svc = UploadService(
                file_repo=FileAssetRepository(session),
                backend=get_storage_backend(),
            )
            for f in files:
                content = await f.read()
                if not content:
                    continue
                asset = svc.upload(
                    data=content,
                    original_name=f.filename or "attachment",
                    mime_type=f.content_type or "application/octet-stream",
                    actor_id=UUID(self.current_user_id),
                    purpose="approval_upward",
                )
                self.uploaded_file_ids = [
                    *self.uploaded_file_ids,
                    str(asset.id),
                ]
            session.commit()

    def remove_file(self, file_id: str) -> None:
        self.uploaded_file_ids = [
            fid for fid in self.uploaded_file_ids if fid != file_id
        ]

    async def submit_request(self) -> None:
        self.error = ""
        self.submitting = True

        if not self.title.strip():
            self.error = "Title is required."
            self.submitting = False
            return

        if self.selected_process_id == "none":
            self.error = "Please select an approval process."
            self.submitting = False
            return

        if self.selected_process_code == "NRF_APPROVAL":
            if self.nrf_available_from and self.nrf_available_to:
                if self.nrf_available_to < self.nrf_available_from:
                    self.error = "'Available To' must be on or after 'Available From'."
                    self.submitting = False
                    return

        # NOC and other faculty-typed processes route through FacultyRequestService
        if self.selected_process_code.startswith("faculty_"):
            return await self._submit_faculty_request()

        from durgam.services.approval_request import (
            ApprovalRequestError,
            ApprovalRequestService,
        )

        try:
            with open_session() as session:
                svc = ApprovalRequestService(session)
                payload: dict[str, Any] | None = None
                if self.selected_process_code == "NRF_APPROVAL":
                    dept_id = self._resolve_user_dept_scope(session)
                    if not dept_id:
                        self.error = "Cannot determine your department for NRF submission."
                        self.submitting = False
                        return
                    payload = {
                        "description": self.description.strip(),
                        "nrf_data": {
                            "department_id": str(dept_id),
                            "name": self.nrf_name.strip(),
                            "designation": self.nrf_designation.strip(),
                            "organization": self.nrf_organization.strip(),
                            "expertise": self.nrf_expertise.strip(),
                            "available_from": self.nrf_available_from,
                            "available_to": self.nrf_available_to,
                            "non_regular_type": self.nrf_type,
                        },
                    }
                elif self.description.strip():
                    payload = {"description": self.description.strip()}
                request = svc.submit(
                    process_id=UUID(self.selected_process_id),
                    requestor_user_id=UUID(self.current_user_id),
                    title=self.title.strip(),
                    payload=payload,
                    upward_attachment_file_ids=[UUID(fid) for fid in self.uploaded_file_ids] if self.uploaded_file_ids else None,
                )
                session.commit()
                new_id = str(request.id)

            self.submitting = False
            return rx.redirect(f"/approvals/request/{new_id}")
        except ApprovalRequestError as e:
            self.error = str(e)
            self.submitting = False
        except Exception as e:
            log.error(
                "submit_request_failed",
                exc_info=True,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            self.error = "An unexpected error occurred. Please try again."
            self.submitting = False

    async def _submit_faculty_request(self) -> rx.event.EventSpec | None:
        """Handle submit for faculty_* process codes.

        Phase 5D supports: noc, invited_talk, professional_membership, wfh, field_visit.
        NOC has structured payload (purpose/to_whom/date_required_by/notes). All others
        use generic description-only payload per Q-P5.6.
        """
        from durgam.repositories.faculty import FacultyRepository
        from durgam.services.faculty_request import (
            EmptyApproverPoolError,
            FacultyRequestService,
            InvalidRequestStatusTransitionError,
            UnknownRequestTypeError,
        )

        user_id = UUID(self.current_user_id)

        # Derive request_type from process code: "faculty_noc" → "noc"
        process_code = self.selected_process_code
        request_type = process_code[len("faculty_"):]

        # Build payload: NOC has structured fields; all others use generic description.
        payload: dict[str, Any] = {}
        if request_type == "noc":
            if not self.noc_purpose.strip():
                self.error = "Purpose is required."
                self.submitting = False
                return
            if not self.noc_to_whom.strip():
                self.error = "To Whom is required."
                self.submitting = False
                return
            payload = {"purpose": self.noc_purpose.strip(), "to_whom": self.noc_to_whom.strip()}
            if self.noc_date_required_by:
                payload["date_required_by"] = self.noc_date_required_by
            if self.noc_additional_notes.strip():
                payload["additional_notes"] = self.noc_additional_notes.strip()
        else:
            # Q-P5.6: generic description-only payload for the 9 non-NOC faculty
            # request types. Per-type payload schemas deferred to post-gate polish.
            if self.description.strip():
                payload = {"description": self.description.strip()}

        try:
            with open_session() as session:
                fac_repo = FacultyRepository(session)
                faculty = fac_repo.get_by_user_id(user_id)
                if faculty is None:
                    self.error = "No faculty profile found for your account."
                    self.submitting = False
                    return

                svc = FacultyRequestService(session)
                draft = svc.create_request(
                    faculty_id=faculty.id,
                    request_type=request_type,
                    payload=payload,
                    actor_id=user_id,
                )
                updated = svc.submit_for_approval(draft.id, user_id)
                approval_request_id = str(updated.approval_request_id)
                session.commit()

            self.submitting = False
            return rx.redirect(f"/approvals/request/{approval_request_id}")
        except (
            InvalidRequestStatusTransitionError,
            UnknownRequestTypeError,
            EmptyApproverPoolError,
        ) as e:
            self.error = str(e)
            self.submitting = False
        except Exception as e:
            log.error(
                "faculty_submit_request_failed",
                exc_info=True,
                error_type=type(e).__name__,
            )
            self.error = "An unexpected error occurred. Please try again."
            self.submitting = False


# ── Request Detail (read-only for Phase 2) ─────────────────────────────


class RequestDetailState(BaseState):
    request: dict[str, Any] = {}
    process: dict[str, Any] = {}
    steps: list[dict[str, Any]] = []
    upward_attachments: list[dict[str, Any]] = []
    downward_attachments: list[dict[str, Any]] = []
    viewer_is_requestor: bool = False
    can_withdraw: bool = False
    loading: bool = True
    error: str = ""
    confirm_withdraw_open: bool = False

    # Phase 3 — approver decision state
    viewer_is_channel_approver: bool = False
    viewer_is_current_stage_approver: bool = False
    can_decide: bool = False
    next_stage_approvers_preview: list[str] = []
    is_terminal_stage: bool = False
    current_stage_role_code: str = ""
    approve_dialog_open: bool = False
    reject_dialog_open: bool = False

    # Phase 7F — confidentiality controls (approver-side; passed to approve/reject)
    decision_hide_from_requestor: bool = False
    decision_share_with_user_ids: list[str] = []
    prior_action_actors: list[dict[str, Any]] = []

    # Phase 7F — linked FacultyRequest for faculty_* processes
    linked_faculty_request_id: str = ""
    linked_faculty_request_status: str = ""
    noc_payload: dict[str, Any] = {}
    decision_comment: str = ""
    decision_downward_file_ids: list[str] = []
    decision_submitting: bool = False
    decision_error: str = ""
    process_allows_downward: bool = False
    process_requires_downward: bool = False
    process_max_downward: int = 0

    # M8 — leave-specific detail (populated only when process_code == "LEAVE_APPROVAL")
    is_leave_request: bool = False
    leave_type: str = ""
    leave_starts_on: str = ""
    leave_ends_on: str = ""
    leave_chargeable_days: float = 0.0
    leave_sanctioned_days_current: float = 0.0
    leave_state: str = ""
    leave_requestor_balance: dict[str, Any] = {}
    leave_has_medical_cert: bool = False
    leave_has_fitness_cert: bool = False
    leave_has_bond: bool = False
    leave_medical_cert_file_id: str = ""
    leave_fitness_cert_file_id: str = ""
    leave_bond_file_id: str = ""

    # Sanctioner partial-modify input
    sanctioned_days_input: str = ""

    # Recommend-only flag for current stage
    current_stage_is_recommend_only: bool = False

    def set_sanctioned_days_input(self, value: str) -> None:
        self.sanctioned_days_input = value

    def set_decision_hide_from_requestor(self, value: bool) -> None:
        self.decision_hide_from_requestor = value

    def toggle_decision_share_with(self, user_id: str) -> None:
        if user_id in self.decision_share_with_user_ids:
            self.decision_share_with_user_ids = [
                uid for uid in self.decision_share_with_user_ids if uid != user_id
            ]
        else:
            self.decision_share_with_user_ids = [*self.decision_share_with_user_ids, user_id]

    async def load_detail(self) -> None:
        redirect = _resolve_or_redirect(self)
        if redirect is not None:
            return redirect

        self.loading = True
        self.error = ""
        self.request = {}
        self.process = {}
        self.steps = []
        self.upward_attachments = []
        self.downward_attachments = []
        self.viewer_is_requestor = False
        self.can_withdraw = False
        self.confirm_withdraw_open = False
        self.viewer_is_channel_approver = False
        self.viewer_is_current_stage_approver = False
        self.can_decide = False
        self.next_stage_approvers_preview = []
        self.is_terminal_stage = False
        self.current_stage_role_code = ""
        self.approve_dialog_open = False
        self.reject_dialog_open = False
        self.decision_comment = ""
        self.decision_downward_file_ids = []
        self.decision_submitting = False
        self.decision_error = ""
        self.process_allows_downward = False
        self.process_requires_downward = False
        self.process_max_downward = 0
        # Phase 7F confidentiality + linked faculty request reset
        self.decision_hide_from_requestor = False
        self.decision_share_with_user_ids = []
        self.prior_action_actors = []
        self.linked_faculty_request_id = ""
        self.linked_faculty_request_status = ""
        self.noc_payload = {}
        # M8 leave-specific reset
        self.is_leave_request = False
        self.leave_type = ""
        self.leave_starts_on = ""
        self.leave_ends_on = ""
        self.leave_chargeable_days = 0.0
        self.leave_sanctioned_days_current = 0.0
        self.leave_state = ""
        self.leave_requestor_balance = {}
        self.leave_has_medical_cert = False
        self.leave_has_fitness_cert = False
        self.leave_has_bond = False
        self.leave_medical_cert_file_id = ""
        self.leave_fitness_cert_file_id = ""
        self.leave_bond_file_id = ""
        self.sanctioned_days_input = ""
        self.current_stage_is_recommend_only = False

        request_id_str = self.router.page.params.get("approval_request_id", "")
        if not request_id_str:
            self.error = "Request not found."
            self.loading = False
            return

        from sqlmodel import select

        from durgam.models.crosscutting import FileAsset
        from durgam.models.identity import User
        from durgam.repositories.approval_process import ApprovalProcessRepository
        from durgam.repositories.approval_request import ApprovalRequestRepository
        from durgam.repositories.approval_step import ApprovalStepRepository
        from durgam.services.approval_request import ApprovalRequestService

        try:
            request_id = UUID(request_id_str)
        except ValueError:
            self.error = "Invalid request ID."
            self.loading = False
            return

        with open_session() as session:
            req_repo = ApprovalRequestRepository(session)
            proc_repo = ApprovalProcessRepository(session)
            step_repo = ApprovalStepRepository(session)

            req = req_repo.get_by_id(request_id)
            if req is None:
                self.error = "Request not found or not accessible."
                self.loading = False
                self._load_nav_entries()
                return

            viewer_id = UUID(self.current_user_id)
            self.viewer_is_requestor = req.requestor_user_id == viewer_id

            proc = proc_repo.get_by_id(req.process_id)

            # Access gate: viewer must be requestor, a channel approver
            # (current or prior stage), or hold approval_request:approve:*.
            if not self.viewer_is_requestor:
                from durgam.services.approval_routing import resolve_stage_approvers
                from durgam.auth.permissions import can

                is_approver = False

                # Check prior-stage approver via recorded steps
                prior_steps = step_repo.list_for_request(request_id)
                if any(s.approver_user_id == viewer_id for s in prior_steps):
                    is_approver = True

                # Check current-stage approver via routing
                if not is_approver and req.state in ("submitted", "in_review") and proc:
                    try:
                        approvers = resolve_stage_approvers(
                            request=req, process=proc, session=session,
                        )
                        if viewer_id in {u.id for u in approvers}:
                            is_approver = True
                    except Exception:
                        pass

                # Fallback: user holds the approve permission (e.g. SYSTEM_ADMIN)
                if not is_approver:
                    if can(viewer_id, "approve", "approval_request", None, None, session):
                        is_approver = True

                if not is_approver:
                    self.error = ""
                    self.loading = False
                    return rx.redirect("/approvals/my-requests")

            from durgam.pages.approvals import is_channel_approver as _is_ch
            self.viewer_is_channel_approver = _is_ch(viewer_id, session)

            svc = ApprovalRequestService(session)
            svc.view_request(request_id=request_id, viewer_user_id=viewer_id)
            session.commit()

            req = req_repo.get_by_id(request_id)
            if req is None:
                self.error = "Request not found."
                self.loading = False
                return
            channel_len = len(proc.channel_role_codes) if proc and proc.channel_role_codes else 0
            # For leave requests the per-request channel (resolved_channel_json) is the
            # source of truth for length — it may be shorter than proc.channel_role_codes
            # which is the union of all sanctioner roles used only for nav gating.
            if req.resolved_channel_json:
                channel_len = len(req.resolved_channel_json)

            requestor = session.get(User, req.requestor_user_id)
            requestor_name = requestor.full_name or requestor.username if requestor else "Unknown"

            nrf_data = (req.payload_json or {}).get("nrf_data")
            self.request = {
                "id": str(req.id),
                "title": req.title,
                "state": req.state,
                "current_stage": req.current_stage,
                "current_stage_label": _stage_label(req.current_stage, channel_len, req.state),
                "submitted_at": _format_dt(req.created_at),
                "decided_at": _format_dt(req.decided_at),
                "description": (req.payload_json or {}).get("description", ""),
                "requestor_name": requestor_name,
                "process_code": proc.code if proc else "",
                "nrf_name": nrf_data.get("name", "") if nrf_data else "",
                "nrf_designation": nrf_data.get("designation", "") if nrf_data else "",
                "nrf_organization": nrf_data.get("organization", "") if nrf_data else "",
                "nrf_expertise": nrf_data.get("expertise", "") if nrf_data else "",
                "nrf_available_from": nrf_data.get("available_from", "") if nrf_data else "",
                "nrf_available_to": nrf_data.get("available_to", "") if nrf_data else "",
                "nrf_type": nrf_data.get("non_regular_type", "visiting") if nrf_data else "",
                "cc_role_codes": ", ".join(proc.informational_cc_role_codes) if proc and proc.informational_cc_role_codes else "",
            }

            self.process = {
                "code": proc.code if proc else "",
                "title": proc.title if proc else "",
            }

            # Keep raw_steps for downward-attachment uploader attribution only
            raw_steps = step_repo.list_for_request(request_id)

            # Phase 7F/7G/7G.4: switch history to ApprovalActions; redact hidden rows.
            # Both requestor and approver views use a (action, is_redacted) tuple list
            # so the step-building loop below is shared. Redacted rows show
            # "Comment not shared with you." — consistent UX for both viewer types.
            apr_svc = ApprovalRequestService(session)
            if self.viewer_is_requestor:
                # Phase 7G: return ALL actions; derive redaction from is_visible_to_requestor
                action_pairs: list[tuple[Any, bool]] = [
                    (act, not act.is_visible_to_requestor)
                    for act in apr_svc.list_actions_for_requestor_redacted(request_id)
                ]
            else:
                # Phase 7G.4: return ALL actions; redact higher-stage unshared ones
                action_pairs = apr_svc.list_actions_for_approver_redacted(
                    approval_request_id=request_id,
                    approver_user_id=viewer_id,
                    approver_stage=req.current_stage,
                )
            step_dicts: list[dict[str, Any]] = []
            prior_actors_seen: dict[str, str] = {}
            for act, is_redacted in action_pairs:
                actor = session.get(User, act.actor_user_id)
                actor_display = (actor.full_name or actor.username) if actor else "—"
                step_dicts.append({
                    "stage": act.stage_index,
                    "approver_role_code": "—",
                    "approver_display": actor_display,
                    "decision": act.action_type.capitalize(),
                    "comment": (
                        "Comment not shared with you." if is_redacted else (act.comment or "")
                    ),
                    "decided_at": _format_dt(act.created_at),
                    "is_redacted": is_redacted,
                })
                # Only include non-redacted prior actors in the share-with picker:
                # offering a "Share with X" checkbox when X's action is hidden is
                # confusing (the current approver can't see what they'd be sharing about).
                if (
                    act.stage_index < req.current_stage
                    and not is_redacted
                    and str(act.actor_user_id) not in prior_actors_seen
                ):
                    prior_actors_seen[str(act.actor_user_id)] = actor_display
            self.steps = step_dicts
            self.prior_action_actors = [
                {"id": uid, "display": display}
                for uid, display in prior_actors_seen.items()
            ]

            # Phase 7F: load linked FacultyRequest for faculty_* processes
            if proc and proc.code.startswith("faculty_"):
                from durgam.repositories.faculty_request import FacultyRequestRepository
                fr_repo = FacultyRequestRepository(session)
                fr = fr_repo.get_by_approval_request_id(request_id)
                if fr is not None:
                    self.linked_faculty_request_id = str(fr.id)
                    self.linked_faculty_request_status = fr.status
                    if proc.code == "faculty_noc":
                        raw_payload = fr.payload_json or {}
                        self.noc_payload = {
                            "purpose": raw_payload.get("purpose", "—"),
                            "to_whom": raw_payload.get("to_whom", "—"),
                            "date_required_by": raw_payload.get("date_required_by", ""),
                            "additional_notes": raw_payload.get("additional_notes", ""),
                        }

            up_stmt = (
                select(FileAsset)
                .where(
                    FileAsset.purpose == "approval_upward",
                    FileAsset.is_deleted == False,  # noqa: E712
                )
            )
            up_files = session.exec(up_stmt).all()
            self.upward_attachments = [
                {
                    "id": str(f.id),
                    "name": f.original_name,
                    "size_kb": round(f.size_bytes / 1024, 1),
                }
                for f in up_files
                if (f.metadata_json or {}).get("approval_request_id") == str(request_id)
            ]

            down_stmt = (
                select(FileAsset)
                .where(
                    FileAsset.purpose == "approval_downward",
                    FileAsset.is_deleted == False,  # noqa: E712
                )
            )
            down_files = session.exec(down_stmt).all()
            step_by_approver: dict[UUID, tuple[str, int]] = {}
            for s in raw_steps:
                if s.approver_user_id and s.approver_user_id not in step_by_approver:
                    step_by_approver[s.approver_user_id] = (
                        s.approver_role_code,
                        s.stage,
                    )
            down_list: list[dict[str, Any]] = []
            for f in down_files:
                if (f.metadata_json or {}).get("approval_request_id") != str(request_id):
                    continue
                uploader_name = ""
                uploader_info = ""
                if f.owner_user_id:
                    uploader = session.get(User, f.owner_user_id)
                    if uploader:
                        uploader_name = uploader.full_name or uploader.username
                    role_stage = step_by_approver.get(f.owner_user_id)
                    if role_stage:
                        uploader_info = f"{uploader_name} ({role_stage[0]}, Stage {role_stage[1]})"
                    else:
                        uploader_info = uploader_name
                entry: dict[str, Any] = {
                    "id": str(f.id),
                    "name": f.original_name,
                    "size_kb": round(f.size_bytes / 1024, 1),
                    "uploader": uploader_info,
                }
                down_list.append(entry)
            self.downward_attachments = down_list

            self.can_withdraw = (
                self.viewer_is_requestor and req.state == "submitted"
            )

            # Phase 3: approver decision state
            from durgam.services.approval_routing import resolve_stage_approvers

            channel = proc.channel_role_codes or [] if proc else []
            # resolved_channel_json holds the per-request channel for leave requests;
            # it is authoritative for length and role-code lookup.
            resolved_channel = req.resolved_channel_json or []
            effective_len = len(resolved_channel) if resolved_channel else len(channel)
            self.is_terminal_stage = req.current_stage >= effective_len

            if req.state in ("submitted", "in_review") and proc and (channel or resolved_channel):
                stage_idx = req.current_stage - 1
                if resolved_channel and 0 <= stage_idx < len(resolved_channel):
                    entry = resolved_channel[stage_idx]
                    self.current_stage_role_code = entry.get("role_code", "") if isinstance(entry, dict) else ""
                elif 0 <= stage_idx < len(channel):
                    self.current_stage_role_code = channel[stage_idx]

                try:
                    approvers = resolve_stage_approvers(
                        request=req, process=proc, session=session,
                    )
                    approver_ids = {u.id for u in approvers}
                    self.viewer_is_current_stage_approver = viewer_id in approver_ids
                except Exception:
                    self.viewer_is_current_stage_approver = False

                self.can_decide = self.viewer_is_current_stage_approver

                # Preview next-stage approvers for non-terminal stages
                if self.can_decide and not self.is_terminal_stage:
                    try:
                        next_stage = req.current_stage + 1
                        next_idx = next_stage - 1
                        if next_idx < effective_len:
                            simulated_req = type(req).model_validate(req)
                            simulated_req.current_stage = next_stage
                            next_approvers = resolve_stage_approvers(
                                request=simulated_req,
                                process=proc,
                                session=session,
                            )
                            names = [
                                a.full_name or a.username
                                for a in next_approvers[:3]
                            ]
                            if len(next_approvers) > 3:
                                names.append(f"and {len(next_approvers) - 3} more")
                            self.next_stage_approvers_preview = names
                    except Exception:
                        self.next_stage_approvers_preview = []

                # Downward attachment config
                if proc:
                    self.process_allows_downward = (
                        proc.max_downward_attachments > 0
                        or not proc.requires_downward_attachments
                    )
                    self.process_requires_downward = proc.requires_downward_attachments
                    self.process_max_downward = proc.max_downward_attachments

            # M8 — LEAVE_APPROVAL specific data loading
            if proc and proc.code == "LEAVE_APPROVAL":
                from durgam.models.leave import LeaveBalance, LeaveRequest
                from durgam.repositories.leave import LeaveBalanceRepository, LeaveRepository

                leave_req_id_str = (req.payload_json or {}).get("leave_request_id", "")
                if leave_req_id_str:
                    try:
                        leave_req_id = UUID(leave_req_id_str)
                        leave_repo = LeaveRepository(session)
                        lr = leave_repo.get(leave_req_id)
                        if lr is not None:
                            self.is_leave_request = True
                            self.leave_type = lr.leave_type
                            self.leave_starts_on = lr.starts_on.isoformat()
                            self.leave_ends_on = lr.ends_on.isoformat()
                            self.leave_chargeable_days = lr.chargeable_days
                            self.leave_sanctioned_days_current = lr.sanctioned_days or 0.0
                            self.leave_state = lr.state
                            self.leave_has_medical_cert = lr.medical_cert_file_id is not None
                            self.leave_has_fitness_cert = lr.fitness_cert_file_id is not None
                            self.leave_has_bond = lr.bond_file_id is not None
                            self.leave_medical_cert_file_id = str(lr.medical_cert_file_id) if lr.medical_cert_file_id else ""
                            self.leave_fitness_cert_file_id = str(lr.fitness_cert_file_id) if lr.fitness_cert_file_id else ""
                            self.leave_bond_file_id = str(lr.bond_file_id) if lr.bond_file_id else ""

                            # Load requestor's balance for this leave type
                            bal_type = "HPL" if lr.leave_type == "CML" else lr.leave_type
                            if bal_type not in {"EOL", "SL", "SCL"}:
                                bal_repo = LeaveBalanceRepository(session)
                                bal = bal_repo.get(lr.requestor_user_id, bal_type, lr.academic_year_id)
                                if bal is not None:
                                    self.leave_requestor_balance = {
                                        "leave_type": bal.leave_type,
                                        "opening": bal.opening_balance,
                                        "credited": bal.credited,
                                        "availed": bal.availed,
                                        "closing": bal.closing_balance,
                                    }
                    except (ValueError, Exception):
                        pass  # malformed leave_request_id — leave is_leave_request=False

                # Check if current stage is recommend-only
                resolved = req.resolved_channel_json or []
                stage_idx = req.current_stage - 1
                if 0 <= stage_idx < len(resolved):
                    entry = resolved[stage_idx]
                    if isinstance(entry, dict) and entry.get("recommend_only"):
                        self.current_stage_is_recommend_only = True

        self.loading = False
        self._load_nav_entries()

    def open_withdraw_confirm(self) -> None:
        self.confirm_withdraw_open = True

    def cancel_withdraw(self) -> None:
        self.confirm_withdraw_open = False

    async def withdraw_request(self) -> None:
        self.confirm_withdraw_open = False
        if not self.can_withdraw:
            self.error = "Cannot withdraw this request."
            return

        from durgam.services.approval_request import (
            ApprovalRequestError,
            ApprovalRequestService,
        )

        request_id_str = self.request.get("id", "")
        if not request_id_str:
            return

        try:
            with open_session() as session:
                # Phase 7F: if a FacultyRequest is linked, delegate to FacultyRequestService
                # so the FacultyRequest.status is also synced to "withdrawn".
                if self.linked_faculty_request_id:
                    from durgam.services.faculty_request import (
                        FacultyRequestService,
                        InvalidRequestStatusTransitionError,
                        UnauthorizedWithdrawError,
                    )
                    try:
                        fr_svc = FacultyRequestService(session)
                        fr_svc.withdraw_request(
                            UUID(self.linked_faculty_request_id),
                            UUID(self.current_user_id),
                        )
                        session.commit()
                    except (InvalidRequestStatusTransitionError, UnauthorizedWithdrawError) as e:
                        self.error = str(e)
                        return
                else:
                    svc = ApprovalRequestService(session)
                    svc.withdraw(
                        request_id=UUID(request_id_str),
                        requestor_user_id=UUID(self.current_user_id),
                    )
                    session.commit()
        except ApprovalRequestError as e:
            self.error = str(e)
            return

        await self.load_detail()

    # Phase 3 — decision dialog handlers

    def open_approve_dialog(self) -> None:
        self.approve_dialog_open = True
        self.decision_error = ""

    def close_approve_dialog(self) -> None:
        self.approve_dialog_open = False
        self.decision_comment = ""
        self.decision_downward_file_ids = []
        self.decision_error = ""

    def open_reject_dialog(self) -> None:
        self.reject_dialog_open = True
        self.decision_error = ""

    def close_reject_dialog(self) -> None:
        self.reject_dialog_open = False
        self.decision_comment = ""
        self.decision_downward_file_ids = []
        self.decision_error = ""

    def set_decision_comment(self, value: str) -> None:
        self.decision_comment = value

    async def handle_decision_upload(self, files: list[rx.UploadFile]) -> None:
        from durgam.repositories.file_asset import FileAssetRepository
        from durgam.services.upload import UploadService
        from durgam.storage import get_storage_backend

        if not files:
            return

        with open_session() as session:
            svc = UploadService(
                file_repo=FileAssetRepository(session),
                backend=get_storage_backend(),
            )
            for f in files:
                content = await f.read()
                if not content:
                    continue
                asset = svc.upload(
                    data=content,
                    original_name=f.filename or "attachment",
                    mime_type=f.content_type or "application/octet-stream",
                    actor_id=UUID(self.current_user_id),
                    purpose="approval_downward",
                )
                self.decision_downward_file_ids = [
                    *self.decision_downward_file_ids,
                    str(asset.id),
                ]
            session.commit()

    def remove_decision_file(self, file_id: str) -> None:
        self.decision_downward_file_ids = [
            fid for fid in self.decision_downward_file_ids if fid != file_id
        ]

    async def submit_approve(self) -> None:
        if not self.can_decide:
            self.decision_error = "You cannot approve this request."
            return

        self.decision_submitting = True
        self.decision_error = ""

        from durgam.services.approval_request import (
            ApprovalRequestError,
            ApprovalRequestService,
        )

        request_id_str = self.request.get("id", "")
        if not request_id_str:
            self.decision_submitting = False
            return

        try:
            with open_session() as session:
                # M8 — partial sanction: apply set_sanctioned_days before approval if specified
                if self.is_leave_request and self.sanctioned_days_input.strip():
                    from durgam.repositories.leave import (
                        LeaveBalanceRepository,
                        LeaveRepository,
                        LeaveSanctionRuleRepository,
                    )
                    from durgam.repositories.approval_request import ApprovalRequestRepository
                    from durgam.services.approval_request import ApprovalRequestService
                    from durgam.services.leave_request import LeaveRequestError, LeaveRequestService

                    try:
                        sd = float(self.sanctioned_days_input.strip())
                    except ValueError:
                        self.decision_error = "Sanctioned days must be a number."
                        self.decision_submitting = False
                        return
                    if sd <= 0 or sd > self.leave_chargeable_days:
                        self.decision_error = (
                            f"Sanctioned days must be > 0 and ≤ {self.leave_chargeable_days}."
                        )
                        self.decision_submitting = False
                        return

                    leave_req_id_str = self.request.get("id", "")
                    # Find the LeaveRequest via ApprovalRequest id
                    req_repo = ApprovalRequestRepository(session)
                    ar = req_repo.get_by_id(UUID(request_id_str))
                    if ar is not None:
                        leave_req_id_raw = (ar.payload_json or {}).get("leave_request_id", "")
                        if leave_req_id_raw:
                            leave_svc = LeaveRequestService(
                                session=session,
                                leave_repo=LeaveRepository(session),
                                balance_repo=LeaveBalanceRepository(session),
                                rule_repo=LeaveSanctionRuleRepository(session),
                                approval_service=ApprovalRequestService(session),
                            )
                            try:
                                leave_svc.set_sanctioned_days(
                                    UUID(leave_req_id_raw),
                                    UUID(self.current_user_id),
                                    sd,
                                )
                            except LeaveRequestError as e:
                                self.decision_error = str(e)
                                self.decision_submitting = False
                                return

                svc = ApprovalRequestService(session)
                svc.approve(
                    request_id=UUID(request_id_str),
                    approver_user_id=UUID(self.current_user_id),
                    comment=self.decision_comment.strip() or None,
                    downward_attachment_file_ids=(
                        [UUID(fid) for fid in self.decision_downward_file_ids]
                        if self.decision_downward_file_ids
                        else None
                    ),
                    is_visible_to_requestor=not self.decision_hide_from_requestor,
                    visible_to_lower_user_ids=(
                        [UUID(uid) for uid in self.decision_share_with_user_ids]
                        if self.decision_share_with_user_ids
                        else None
                    ),
                )
                session.commit()
        except ApprovalRequestError as e:
            self.decision_error = str(e)
            self.decision_submitting = False
            return
        except Exception as e:
            log.error(
                "submit_approve_failed",
                exc_info=True,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            self.decision_error = "An unexpected error occurred."
            self.decision_submitting = False
            return

        self.approve_dialog_open = False
        self.decision_submitting = False
        await self.load_detail()

    async def recommend_stage(self) -> None:
        """SCL-style recommend: calls approve() — engine records decision='recommended'
        when the current channel entry has recommend_only=True."""
        if not self.can_decide:
            self.decision_error = "You cannot recommend at this stage."
            return

        self.decision_submitting = True
        self.decision_error = ""

        from durgam.services.approval_request import (
            ApprovalRequestError,
            ApprovalRequestService,
        )

        request_id_str = self.request.get("id", "")
        if not request_id_str:
            self.decision_submitting = False
            return

        try:
            with open_session() as session:
                svc = ApprovalRequestService(session)
                svc.approve(
                    request_id=UUID(request_id_str),
                    approver_user_id=UUID(self.current_user_id),
                    comment=self.decision_comment.strip() or None,
                )
                session.commit()
        except ApprovalRequestError as e:
            self.decision_error = str(e)
            self.decision_submitting = False
            return
        except Exception as e:
            log.error(
                "recommend_stage_failed",
                exc_info=True,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            self.decision_error = "An unexpected error occurred."
            self.decision_submitting = False
            return

        self.decision_submitting = False
        await self.load_detail()

    async def submit_reject(self) -> None:
        if not self.can_decide:
            self.decision_error = "You cannot reject this request."
            return

        if not self.decision_comment.strip():
            self.decision_error = "A reason for rejection is required."
            return

        self.decision_submitting = True
        self.decision_error = ""

        from durgam.services.approval_request import (
            ApprovalRequestError,
            ApprovalRequestService,
        )

        request_id_str = self.request.get("id", "")
        if not request_id_str:
            self.decision_submitting = False
            return

        try:
            with open_session() as session:
                svc = ApprovalRequestService(session)
                svc.reject(
                    request_id=UUID(request_id_str),
                    approver_user_id=UUID(self.current_user_id),
                    comment=self.decision_comment.strip(),
                    is_visible_to_requestor=not self.decision_hide_from_requestor,
                    visible_to_lower_user_ids=(
                        [UUID(uid) for uid in self.decision_share_with_user_ids]
                        if self.decision_share_with_user_ids
                        else None
                    ),
                )
                session.commit()
        except ApprovalRequestError as e:
            self.decision_error = str(e)
            self.decision_submitting = False
            return
        except Exception as e:
            log.error(
                "submit_reject_failed",
                exc_info=True,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            self.decision_error = "An unexpected error occurred."
            self.decision_submitting = False
            return

        self.reject_dialog_open = False
        self.decision_submitting = False
        await self.load_detail()
