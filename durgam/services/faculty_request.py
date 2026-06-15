"""FacultyRequestService — business rules for faculty-initiated requests (M10 Phase 5A).

Layering: service owns validation rules; repositories own all SQL.
No session.commit() here — callers (page states) must commit.
No audit emissions in Phase 5A — wired at state-handler boundary in Phase 7+.
"""

from __future__ import annotations

from uuid import UUID

from sqlmodel import Session

from durgam.models.faculty_request import (
    FACULTY_REQUEST_TYPES,
    STATUS_DRAFT,
    FacultyRequest,
)
from durgam.repositories.faculty import FacultyRepository
from durgam.repositories.faculty_request import FacultyRequestRepository


class UnknownRequestTypeError(ValueError):
    """request_type is not in FACULTY_REQUEST_TYPES."""


class InvalidRequestStatusTransitionError(ValueError):
    """Operation not allowed in current status (e.g., update_payload on submitted request)."""


class FacultyRequestNotFoundError(ValueError):
    """FacultyRequest row not found or is soft-deleted."""


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
