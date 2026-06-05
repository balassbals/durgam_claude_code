"""States for requestor-facing approval pages (M7 Phase 2).

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


# ── Submit Request ─────────────────────────────────────────────────────


class SubmitRequestState(BaseState):
    process_options: list[dict[str, Any]] = []
    selected_process_id: str = "none"
    title: str = ""
    description: str = ""
    uploaded_file_ids: list[str] = []
    submitting: bool = False
    error: str = ""

    @rx.var
    def selected_process(self) -> dict[str, Any]:
        for p in self.process_options:
            if p["id"] == self.selected_process_id:
                return p
        return {}

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
        return self.submitting

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

        from durgam.services.approval_request import (
            ApprovalRequestError,
            ApprovalRequestService,
        )

        try:
            with open_session() as session:
                svc = ApprovalRequestService(session)
                request = svc.submit(
                    process_id=UUID(self.selected_process_id),
                    requestor_user_id=UUID(self.current_user_id),
                    title=self.title.strip(),
                    payload={"description": self.description.strip()} if self.description.strip() else None,
                    upward_attachment_file_ids=[UUID(fid) for fid in self.uploaded_file_ids] if self.uploaded_file_ids else None,
                )
                session.commit()
                new_id = str(request.id)

            self.submitting = False
            return rx.redirect(f"/approvals/request/{new_id}")
        except ApprovalRequestError as e:
            self.error = str(e)
            self.submitting = False
        except Exception:
            log.exception("submit_request_failed")
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

        request_id_str = self.router.page.params.get("request_id", "")
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

            svc = ApprovalRequestService(session)
            svc.view_request(request_id=request_id, viewer_user_id=viewer_id)
            session.commit()

            req = req_repo.get_by_id(request_id)
            if req is None:
                self.error = "Request not found."
                self.loading = False
                return

            proc = proc_repo.get_by_id(req.process_id)
            channel_len = len(proc.channel_role_codes) if proc and proc.channel_role_codes else 0

            requestor = session.get(User, req.requestor_user_id)
            requestor_name = requestor.full_name or requestor.username if requestor else "Unknown"

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
            self.downward_attachments = [
                {
                    "id": str(f.id),
                    "name": f.original_name,
                    "size_kb": round(f.size_bytes / 1024, 1),
                }
                for f in down_files
                if (f.metadata_json or {}).get("approval_request_id") == str(request_id)
            ]

            self.can_withdraw = (
                self.viewer_is_requestor and req.state == "submitted"
            )

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
