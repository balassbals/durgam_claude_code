"""ApprovalRequestService — state machine for approval requests.

Each transition is atomic: state change + audit row + notifications in one
session transaction. The caller owns the session and calls session.commit().
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlmodel import Session, select

from durgam.audit.log import write_audit_row
from durgam.models.crosscutting import (
    ApprovalProcess,
    ApprovalRequest,
    ApprovalStep,
    FileAsset,
    Notification,
)
from durgam.models.identity import Role, User, UserRole
from durgam.repositories.approval_process import ApprovalProcessRepository
from durgam.repositories.approval_request import ApprovalRequestRepository
from durgam.repositories.approval_step import ApprovalStepRepository
from durgam.services.approval_routing import (
    ApprovalRoutingError,
    resolve_stage_approvers,
)

log = structlog.get_logger(__name__)

_TERMINAL_STATES = frozenset({"approved", "rejected", "withdrawn", "cancelled"})


class ApprovalRequestError(Exception):
    pass


class ApprovalRequestService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._req_repo = ApprovalRequestRepository(session)
        self._step_repo = ApprovalStepRepository(session)
        self._proc_repo = ApprovalProcessRepository(session)

    def submit(
        self,
        *,
        process_id: UUID,
        requestor_user_id: UUID,
        title: str,
        payload: dict[str, Any] | None = None,
        upward_attachment_file_ids: list[UUID] | None = None,
    ) -> ApprovalRequest:
        process = self._proc_repo.get_by_id(process_id)
        if process is None:
            raise ApprovalRequestError("Approval process not found.")

        self._verify_requestor_role(process, requestor_user_id)
        self._validate_upward_attachments(process, upward_attachment_file_ids)

        now = datetime.now(UTC)
        request = ApprovalRequest(
            process_id=process_id,
            requestor_user_id=requestor_user_id,
            title=title.strip(),
            payload_json=payload,
            state="submitted",
            current_stage=1,
            created_by=requestor_user_id,
            updated_by=requestor_user_id,
            created_at=now,
            updated_at=now,
        )
        request = self._req_repo.save(request)

        self._link_attachments(
            upward_attachment_file_ids or [],
            request.id,
            "approval_upward",
        )

        approvers = self._resolve_approvers(request, process)

        self._enqueue_notifications(
            recipients=approvers,
            subject=f"New approval request: {request.title}",
            body=f"A new request '{request.title}' has been submitted and requires your review.",
            request=request,
            process=process,
            action="submit",
        )

        write_audit_row(
            actor_user_id=requestor_user_id,
            actor_role_code=None,
            action="submit",
            resource="approval_request",
            resource_id=str(request.id),
            request_id=None,
            ip=None,
            user_agent=None,
            before=None,
            after={"state": "submitted", "stage": 1, "title": request.title},
            session=self._session,
        )

        log.info(
            "approval_request_submitted",
            request_id=str(request.id),
            process_id=str(process_id),
            requestor=str(requestor_user_id),
        )
        return request

    def view_request(
        self,
        *,
        request_id: UUID,
        viewer_user_id: UUID,
    ) -> ApprovalRequest:
        request = self._req_repo.get_by_id(request_id)
        if request is None:
            raise ApprovalRequestError("Approval request not found.")

        process = self._proc_repo.get_by_id(request.process_id)
        if process is None:
            return request

        if request.state == "submitted":
            approvers = self._resolve_approvers(request, process)
            approver_ids = {u.id for u in approvers}
            if viewer_user_id in approver_ids:
                self._req_repo.update_state(request, "in_review")

                write_audit_row(
                    actor_user_id=viewer_user_id,
                    actor_role_code=None,
                    action="view_first_review",
                    resource="approval_request",
                    resource_id=str(request.id),
                    request_id=None,
                    ip=None,
                    user_agent=None,
                    before={"state": "submitted"},
                    after={"state": "in_review"},
                    session=self._session,
                )

        return request

    def approve(
        self,
        *,
        request_id: UUID,
        approver_user_id: UUID,
        comment: str | None = None,
        downward_attachment_file_ids: list[UUID] | None = None,
    ) -> ApprovalRequest:
        request = self._req_repo.get_by_id(request_id)
        if request is None:
            raise ApprovalRequestError("Approval request not found.")

        process = self._proc_repo.get_by_id(request.process_id)
        if process is None:
            raise ApprovalRequestError("Associated approval process not found.")

        if request.state in _TERMINAL_STATES:
            raise ApprovalRequestError(
                f"Cannot approve: request is already {request.state}."
            )

        if request.state == "submitted":
            self._req_repo.update_state(request, "in_review")

        approvers = self._resolve_approvers(request, process)
        approver_ids = {u.id for u in approvers}
        if approver_user_id not in approver_ids:
            raise ApprovalRequestError(
                "You are not an approver for the current stage."
            )

        self._validate_downward_attachments(process, downward_attachment_file_ids)

        channel = process.channel_role_codes or []
        role_code = channel[request.current_stage - 1]
        now = datetime.now(UTC)

        step = ApprovalStep(
            request_id=request.id,
            stage=request.current_stage,
            approver_role_code=role_code,
            approver_user_id=approver_user_id,
            decision="approved",
            comment=comment,
            decided_at=now,
        )
        self._step_repo.create(step)

        self._link_attachments(
            downward_attachment_file_ids or [],
            request.id,
            "approval_downward",
        )

        is_terminal = request.current_stage >= len(channel)

        if is_terminal:
            self._req_repo.update_state(request, "approved", decided_at=now)

            requestor = self._session.get(User, request.requestor_user_id)
            recipients = [requestor] if requestor else []
            cc_users = self._get_cc_users(process)
            recipients.extend(cc_users)

            self._enqueue_notifications(
                recipients=recipients,
                subject=f"Request approved: {request.title}",
                body=f"Your request '{request.title}' has been approved.",
                request=request,
                process=process,
                action="approve",
            )

            write_audit_row(
                actor_user_id=approver_user_id,
                actor_role_code=role_code,
                action="approve",
                resource="approval_request",
                resource_id=str(request.id),
                request_id=None,
                ip=None,
                user_agent=None,
                before={"state": "in_review", "stage": request.current_stage},
                after={"state": "approved", "stage": request.current_stage},
                session=self._session,
            )
        else:
            old_stage = request.current_stage
            self._req_repo.advance_stage(request)

            new_approvers = self._resolve_approvers(request, process)

            self._enqueue_notifications(
                recipients=new_approvers,
                subject=f"Request forwarded for review: {request.title}",
                body=(
                    f"Request '{request.title}' has been approved at stage "
                    f"{old_stage} and forwarded to you for review."
                ),
                request=request,
                process=process,
                action="forward",
            )

            write_audit_row(
                actor_user_id=approver_user_id,
                actor_role_code=role_code,
                action="forward",
                resource="approval_request",
                resource_id=str(request.id),
                request_id=None,
                ip=None,
                user_agent=None,
                before={"state": "in_review", "stage": old_stage},
                after={"state": "in_review", "stage": request.current_stage},
                session=self._session,
            )

        log.info(
            "approval_request_approved",
            request_id=str(request.id),
            approver=str(approver_user_id),
            terminal=is_terminal,
        )
        return request

    def reject(
        self,
        *,
        request_id: UUID,
        approver_user_id: UUID,
        comment: str,
    ) -> ApprovalRequest:
        if not comment or not comment.strip():
            raise ApprovalRequestError("A comment is required when rejecting.")

        request = self._req_repo.get_by_id(request_id)
        if request is None:
            raise ApprovalRequestError("Approval request not found.")

        process = self._proc_repo.get_by_id(request.process_id)
        if process is None:
            raise ApprovalRequestError("Associated approval process not found.")

        if request.state in _TERMINAL_STATES:
            raise ApprovalRequestError(
                f"Cannot reject: request is already {request.state}."
            )

        if request.state == "submitted":
            self._req_repo.update_state(request, "in_review")

        approvers = self._resolve_approvers(request, process)
        approver_ids = {u.id for u in approvers}
        if approver_user_id not in approver_ids:
            raise ApprovalRequestError(
                "You are not an approver for the current stage."
            )

        channel = process.channel_role_codes or []
        role_code = channel[request.current_stage - 1]
        now = datetime.now(UTC)

        step = ApprovalStep(
            request_id=request.id,
            stage=request.current_stage,
            approver_role_code=role_code,
            approver_user_id=approver_user_id,
            decision="rejected",
            comment=comment.strip(),
            decided_at=now,
        )
        self._step_repo.create(step)

        old_state = request.state
        self._req_repo.update_state(request, "rejected", decided_at=now)

        requestor = self._session.get(User, request.requestor_user_id)
        recipients = [requestor] if requestor else []
        cc_users = self._get_cc_users(process)
        recipients.extend(cc_users)

        self._enqueue_notifications(
            recipients=recipients,
            subject=f"Request rejected: {request.title}",
            body=f"Your request '{request.title}' has been rejected. Reason: {comment.strip()}",
            request=request,
            process=process,
            action="reject",
        )

        write_audit_row(
            actor_user_id=approver_user_id,
            actor_role_code=role_code,
            action="reject",
            resource="approval_request",
            resource_id=str(request.id),
            request_id=None,
            ip=None,
            user_agent=None,
            before={"state": old_state, "stage": request.current_stage},
            after={
                "state": "rejected",
                "stage": request.current_stage,
                "comment": comment.strip(),
            },
            session=self._session,
        )

        log.info(
            "approval_request_rejected",
            request_id=str(request.id),
            approver=str(approver_user_id),
        )
        return request

    def withdraw(
        self,
        *,
        request_id: UUID,
        requestor_user_id: UUID,
    ) -> ApprovalRequest:
        request = self._req_repo.get_by_id(request_id)
        if request is None:
            raise ApprovalRequestError("Approval request not found.")

        if request.requestor_user_id != requestor_user_id:
            raise ApprovalRequestError("Only the requestor can withdraw.")

        if request.state != "submitted":
            raise ApprovalRequestError(
                f"Cannot withdraw: request is in '{request.state}' state. "
                "Withdrawal is only allowed while the request is 'submitted'."
            )

        now = datetime.now(UTC)
        self._req_repo.update_state(request, "withdrawn", decided_at=now)

        process = self._proc_repo.get_by_id(request.process_id)
        if process is not None:
            approvers = self._resolve_approvers(request, process)
            self._enqueue_notifications(
                recipients=approvers,
                subject=f"Request withdrawn: {request.title}",
                body=f"The request '{request.title}' has been withdrawn by the requestor.",
                request=request,
                process=process,
                action="withdraw",
            )

        write_audit_row(
            actor_user_id=requestor_user_id,
            actor_role_code=None,
            action="withdraw",
            resource="approval_request",
            resource_id=str(request.id),
            request_id=None,
            ip=None,
            user_agent=None,
            before={"state": "submitted", "stage": request.current_stage},
            after={"state": "withdrawn", "stage": request.current_stage},
            session=self._session,
        )

        log.info(
            "approval_request_withdrawn",
            request_id=str(request.id),
            requestor=str(requestor_user_id),
        )
        return request

    def cancel(
        self,
        *,
        request_id: UUID,
        sys_admin_user_id: UUID,
        comment: str,
    ) -> ApprovalRequest:
        if not self._is_system_admin(sys_admin_user_id):
            raise ApprovalRequestError(
                "Only a System Administrator can cancel requests."
            )

        request = self._req_repo.get_by_id(request_id)
        if request is None:
            raise ApprovalRequestError("Approval request not found.")

        if request.state in _TERMINAL_STATES:
            raise ApprovalRequestError(
                f"Cannot cancel: request is already {request.state}."
            )

        now = datetime.now(UTC)
        old_state = request.state
        self._req_repo.update_state(request, "cancelled", decided_at=now)

        requestor = self._session.get(User, request.requestor_user_id)
        if requestor is not None:
            process = self._proc_repo.get_by_id(request.process_id)
            self._enqueue_notifications(
                recipients=[requestor],
                subject=f"Request cancelled: {request.title}",
                body=(
                    f"Your request '{request.title}' has been cancelled by "
                    f"a System Administrator. Reason: {comment.strip()}"
                ),
                request=request,
                process=process,
                action="cancel",
            )

        write_audit_row(
            actor_user_id=sys_admin_user_id,
            actor_role_code="SYSTEM_ADMIN",
            action="cancel",
            resource="approval_request",
            resource_id=str(request.id),
            request_id=None,
            ip=None,
            user_agent=None,
            before={"state": old_state, "stage": request.current_stage},
            after={
                "state": "cancelled",
                "stage": request.current_stage,
                "comment": comment.strip(),
            },
            session=self._session,
        )

        log.info(
            "approval_request_cancelled",
            request_id=str(request.id),
            admin=str(sys_admin_user_id),
        )
        return request

    # ── Private helpers ─────────────────────────────────────────────────

    def _verify_requestor_role(
        self,
        process: ApprovalProcess,
        user_id: UUID,
    ) -> None:
        if not process.requestor_role_codes:
            return
        user_roles = self._session.exec(
            select(UserRole).where(UserRole.user_id == user_id)
        ).all()
        user_role_codes: set[str] = set()
        for ur in user_roles:
            role = self._session.get(Role, ur.role_id)
            if role is not None and not role.is_deleted:
                user_role_codes.add(role.code)

        allowed = set(process.requestor_role_codes)
        if not user_role_codes & allowed:
            raise ApprovalRequestError(
                f"Requestor does not hold a required role: {allowed}."
            )

    def _validate_upward_attachments(
        self,
        process: ApprovalProcess,
        file_ids: list[UUID] | None,
    ) -> None:
        count = len(file_ids) if file_ids else 0
        if process.requires_upward_attachments and count < 1:
            raise ApprovalRequestError(
                "At least one upward attachment is required."
            )
        if process.max_upward_attachments > 0 and count > process.max_upward_attachments:
            raise ApprovalRequestError(
                f"Too many upward attachments: {count} provided, "
                f"maximum is {process.max_upward_attachments}."
            )

    def _validate_downward_attachments(
        self,
        process: ApprovalProcess,
        file_ids: list[UUID] | None,
    ) -> None:
        count = len(file_ids) if file_ids else 0
        if process.requires_downward_attachments and count < 1:
            raise ApprovalRequestError(
                "At least one downward attachment is required."
            )
        if process.max_downward_attachments > 0 and count > process.max_downward_attachments:
            raise ApprovalRequestError(
                f"Too many downward attachments: {count} provided, "
                f"maximum is {process.max_downward_attachments}."
            )

    def _link_attachments(
        self,
        file_ids: list[UUID],
        request_id: UUID,
        purpose: str,
    ) -> None:
        for fid in file_ids:
            asset = self._session.get(FileAsset, fid)
            if asset is not None and not asset.is_deleted:
                asset.purpose = purpose
                asset.metadata_json = {
                    **(asset.metadata_json or {}),
                    "approval_request_id": str(request_id),
                }
                self._session.add(asset)
        if file_ids:
            self._session.flush()

    def _resolve_approvers(
        self,
        request: ApprovalRequest,
        process: ApprovalProcess,
    ) -> list[User]:
        try:
            return resolve_stage_approvers(
                request=request,
                process=process,
                session=self._session,
            )
        except ApprovalRoutingError as e:
            log.warning("approver_resolution_failed", error=str(e))
            return []

    def _get_cc_users(self, process: ApprovalProcess) -> list[User]:
        if not process.informational_cc_role_codes:
            return []
        users: list[User] = []
        seen: set[UUID] = set()
        for rc in process.informational_cc_role_codes:
            role = self._session.exec(
                select(Role).where(
                    Role.code == rc,
                    Role.is_deleted == False,  # noqa: E712
                )
            ).first()
            if role is None:
                continue
            holders = self._session.exec(
                select(UserRole).where(UserRole.role_id == role.id)
            ).all()
            for h in holders:
                if h.user_id not in seen:
                    user = self._session.exec(
                        select(User).where(
                            User.id == h.user_id,
                            User.is_deleted == False,  # noqa: E712
                            User.is_active == True,  # noqa: E712
                        )
                    ).first()
                    if user is not None:
                        users.append(user)
                        seen.add(h.user_id)
        return users

    def _is_system_admin(self, user_id: UUID) -> bool:
        role = self._session.exec(
            select(Role).where(
                Role.code == "SYSTEM_ADMIN",
                Role.is_deleted == False,  # noqa: E712
            )
        ).first()
        if role is None:
            return False
        ur = self._session.exec(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role.id,
            )
        ).first()
        return ur is not None

    def _enqueue_notifications(
        self,
        recipients: list[User | None],
        subject: str,
        body: str,
        request: ApprovalRequest,
        process: ApprovalProcess | None,
        action: str,
    ) -> None:
        now = datetime.now(UTC)
        payload = {
            "approval_request_id": str(request.id),
            "action": action,
            "process_code": process.code if process else None,
        }
        seen: set[UUID] = set()
        for user in recipients:
            if user is None or user.id in seen:
                continue
            seen.add(user.id)
            for channel in ("in_app", "email"):
                notif = Notification(
                    recipient_user_id=user.id,
                    channel=channel,
                    subject=subject,
                    body_text=body,
                    payload_json=payload,
                    delivery_status="pending",
                    created_at=now,
                    updated_at=now,
                    created_by=request.requestor_user_id,
                    updated_by=request.requestor_user_id,
                )
                self._session.add(notif)
        self._session.flush()
