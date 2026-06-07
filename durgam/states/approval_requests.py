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
    if dt is None:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M UTC")


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
    rows: list[dict[str, Any]] = []
    loading: bool = True

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
        self.rows = []

        from durgam.models.identity import User
        from durgam.repositories.approval_process import ApprovalProcessRepository
        from durgam.repositories.approval_request import ApprovalRequestRepository
        from durgam.services.approval_routing import resolve_stage_approvers

        with open_session() as session:
            req_repo = ApprovalRequestRepository(session)
            proc_repo = ApprovalProcessRepository(session)

            pending = req_repo.list_by_states(["submitted", "in_review"])

            viewer_id = UUID(self.current_user_id)
            proc_cache: dict[UUID, Any] = {}
            enriched: list[dict[str, Any]] = []

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
                requestor = session.get(User, r.requestor_user_id)
                requestor_display = (
                    (requestor.full_name or requestor.username) if requestor else "Unknown"
                )

                enriched.append({
                    "id": str(r.id),
                    "title": r.title,
                    "process_code": proc.code,
                    "process_title": proc.title,
                    "requestor_display": requestor_display,
                    "current_stage_label": _stage_label(r.current_stage, channel_len, r.state),
                    "submitted_at_display": _format_dt(r.created_at),
                    "state": r.state,
                })
            self.rows = enriched

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
    decision_comment: str = ""
    decision_downward_file_ids: list[str] = []
    decision_submitting: bool = False
    decision_error: str = ""
    process_allows_downward: bool = False
    process_requires_downward: bool = False
    process_max_downward: int = 0

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
            }

            self.process = {
                "code": proc.code if proc else "",
                "title": proc.title if proc else "",
            }

            raw_steps = step_repo.list_for_request(request_id)
            step_dicts: list[dict[str, Any]] = []
            for s in raw_steps:
                approver = session.get(User, s.approver_user_id) if s.approver_user_id else None
                approver_display = (approver.full_name or approver.username) if approver else "—"
                step_dicts.append({
                    "stage": s.stage,
                    "approver_role_code": s.approver_role_code,
                    "approver_display": approver_display,
                    "decision": s.decision or "—",
                    "comment": s.comment or "",
                    "decided_at": _format_dt(s.decided_at),
                })
            self.steps = step_dicts

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
            self.is_terminal_stage = req.current_stage >= len(channel)

            if req.state in ("submitted", "in_review") and proc and channel:
                stage_idx = req.current_stage - 1
                if 0 <= stage_idx < len(channel):
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
                        if next_idx < len(channel):
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
