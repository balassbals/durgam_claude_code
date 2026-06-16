"""FacultyRequestService — business rules for faculty-initiated requests (M10).

Layering: service owns validation rules; repositories own all SQL.
No session.commit() here — callers (page states) must commit.
No audit emissions in Phase 5A/5B — wired at state-handler boundary in Phase 7+.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Session

from durgam.models.crosscutting import ApprovalRequest, FileAsset
from durgam.models.faculty_request import (
    FACULTY_REQUEST_TYPES,
    STATUS_APPROVED,
    STATUS_DRAFT,
    STATUS_REJECTED,
    STATUS_SUBMITTED,
    STATUS_WITHDRAWN,
    FacultyRequest,
)
from durgam.repositories.approval_process import ApprovalProcessRepository
from durgam.repositories.faculty import FacultyRepository
from durgam.repositories.faculty_request import FacultyRequestRepository
from durgam.repositories.file_asset import FileAssetRepository
from durgam.services.approval_engine import (
    StageOptionMismatchError,
    resolve_stage_authority,
)
from durgam.services.approval_resolvers import ResolverContext
from durgam.storage.backend import StorageBackend


class UnknownRequestTypeError(ValueError):
    """request_type is not in FACULTY_REQUEST_TYPES, or no approval process is configured."""


class InvalidRequestStatusTransitionError(ValueError):
    """Operation not allowed in current status (e.g., update_payload on submitted request)."""


class FacultyRequestNotFoundError(ValueError):
    """FacultyRequest row not found or is soft-deleted."""


class EmptyApproverPoolError(ValueError):
    """Stage 1 resolver returned no approvers for this faculty's dept+campus."""


class StageAlreadyAdvancedError(ValueError):
    """expected_stage_index doesn't match current_stage — another approver acted first."""


class UnauthorizedActorError(PermissionError):
    """Actor is not in the approver pool for the current stage."""


class InvalidRejectReasonError(ValueError):
    """Reject reason is empty, whitespace-only, or exceeds 1000 chars."""


class UnauthorizedWithdrawError(PermissionError):
    """Actor is not the originating faculty for this FacultyRequest."""


class AttachmentNotConfiguredError(ValueError):
    """ApprovalProcess does not allow attachments for this request type."""


class DisallowedMimeTypeError(ValueError):
    """MIME type not in the process's allowed list."""


class AttachmentTooLargeError(ValueError):
    """File exceeds max_attachment_mb."""


class AttachmentLimitExceededError(ValueError):
    """Request has reached max_attachment_count (max_upward_attachments)."""


class UnauthorizedAttachmentError(PermissionError):
    """Actor cannot manage attachments for this FacultyRequest."""


class AttachmentNotFoundError(ValueError):
    """No attachment (FileAsset) with that ID linked to this request."""


