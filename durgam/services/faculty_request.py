"""FacultyRequestService — business rules for faculty-initiated requests (M10).

Layering: service owns validation rules; repositories own all SQL.
No session.commit() here — callers (page states) must commit.
No audit emissions in Phase 5A/5B — wired at state-handler boundary in Phase 7+.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import Session

from durgam.models.crosscutting import ApprovalRequest
from durgam.models.faculty_request import (
    FACULTY_REQUEST_TYPES,
    STATUS_DRAFT,
    STATUS_SUBMITTED,
    FacultyRequest,
)
from durgam.repositories.approval_process import ApprovalProcessRepository
from durgam.repositories.faculty import FacultyRepository
from durgam.repositories.faculty_request import FacultyRequestRepository
from durgam.services.approval_engine import (
    StageOptionMismatchError,
    resolve_stage_authority,
)
from durgam.services.approval_resolvers import ResolverContext


class UnknownRequestTypeError(ValueError):
    """request_type is not in FACULTY_REQUEST_TYPES, or no approval process is configured."""


class InvalidRequestStatusTransitionError(ValueError):
    """Operation not allowed in current status (e.g., update_payload on submitted request)."""


class FacultyRequestNotFoundError(ValueError):
    """FacultyRequest row not found or is soft-deleted."""


class EmptyApproverPoolError(ValueError):
    """Stage 1 resolver returned no approvers for this faculty's dept+campus."""


class FacultyRequestService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = FacultyRequestRepository(session)
        self._faculty_repo = FacultyRepository(session)

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
