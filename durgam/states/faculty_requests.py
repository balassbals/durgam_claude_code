"""States for faculty request pages (M10 Phase 7B).

Three state classes:
- FacultyRequestsState: list page (/faculty/requests)
- NewFacultyRequestState: submit form (/faculty/requests/new)
- FacultyRequestDetailState: detail + withdraw (/faculty/requests/{id})
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import reflex as rx
import structlog

from durgam.db import open_session
from durgam.states.base import BaseState

log = structlog.get_logger(__name__)

_STATUS_LABELS: dict[str, str] = {
    "draft": "Draft",
    "submitted": "Submitted",
    "approved": "Approved",
    "rejected": "Rejected",
    "withdrawn": "Withdrawn",
}


def _fmt_status(s: str) -> str:
    return _STATUS_LABELS.get(s, s.capitalize())


def _resolve_or_redirect(state: BaseState):
    state._resolve_session()
    if not state.current_user_id:
        return rx.redirect("/login")
    return None


# ── List page ──────────────────────────────────────────────────────────────────


class FacultyRequestsState(BaseState):
    my_requests: list[dict[str, Any]] = []
    list_loading: bool = True

    async def load_my_requests(self) -> None:
        redirect = _resolve_or_redirect(self)
        if redirect is not None:
            return redirect

        self.list_loading = True
        self.my_requests = []

        from durgam.repositories.faculty import FacultyRepository
        from durgam.services.faculty_request import FacultyRequestService

        user_id = UUID(self.current_user_id)

        with open_session() as session:
            fac_repo = FacultyRepository(session)
            faculty = fac_repo.get_by_user_id(user_id)
            if faculty is None:
                self.list_loading = False
                return

            svc = FacultyRequestService(session)
            rows = svc.list_for_faculty(faculty.id)
            enriched: list[dict[str, Any]] = []
            for r in rows:
                payload = r.payload_json or {}
                enriched.append({
                    "id": str(r.id),
                    "request_type": r.request_type.replace("_", " ").title(),
                    "purpose": payload.get("purpose", "—")[:80],
                    "status": r.status,
                    "status_label": _fmt_status(r.status),
                    "submitted_at": r.updated_at.strftime("%Y-%m-%d") if r.updated_at else "—",
                })
            self.my_requests = enriched

        self.list_loading = False
        self._load_nav_entries()


# ── New request form ────────────────────────────────────────────────────────────


class NewFacultyRequestState(BaseState):
    draft_id: str = ""
    purpose: str = ""
    to_whom: str = ""
    date_required_by: str = ""
    additional_notes: str = ""
    attached_files: list[dict[str, Any]] = []
    form_error: str = ""
    submitting: bool = False

    def set_purpose(self, v: str) -> None:
        self.purpose = v

    def set_to_whom(self, v: str) -> None:
        self.to_whom = v

    def set_date_required_by(self, v: str) -> None:
        self.date_required_by = v

    def set_additional_notes(self, v: str) -> None:
        self.additional_notes = v

    @rx.var
    def can_upload(self) -> bool:
        return bool(self.draft_id)

    @rx.var
    def submit_disabled(self) -> bool:
        return (
            self.submitting
            or not self.draft_id
            or not self.purpose.strip()
            or not self.to_whom.strip()
        )

    async def init_new_request(self) -> None:
        redirect = _resolve_or_redirect(self)
        if redirect is not None:
            return redirect

        self.draft_id = ""
        self.purpose = ""
        self.to_whom = ""
        self.date_required_by = ""
        self.additional_notes = ""
        self.attached_files = []
        self.form_error = ""
        self.submitting = False

        from durgam.models.faculty_request import REQUEST_TYPE_NOC
        from durgam.repositories.faculty import FacultyRepository
        from durgam.services.faculty_request import FacultyRequestService, UnknownRequestTypeError

        user_id = UUID(self.current_user_id)

        with open_session() as session:
            fac_repo = FacultyRepository(session)
            faculty = fac_repo.get_by_user_id(user_id)
            if faculty is None:
                self.form_error = "No faculty profile found for your account."
                return

            svc = FacultyRequestService(session)
            try:
                draft = svc.create_request(
                    faculty_id=faculty.id,
                    request_type=REQUEST_TYPE_NOC,
                    payload=None,
                    actor_id=user_id,
                )
            except UnknownRequestTypeError as e:
                self.form_error = str(e)
                return

            self.draft_id = str(draft.id)
            session.commit()

        self._load_nav_entries()

    async def handle_upload(self, files: list[rx.UploadFile]) -> None:
        if not files or not self.draft_id:
            return

        from durgam.services.faculty_request import (
            AttachmentLimitExceededError,
            AttachmentNotConfiguredError,
            AttachmentTooLargeError,
            DisallowedMimeTypeError,
            FacultyRequestService,
        )

        user_id = UUID(self.current_user_id)
        request_id = UUID(self.draft_id)

        with open_session() as session:
            svc = FacultyRequestService(session)
            for f in files:
                content = await f.read()
                if not content:
                    continue
                try:
                    asset = svc.add_attachment(
                        request_id=request_id,
                        file_bytes=content,
                        filename=f.filename or "attachment",
                        mime_type=f.content_type or "application/octet-stream",
                        actor_id=user_id,
                    )
                    self.attached_files = [
                        *self.attached_files,
                        {
                            "id": str(asset.id),
                            "name": asset.original_name,
                            "size_kb": str(round(asset.size_bytes / 1024, 1)),
                        },
                    ]
                except (
                    AttachmentNotConfiguredError,
                    DisallowedMimeTypeError,
                    AttachmentTooLargeError,
                    AttachmentLimitExceededError,
                ) as e:
                    self.form_error = str(e)
                    return
            session.commit()

    def remove_attachment(self, file_id: str) -> None:
        from durgam.services.faculty_request import FacultyRequestService

        user_id = UUID(self.current_user_id)
        with open_session() as session:
            svc = FacultyRequestService(session)
            svc.remove_attachment(UUID(file_id), user_id)
            session.commit()
        self.attached_files = [f for f in self.attached_files if f["id"] != file_id]

    async def submit_request(self) -> None:
        self.form_error = ""
        if not self.purpose.strip():
            self.form_error = "Purpose is required."
            return
        if not self.to_whom.strip():
            self.form_error = "To Whom is required."
            return
        if not self.draft_id:
            self.form_error = "No draft request. Please reload the form."
            return

        self.submitting = True

        from durgam.services.faculty_request import (
            EmptyApproverPoolError,
            FacultyRequestService,
            InvalidRequestStatusTransitionError,
            UnknownRequestTypeError,
        )

        user_id = UUID(self.current_user_id)
        request_id = UUID(self.draft_id)

        payload: dict[str, Any] = {
            "purpose": self.purpose.strip(),
            "to_whom": self.to_whom.strip(),
        }
        if self.date_required_by:
            payload["date_required_by"] = self.date_required_by
        if self.additional_notes.strip():
            payload["additional_notes"] = self.additional_notes.strip()

        try:
            with open_session() as session:
                svc = FacultyRequestService(session)
                svc.update_payload(request_id, payload, user_id)
                svc.submit_for_approval(request_id, user_id)
                session.commit()

            self.submitting = False
            return rx.redirect(f"/faculty/requests/{self.draft_id}")
        except (
            InvalidRequestStatusTransitionError,
            UnknownRequestTypeError,
            EmptyApproverPoolError,
        ) as e:
            self.form_error = str(e)
            self.submitting = False
        except Exception as e:
            log.error("faculty_request_submit_failed", exc_info=True, error_type=type(e).__name__)
            self.form_error = "An unexpected error occurred. Please try again."
            self.submitting = False


# ── Detail page ─────────────────────────────────────────────────────────────────


class FacultyRequestDetailState(BaseState):
    detail: dict[str, Any] = {}
    attachments: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    detail_loading: bool = True
    detail_error: str = ""
    confirm_withdraw_open: bool = False

    async def load_detail(self) -> None:
        redirect = _resolve_or_redirect(self)
        if redirect is not None:
            return redirect

        self.detail_loading = True
        self.detail_error = ""
        self.detail = {}
        self.attachments = []
        self.actions = []
        self.confirm_withdraw_open = False

        request_id_str = self.router.page.params.get("faculty_request_id", "")
        if not request_id_str:
            self.detail_error = "Request not found."
            self.detail_loading = False
            return

        from durgam.repositories.faculty import FacultyRepository
        from durgam.services.faculty_request import FacultyRequestNotFoundError, FacultyRequestService
        from durgam.models.identity import User

        user_id = UUID(self.current_user_id)

        try:
            with open_session() as session:
                fac_repo = FacultyRepository(session)
                faculty = fac_repo.get_by_user_id(user_id)
                if faculty is None:
                    self.detail_error = "No faculty profile found for your account."
                    self.detail_loading = False
                    return

                svc = FacultyRequestService(session)
                request_id = UUID(request_id_str)
                row = svc.get_request(request_id)

                if row.faculty_id != faculty.id:
                    self.detail_error = "You do not have access to this request."
                    self.detail_loading = False
                    return

                payload = row.payload_json or {}
                self.detail = {
                    "id": str(row.id),
                    "request_type": row.request_type.replace("_", " ").title(),
                    "status": row.status,
                    "status_label": _fmt_status(row.status),
                    "purpose": payload.get("purpose", "—"),
                    "to_whom": payload.get("to_whom", "—"),
                    "date_required_by": payload.get("date_required_by", "—"),
                    "additional_notes": payload.get("additional_notes", ""),
                    "can_withdraw": row.status == "submitted",
                    "submitted_at": row.updated_at.strftime("%Y-%m-%d %H:%M UTC") if row.updated_at else "—",
                }

                attachments_raw = svc.list_attachments(request_id)
                self.attachments = [
                    {
                        "id": str(a.id),
                        "name": a.original_name,
                        "size_kb": str(round(a.size_bytes / 1024, 1)),
                    }
                    for a in attachments_raw
                ]

                actions_raw = svc.list_actions_for_requestor(request_id)
                enriched_actions: list[dict[str, Any]] = []
                for act in actions_raw:
                    actor = session.get(User, act.actor_user_id)
                    actor_display = (
                        (actor.full_name or actor.username) if actor else "Unknown"
                    )
                    enriched_actions.append({
                        "stage_index": str(act.stage_index),
                        "action_type": act.action_type.capitalize(),
                        "actor_display": actor_display,
                        "comment": act.comment or "",
                        "decided_at": act.created_at.strftime("%Y-%m-%d %H:%M UTC") if act.created_at else "—",
                    })
                self.actions = enriched_actions

        except FacultyRequestNotFoundError:
            self.detail_error = "Request not found."
            self.detail_loading = False
            return
        except ValueError:
            self.detail_error = "Invalid request ID."
            self.detail_loading = False
            return

        self.detail_loading = False
        self._load_nav_entries()

    def open_withdraw_confirm(self) -> None:
        self.confirm_withdraw_open = True

    def cancel_withdraw_confirm(self) -> None:
        self.confirm_withdraw_open = False

    async def withdraw_current_request(self) -> None:
        self.confirm_withdraw_open = False
        request_id_str = self.router.page.params.get("faculty_request_id", "")
        if not request_id_str:
            return

        from durgam.repositories.faculty import FacultyRepository
        from durgam.services.faculty_request import (
            FacultyRequestService,
            InvalidRequestStatusTransitionError,
            UnauthorizedWithdrawError,
        )

        user_id = UUID(self.current_user_id)

        try:
            with open_session() as session:
                fac_repo = FacultyRepository(session)
                faculty = fac_repo.get_by_user_id(user_id)
                if faculty is None:
                    self.detail_error = "No faculty profile found."
                    return

                svc = FacultyRequestService(session)
                svc.withdraw_request(UUID(request_id_str), user_id)
                session.commit()
        except (InvalidRequestStatusTransitionError, UnauthorizedWithdrawError) as e:
            self.detail_error = str(e)
            return
        except Exception as e:
            log.error("faculty_withdraw_failed", exc_info=True, error_type=type(e).__name__)
            self.detail_error = "An unexpected error occurred."
            return

        await self.load_detail()