class FacultyRequestService:
    def __init__(self, session: Session, storage_backend: StorageBackend | None = None) -> None:
        self._session = session
        self._repo = FacultyRequestRepository(session)
        self._faculty_repo = FacultyRepository(session)
        self._storage_backend = storage_backend

    def create_request(
        self,
        *,
        faculty_id: UUID,
        request_type: str,
        payload: dict | None,
        actor_id: UUID,
    ) -> FacultyRequest:
        if request_type not in FACULTY_REQUEST_TYPES:
            raise UnknownRequestTypeError(
                f"Unknown request type '{request_type}'. "
                f"Valid types: {sorted(FACULTY_REQUEST_TYPES)}"
            )
        faculty = self._faculty_repo.get(faculty_id)
        if faculty is None:
            raise ValueError(f"Faculty {faculty_id} not found")
        return self._repo.create(
            faculty_id=faculty_id,
            request_type=request_type,
            payload=payload,
            actor_id=actor_id,
        )

    def get_request(self, request_id: UUID) -> FacultyRequest:
        row = self._repo.get(request_id)
        if row is None:
            raise FacultyRequestNotFoundError(f"FacultyRequest {request_id} not found")
        return row

    def list_for_faculty(
        self,
        faculty_id: UUID,
        *,
        status: str | None = None,
    ) -> list[FacultyRequest]:
        return self._repo.list_by_faculty(faculty_id, status=status)

    def update_payload(
        self,
        request_id: UUID,
        payload: dict | None,
        actor_id: UUID,
    ) -> FacultyRequest:
        row = self._repo.get(request_id)
        if row is None:
            raise FacultyRequestNotFoundError(f"FacultyRequest {request_id} not found")
        if row.status != STATUS_DRAFT:
            raise InvalidRequestStatusTransitionError(
                f"Cannot update payload: request is in status '{row.status}'. "
                f"Payload updates are only allowed in draft status."
            )
        return self._repo.update(request_id, {"payload_json": payload}, actor_id)

    def soft_delete_request(self, request_id: UUID, actor_id: UUID) -> None:
        row = self._repo.get(request_id)
        if row is None:
            raise FacultyRequestNotFoundError(f"FacultyRequest {request_id} not found")
        self._repo.soft_delete(request_id, actor_id)

    def submit_for_approval(
        self,
        request_id: UUID,
        actor_id: UUID,
        picked_option_ids: dict[int, UUID] | None = None,
    ) -> FacultyRequest:
        """Transition a draft FacultyRequest to submitted and create an ApprovalRequest.

        Raises:
        - FacultyRequestNotFoundError if request_id not found
        - InvalidRequestStatusTransitionError if not in draft, or requestor pick required but missing
        - UnknownRequestTypeError if no approval process is seeded for this request_type
        - StageOptionMismatchError if picked_option_ids references an option not in Stage 1
        - EmptyApproverPoolError if Stage 1 resolver returns no approvers
        """
        row = self._repo.get(request_id)
        if row is None:
            raise FacultyRequestNotFoundError(f"FacultyRequest {request_id} not found")
        if row.status != STATUS_DRAFT:
            raise InvalidRequestStatusTransitionError(
                f"Cannot submit: request is in status '{row.status}'. "
                "Only draft requests may be submitted."
            )

        process_code = f"faculty_{row.request_type}"
        process_repo = ApprovalProcessRepository(self._session)
        process = process_repo.get_by_code(process_code)
        if process is None:
            raise UnknownRequestTypeError(
                f"No approval process configured for code '{process_code}'. "
                "Ensure the process is seeded before submitting."
            )

        faculty = self._faculty_repo.get(row.faculty_id)
        if faculty is None:
            raise FacultyRequestNotFoundError(f"Faculty {row.faculty_id} not found")

        ctx = ResolverContext(
            requestor_user_id=faculty.user_id,
            process_id=process.id,
            stage_index=1,
            payload=row.payload_json or {},
        )
        picked_opt_stage1 = picked_option_ids.get(1) if picked_option_ids else None

        status, candidates = resolve_stage_authority(
            session=self._session,
            process_id=process.id,
            stage_index=1,
            ctx=ctx,
            requestor_picked_option_id=picked_opt_stage1,
        )

        if status == "pending_pick":
            raise InvalidRequestStatusTransitionError(
                "Stage 1 requires a requestor pick but none was provided."
            )
        if status in ("approver_pool", "requestor_pick") and not candidates:
            raise EmptyApproverPoolError(
                f"No approvers found for stage 1 of process '{process_code}'. "
                "Ensure a HoD or AhoD is assigned to the faculty's department and campus."
            )

        pick_json: dict[str, str] | None = None
        if picked_option_ids:
            pick_json = {str(k): str(v) for k, v in picked_option_ids.items()}

        now = datetime.now(UTC)
        approval_req = ApprovalRequest(
            process_id=process.id,
            requestor_user_id=faculty.user_id,
            title=f"{process.title} — {faculty.first_name} {faculty.last_name}",
            payload_json=row.payload_json,
            state="submitted",
            current_stage=1,
            picked_option_ids_json=pick_json,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(approval_req)
        self._session.flush()
        self._session.refresh(approval_req)
        approval_req_id = approval_req.id

        return self._repo.update(
            request_id,
            {"approval_request_id": approval_req_id, "status": STATUS_SUBMITTED},
            actor_id,
        )

    def approve_request(
        self,
        request_id: UUID,
        actor_id: UUID,
        expected_stage_index: int | None = None,
    ) -> FacultyRequest:
        """Advance the linked ApprovalRequest by one stage as actor_id.

        Syncs FacultyRequest.status to STATUS_APPROVED when the approval chain
        reaches a terminal approved state.

        Raises:
        - FacultyRequestNotFoundError if request_id not found or not linked to an
          approval request
        - StageAlreadyAdvancedError if expected_stage_index is provided but doesn't
          match the current stage (concurrent approval guard)
        - UnauthorizedActorError if actor_id is not in the current-stage approver pool
        - ApprovalRequestError (re-raised from engine) for other engine failures
          (terminal state, process not found, etc.)

        TD-074: imports ApprovalRequestService from another service — intentional
        deviation documented in tech_debt.md.
        """
        from durgam.services.approval_request import (  # noqa: PLC0415
            ApprovalRequestError,
            ApprovalRequestService,
        )

        row = self._repo.get(request_id)
        if row is None:
            raise FacultyRequestNotFoundError(f"FacultyRequest {request_id} not found")
        if row.approval_request_id is None:
            raise FacultyRequestNotFoundError(
                f"FacultyRequest {request_id} is not linked to an approval request"
            )

        approval_req = self._session.get(ApprovalRequest, row.approval_request_id)
        if approval_req is None:
            raise FacultyRequestNotFoundError(
                f"ApprovalRequest {row.approval_request_id} not found"
            )

        if expected_stage_index is not None and approval_req.current_stage != expected_stage_index:
            raise StageAlreadyAdvancedError(
                f"Expected stage {expected_stage_index} but request is at stage "
                f"{approval_req.current_stage}. Another approver may have acted concurrently."
            )

        svc = ApprovalRequestService(self._session)
        try:
            updated = svc.approve(request_id=row.approval_request_id, approver_user_id=actor_id)
        except ApprovalRequestError as exc:
            if "not an approver" in str(exc):
                raise UnauthorizedActorError(
                    f"User {actor_id} is not in the approver pool for stage "
                    f"{approval_req.current_stage}."
                ) from exc
            raise

        if updated.state == "approved":
            return self._repo.update(request_id, {"status": STATUS_APPROVED}, actor_id)

        return row

    def reject_request(
        self,
        request_id: UUID,
        actor_id: UUID,
        reason: str,
        expected_stage_index: int | None = None,
    ) -> FacultyRequest:
        """Reject a submitted FacultyRequest at the current stage.

        Eligibility: actor must be in the current-stage approver pool (same as approve).
        For OR-set stages, any pool member can reject; first action wins.
        The `reason` parameter is passed as `comment` to the engine's reject method.

        Raises:
        - InvalidRejectReasonError if reason is empty, whitespace-only, or > 1000 chars
        - FacultyRequestNotFoundError if request_id not found or not linked
        - InvalidRequestStatusTransitionError if FacultyRequest is not SUBMITTED
        - StageAlreadyAdvancedError if expected_stage_index doesn't match
        - UnauthorizedActorError if actor_id is not in the current-stage pool
        - ApprovalRequestError (re-raised from engine) for other engine failures

        TD-074: imports ApprovalRequestService from another service — intentional.
        """
        if not reason or not reason.strip():
            raise InvalidRejectReasonError("Reject reason must be non-empty.")
        if len(reason) > 1000:
            raise InvalidRejectReasonError("Reject reason exceeds 1000 characters.")

        from durgam.services.approval_request import (  # noqa: PLC0415
            ApprovalRequestError,
            ApprovalRequestService,
        )

        row = self._repo.get(request_id)
        if row is None:
            raise FacultyRequestNotFoundError(f"FacultyRequest {request_id} not found")
        if row.status != STATUS_SUBMITTED:
            raise InvalidRequestStatusTransitionError(
                f"Cannot reject: status is '{row.status}'. Only submitted requests may be rejected."
            )
        if row.approval_request_id is None:
            raise FacultyRequestNotFoundError(
                f"FacultyRequest {request_id} is not linked to an approval request"
            )

        approval_req = self._session.get(ApprovalRequest, row.approval_request_id)
        if approval_req is None:
            raise FacultyRequestNotFoundError(
                f"ApprovalRequest {row.approval_request_id} not found"
            )

        if expected_stage_index is not None and approval_req.current_stage != expected_stage_index:
            raise StageAlreadyAdvancedError(
                f"Expected stage {expected_stage_index} but request is at stage "
                f"{approval_req.current_stage}."
            )

        svc = ApprovalRequestService(self._session)
        try:
            svc.reject(
                request_id=row.approval_request_id,
                approver_user_id=actor_id,
                comment=reason,
            )
        except ApprovalRequestError as exc:
            if "not an approver" in str(exc):
                raise UnauthorizedActorError(
                    f"User {actor_id} is not in the approver pool for stage "
                    f"{approval_req.current_stage}."
                ) from exc
            raise

        return self._repo.update(request_id, {"status": STATUS_REJECTED}, actor_id)

    def withdraw_request(
        self,
        request_id: UUID,
        actor_id: UUID,
    ) -> FacultyRequest:
        """Withdraw a submitted FacultyRequest. Only the originating faculty may withdraw.

        Delegates to the engine's withdraw() method which also marks the ApprovalRequest
        as 'withdrawn' and notifies approvers.

        Raises:
        - FacultyRequestNotFoundError if request_id not found or not linked
        - InvalidRequestStatusTransitionError if FacultyRequest is not SUBMITTED
        - UnauthorizedWithdrawError if actor_id != faculty.user_id

        TD-074: imports ApprovalRequestService from another service — intentional.
        """
        from durgam.services.approval_request import (  # noqa: PLC0415
            ApprovalRequestError,
            ApprovalRequestService,
        )

        row = self._repo.get(request_id)
        if row is None:
            raise FacultyRequestNotFoundError(f"FacultyRequest {request_id} not found")
        if row.status != STATUS_SUBMITTED:
            raise InvalidRequestStatusTransitionError(
                f"Cannot withdraw: status is '{row.status}'. Only submitted requests may be withdrawn."
            )
        if row.approval_request_id is None:
            raise FacultyRequestNotFoundError(
                f"FacultyRequest {request_id} is not linked to an approval request"
            )

        faculty = self._faculty_repo.get(row.faculty_id)
        if faculty is None:
            raise FacultyRequestNotFoundError(f"Faculty {row.faculty_id} not found")
        if faculty.user_id != actor_id:
            raise UnauthorizedWithdrawError(
                f"User {actor_id} cannot withdraw FacultyRequest {request_id}: "
                f"only the originating faculty ({faculty.user_id}) may withdraw."
            )

        svc = ApprovalRequestService(self._session)
        svc.withdraw(
            request_id=row.approval_request_id,
            requestor_user_id=faculty.user_id,
        )

        return self._repo.update(request_id, {"status": STATUS_WITHDRAWN}, actor_id)

    # ── Attachment methods (Phase 6) ──────────────────────────────────────────

    def add_attachment(
        self,
        request_id: UUID,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
        actor_id: UUID,
    ) -> FileAsset:
        """Attach a file to a FacultyRequest. Validates MIME, size, and count limits
        against the linked ApprovalProcess configuration (DB-driven; no hardcoded values).

        Only allowed when FacultyRequest.status == DRAFT.
        Only the originating faculty (faculty.user_id == actor_id) may attach.

        Raises:
        - FacultyRequestNotFoundError if request_id not found
        - InvalidRequestStatusTransitionError if status != DRAFT
        - UnauthorizedAttachmentError if actor_id != faculty.user_id
        - AttachmentNotConfiguredError if process.allowed_attachment_mime_types_json is None
        - DisallowedMimeTypeError if mime_type not in allowed list
        - AttachmentTooLargeError if size > max_attachment_mb * 1024 * 1024
        - AttachmentLimitExceededError if existing count >= max_upward_attachments
        """
        row = self._repo.get(request_id)
        if row is None:
            raise FacultyRequestNotFoundError(f"FacultyRequest {request_id} not found")
        if row.status != STATUS_DRAFT:
            raise InvalidRequestStatusTransitionError(
                f"Cannot attach file: status is '{row.status}'. "
                "Attachments are only allowed on draft requests."
            )

        faculty = self._faculty_repo.get(row.faculty_id)
        if faculty is None:
            raise FacultyRequestNotFoundError(f"Faculty {row.faculty_id} not found")
        if faculty.user_id != actor_id:
            raise UnauthorizedAttachmentError(
                f"User {actor_id} cannot manage attachments for FacultyRequest {request_id}."
            )

        process_code = f"faculty_{row.request_type}"
        process_repo = ApprovalProcessRepository(self._session)
        process = process_repo.get_by_code(process_code)
        if process is None or process.allowed_attachment_mime_types_json is None:
            raise AttachmentNotConfiguredError(
                f"Process '{process_code}' does not allow attachments."
            )

        allowed_mimes: list[str] = process.allowed_attachment_mime_types_json
        if mime_type not in allowed_mimes:
            raise DisallowedMimeTypeError(
                f"MIME type '{mime_type}' is not allowed for process '{process_code}'. "
                f"Allowed: {', '.join(sorted(allowed_mimes))}"
            )

        max_bytes = process.max_attachment_mb * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise AttachmentTooLargeError(
                f"File exceeds the {process.max_attachment_mb} MB size limit "
                f"({len(file_bytes)} bytes > {max_bytes} bytes)."
            )

        file_repo = FileAssetRepository(self._session)
        existing = file_repo.list_by_faculty_request_id(request_id)
        if len(existing) >= process.max_upward_attachments:
            raise AttachmentLimitExceededError(
                f"Request already has {len(existing)} attachment(s); "
                f"maximum is {process.max_upward_attachments}."
            )

        backend = self._storage_backend
        if backend is None:
            from durgam.storage import get_storage_backend  # noqa: PLC0415
            backend = get_storage_backend()

        sha256 = hashlib.sha256(file_bytes).hexdigest()
        storage_key = uuid4().hex
        backend.put(storage_key, file_bytes, mime_type)

        now = datetime.now(UTC)
        asset = FileAsset(
            storage_key=storage_key,
            original_name=filename,
            mime_type=mime_type,
            size_bytes=len(file_bytes),
            sha256=sha256,
            owner_user_id=actor_id,
            purpose="faculty_request_attachment",
            metadata_json={"faculty_request_id": str(request_id)},
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        return file_repo.save(asset)

    def list_attachments(self, request_id: UUID) -> list[FileAsset]:
        """List non-deleted attachments for a FacultyRequest. No status restriction."""
        file_repo = FileAssetRepository(self._session)
        return file_repo.list_by_faculty_request_id(request_id)

    def remove_attachment(
        self,
        attachment_id: UUID,
        actor_id: UUID,
    ) -> None:
        """Soft-delete a FacultyRequest attachment. MinIO object is retained for audit.

        Only allowed when FacultyRequest.status == DRAFT.
        Only the originating faculty may remove attachments.

        Raises:
        - AttachmentNotFoundError if attachment_id not found or not a faculty_request_attachment
        - FacultyRequestNotFoundError if linked FacultyRequest absent
        - InvalidRequestStatusTransitionError if status != DRAFT
        - UnauthorizedAttachmentError if actor_id != faculty.user_id
        """
        file_repo = FileAssetRepository(self._session)
        asset = file_repo.get_by_id(attachment_id)
        if asset is None or asset.purpose != "faculty_request_attachment":
            raise AttachmentNotFoundError(
                f"Attachment {attachment_id} not found."
            )

        fr_id_str = (asset.metadata_json or {}).get("faculty_request_id")
        if fr_id_str is None:
            raise AttachmentNotFoundError(
                f"Attachment {attachment_id} has no linked FacultyRequest."
            )

        row = self._repo.get(UUID(fr_id_str))
        if row is None:
            raise FacultyRequestNotFoundError(
                f"FacultyRequest {fr_id_str} not found."
            )
        if row.status != STATUS_DRAFT:
            raise InvalidRequestStatusTransitionError(
                f"Cannot remove attachment: FacultyRequest status is '{row.status}'. "
                "Attachments can only be removed from draft requests."
            )

        faculty = self._faculty_repo.get(row.faculty_id)
        if faculty is None:
            raise FacultyRequestNotFoundError(f"Faculty {row.faculty_id} not found")
        if faculty.user_id != actor_id:
            raise UnauthorizedAttachmentError(
                f"User {actor_id} cannot remove attachments from FacultyRequest {row.id}."
            )

        file_repo.soft_delete(asset, actor_id)
