"""States for approver-side faculty request pages (M10 Phase 7C).

Two state classes:
- ApproverInboxState: inbox list (/approver/inbox)
- ApproverRequestDetailState: detail + approve/reject form (/approver/requests/{id})

Honest deviations (TD-083):
- @require_role uses action="approve", resource="approval_request", scope="*" (seeded)
  because faculty_request:approve:* and faculty_request:reject:* are not seeded.
- Comment on approve deferred to Phase 7D (approve_request() lacks comment param).
- Downward attachment upload deferred to Phase 7D (service params not exposed).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import reflex as rx
import structlog

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.states.base import BaseState

log = structlog.get_logger(__name__)


def _resolve_or_redirect(state: BaseState):
    state._resolve_session()
    if not state.current_user_id:
        return rx.redirect("/login")
    return None


# ── Approver inbox ─────────────────────────────────────────────────────────────


class ApproverInboxState(BaseState):
    inbox_items: list[dict[str, Any]] = []
    inbox_loading: bool = True
    inbox_error: str = ""

    async def load_inbox(self) -> None:
        redirect = _resolve_or_redirect(self)
        if redirect is not None:
            return redirect

        self.inbox_loading = True
        self.inbox_items = []
        self.inbox_error = ""

        from durgam.services.faculty_request import FacultyRequestService

        user_id = UUID(self.current_user_id)

        try:
            with open_session() as session:
                svc = FacultyRequestService(session)
                raw = svc.list_inbox_for_user(user_id)
                self.inbox_items = [
                    {
                        **item,
                        "request_type_label": item["request_type"].replace("_", " ").title(),
                        "submitted_at_display": item["submitted_at"][:10] if item["submitted_at"] else "—",
                    }
                    for item in raw
                ]
        except Exception as e:
            log.error("approver_inbox_load_failed", exc_info=True, error_type=type(e).__name__)
            self.inbox_error = "Failed to load inbox."

        self.inbox_loading = False
        self._load_nav_entries()


# ── Approver request detail ────────────────────────────────────────────────────


class ApproverRequestDetailState(BaseState):
    # Loaded data
    request: dict[str, Any] = {}
    attachments: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    prior_action_actors: list[dict[str, Any]] = []
    current_stage: int = 0
    user_eligible: bool = False
    detail_loading: bool = True
    detail_error: str = ""

    # Action form state
    action_comment: str = ""
    action_hide_from_requestor: bool = False
    action_share_with_user_ids: list[str] = []
    action_in_progress: bool = False
    action_error: str = ""

    # Downward attachments (approver-side; staged before approve/reject is clicked)
    action_downward_attachments: list[dict[str, Any]] = []

    def set_action_comment(self, v: str) -> None:
        self.action_comment = v

    def toggle_hide_from_requestor(self) -> None:
        self.action_hide_from_requestor = not self.action_hide_from_requestor

    def toggle_share_with(self, user_id: str) -> None:
        if user_id in self.action_share_with_user_ids:
            self.action_share_with_user_ids = [
                uid for uid in self.action_share_with_user_ids if uid != user_id
            ]
        else:
            self.action_share_with_user_ids = [*self.action_share_with_user_ids, user_id]

    @require_role(action="approve", resource="approval_request", scope="*")
    async def handle_downward_upload(self, files: list[rx.UploadFile]) -> None:
        """Upload approver-side PDFs (e.g., signed NOC). Validates MIME + size from
        ApprovalProcess config (allowed_attachment_mime_types_json, max_attachment_mb).
        Staged in action_downward_attachments until approve/reject is clicked.
        """
        if not files:
            return

        from durgam.services.faculty_request import (  # noqa: PLC0415
            AttachmentTooLargeError,
            DisallowedMimeTypeError,
            FacultyRequestService,
        )

        request_id_str = self.router.page.params.get("faculty_request_id", "")
        if not request_id_str:
            self.action_error = "Cannot upload: no request selected."
            return

        user_id = UUID(self.current_user_id)
        request_id = UUID(request_id_str)

        self.action_error = ""
        try:
            with open_session() as session:
                svc = FacultyRequestService(session)
                new_files: list[dict[str, Any]] = []
                for f in files:
                    content = await f.read()
                    if not content:
                        continue
                    asset = svc.add_downward_attachment(
                        request_id=request_id,
                        file_bytes=content,
                        filename=f.filename or "attachment.pdf",
                        mime_type=f.content_type or "application/octet-stream",
                        actor_id=user_id,
                    )
                    new_files.append({
                        "file_id": str(asset.id),
                        "name": asset.original_name,
                        "size": asset.size_bytes,
                    })
                session.commit()
            self.action_downward_attachments = [
                *self.action_downward_attachments,
                *new_files,
            ]
        except DisallowedMimeTypeError as e:
            self.action_error = str(e)
        except AttachmentTooLargeError as e:
            self.action_error = str(e)
        except Exception as e:
            log.error("downward_upload_failed", exc_info=True, error_type=type(e).__name__)
            self.action_error = "Upload failed. Please try again."

    @require_role(action="approve", resource="approval_request", scope="*")
    def remove_downward_attachment(self, file_id: str) -> None:
        """Remove a staged downward attachment from in-memory list (no DB action — the
        FileAsset row is retained for audit but won't be passed to approve/reject)."""
        self.action_downward_attachments = [
            f for f in self.action_downward_attachments if f["file_id"] != file_id
        ]

    async def load_detail(self) -> None:
        redirect = _resolve_or_redirect(self)
        if redirect is not None:
            return redirect

        self.detail_loading = True
        self.detail_error = ""
        self.request = {}
        self.attachments = []
        self.actions = []
        self.prior_action_actors = []
        self.current_stage = 0
        self.user_eligible = False
        self.action_comment = ""
        self.action_hide_from_requestor = False
        self.action_share_with_user_ids = []
        self.action_in_progress = False
        self.action_error = ""
        self.action_downward_attachments = []

        request_id_str = self.router.page.params.get("faculty_request_id", "")
        if not request_id_str:
            self.detail_error = "Request not found."
            self.detail_loading = False
            return

        from sqlmodel import select as _select  # noqa: PLC0415
        from durgam.models.crosscutting import ApprovalRequest  # noqa: PLC0415
        from durgam.models.faculty import Faculty  # noqa: PLC0415
        from durgam.models.identity import User  # noqa: PLC0415
        from durgam.services.approval_request import ApprovalRequestService  # noqa: PLC0415
        from durgam.services.faculty_request import (  # noqa: PLC0415
            FacultyRequestNotFoundError,
            FacultyRequestService,
        )

        user_id = UUID(self.current_user_id)

        try:
            with open_session() as session:
                svc = FacultyRequestService(session)
                request_id = UUID(request_id_str)
                row = svc.get_request(request_id)

                payload = row.payload_json or {}
                faculty = session.exec(
                    _select(Faculty).where(
                        Faculty.id == row.faculty_id,
                        Faculty.is_deleted == False,  # noqa: E712
                    )
                ).first()
                requestor_name = (
                    f"{faculty.first_name} {faculty.last_name}".strip() if faculty else "Unknown"
                )

                # Get current stage from linked ApprovalRequest
                approval_req = session.get(ApprovalRequest, row.approval_request_id)
                stage = approval_req.current_stage if approval_req else 0

                self.request = {
                    "id": str(row.id),
                    "request_type": row.request_type.replace("_", " ").title(),
                    "status": row.status,
                    "purpose": payload.get("purpose", "—"),
                    "to_whom": payload.get("to_whom", "—"),
                    "date_required_by": payload.get("date_required_by", "—"),
                    "additional_notes": payload.get("additional_notes", ""),
                    "requestor_name": requestor_name,
                    "submitted_at": row.updated_at.strftime("%Y-%m-%d %H:%M UTC") if row.updated_at else "—",
                }
                self.current_stage = stage

                # Attachments (upward — from faculty)
                attachments_raw = svc.list_attachments(request_id)
                self.attachments = [
                    {
                        "id": str(a.id),
                        "name": a.original_name,
                        "size_kb": str(round(a.size_bytes / 1024, 1)),
                    }
                    for a in attachments_raw
                ]

                # Eligibility check
                if row.approval_request_id:
                    apr_svc = ApprovalRequestService(session)
                    self.user_eligible = apr_svc.is_user_eligible_for_current_stage(
                        row.approval_request_id, user_id
                    )

                # Filtered actions for this approver at their current stage
                if row.approval_request_id and stage > 0:
                    actions_raw = svc.list_actions_for_approver(
                        request_id=request_id,
                        approver_user_id=user_id,
                        approver_stage=stage,
                    )
                    prior_actors_seen: dict[str, str] = {}
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
                            "actor_id": str(act.actor_user_id),
                            "comment": act.comment or "",
                            "decided_at": (
                                act.created_at.strftime("%Y-%m-%d %H:%M UTC")
                                if act.created_at else "—"
                            ),
                        })
                        # Collect prior-stage actors for share-with multi-select
                        if act.stage_index < stage and str(act.actor_user_id) not in prior_actors_seen:
                            prior_actors_seen[str(act.actor_user_id)] = actor_display

                    self.actions = enriched_actions
                    self.prior_action_actors = [
                        {"id": uid, "display": display}
                        for uid, display in prior_actors_seen.items()
                    ]

        except FacultyRequestNotFoundError:
            self.detail_error = "Request not found."
            self.detail_loading = False
            return
        except ValueError:
            self.detail_error = "Invalid request ID."
            self.detail_loading = False
            return
        except Exception as e:
            log.error("approver_detail_load_failed", exc_info=True, error_type=type(e).__name__)
            self.detail_error = "Failed to load request detail."
            self.detail_loading = False
            return

        self.detail_loading = False
        self._load_nav_entries()

    @require_role(action="approve", resource="approval_request", scope="*")
    @audit_action(action="approve", resource="faculty_request")
    async def approve(self) -> None:
        """Approve the current faculty request at the current stage."""
        self.action_error = ""
        self.action_in_progress = True

        request_id_str = self.router.page.params.get("faculty_request_id", "")
        if not request_id_str:
            self.action_error = "No request selected."
            self.action_in_progress = False
            return

        from durgam.services.faculty_request import (
            FacultyRequestService,
            StageAlreadyAdvancedError,
            UnauthorizedActorError,
        )

        user_id = UUID(self.current_user_id)
        request_id = UUID(request_id_str)
        is_visible = not self.action_hide_from_requestor
        share_with = [UUID(uid) for uid in self.action_share_with_user_ids] or None
        comment = self.action_comment.strip() or None
        file_ids = [UUID(f["file_id"]) for f in self.action_downward_attachments] or None

        try:
            with open_session() as session:
                svc = FacultyRequestService(session)
                svc.approve_request(
                    request_id=request_id,
                    actor_id=user_id,
                    comment=comment,
                    downward_attachment_file_ids=file_ids,
                    expected_stage_index=self.current_stage or None,
                    is_visible_to_requestor=is_visible,
                    visible_to_lower_user_ids=share_with,
                )
                session.commit()
            self._set_audit(resource_id=request_id_str)
        except StageAlreadyAdvancedError as e:
            self.action_error = str(e)
            self.action_in_progress = False
            return
        except UnauthorizedActorError as e:
            self.action_error = str(e)
            self.action_in_progress = False
            return
        except Exception as e:
            log.error("approver_approve_failed", exc_info=True, error_type=type(e).__name__)
            self.action_error = "Approve failed. Please try again."
            self.action_in_progress = False
            return

        self.action_in_progress = False
        return rx.redirect("/approver/inbox")

    @require_role(action="approve", resource="approval_request", scope="*")
    @audit_action(action="reject", resource="faculty_request")
    async def reject(self) -> None:
        """Reject the current faculty request. Comment is required."""
        self.action_error = ""

        if not self.action_comment.strip():
            self.action_error = "A comment is required to reject a request."
            return

        self.action_in_progress = True

        request_id_str = self.router.page.params.get("faculty_request_id", "")
        if not request_id_str:
            self.action_error = "No request selected."
            self.action_in_progress = False
            return

        from durgam.services.faculty_request import (
            FacultyRequestService,
            InvalidRejectReasonError,
            StageAlreadyAdvancedError,
            UnauthorizedActorError,
        )

        user_id = UUID(self.current_user_id)
        request_id = UUID(request_id_str)
        is_visible = not self.action_hide_from_requestor
        share_with = [UUID(uid) for uid in self.action_share_with_user_ids] or None
        file_ids = [UUID(f["file_id"]) for f in self.action_downward_attachments] or None

        try:
            with open_session() as session:
                svc = FacultyRequestService(session)
                svc.reject_request(
                    request_id=request_id,
                    actor_id=user_id,
                    reason=self.action_comment.strip(),
                    downward_attachment_file_ids=file_ids,
                    expected_stage_index=self.current_stage or None,
                    is_visible_to_requestor=is_visible,
                    visible_to_lower_user_ids=share_with,
                )
                session.commit()
            self._set_audit(resource_id=request_id_str)
        except InvalidRejectReasonError as e:
            self.action_error = str(e)
            self.action_in_progress = False
            return
        except StageAlreadyAdvancedError as e:
            self.action_error = str(e)
            self.action_in_progress = False
            return
        except UnauthorizedActorError as e:
            self.action_error = str(e)
            self.action_in_progress = False
            return
        except Exception as e:
            log.error("approver_reject_failed", exc_info=True, error_type=type(e).__name__)
            self.action_error = "Reject failed. Please try again."
            self.action_in_progress = False
            return

        self.action_in_progress = False
        return rx.redirect("/approver/inbox")
