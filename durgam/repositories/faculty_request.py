"""FacultyRequestRepository — CRUD for faculty_requests table (M10 Phase 5A)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import Session, select

from durgam.models.faculty_request import FacultyRequest, STATUS_DRAFT


class FacultyRequestRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, request_id: UUID) -> FacultyRequest | None:
        row = self._session.get(FacultyRequest, request_id)
        if row is None or row.is_deleted:
            return None
        return row

    def list_by_status(self, status: str) -> list[FacultyRequest]:
        """All non-deleted FacultyRequests with the given status, oldest-updated first."""
        stmt = (
            select(FacultyRequest)
            .where(FacultyRequest.status == status, FacultyRequest.is_deleted == False)  # noqa: E712
            .order_by(FacultyRequest.updated_at.asc())
        )
        return list(self._session.exec(stmt).all())

    def list_by_faculty(
        self,
        faculty_id: UUID,
        *,
        status: str | None = None,
    ) -> list[FacultyRequest]:
        stmt = select(FacultyRequest).where(
            FacultyRequest.faculty_id == faculty_id,
            FacultyRequest.is_deleted == False,  # noqa: E712
        )
        if status is not None:
            stmt = stmt.where(FacultyRequest.status == status)
        stmt = stmt.order_by(FacultyRequest.created_at.desc())
        return list(self._session.exec(stmt).all())

    def list_by_type(
        self,
        request_type: str,
        *,
        status: str | None = None,
    ) -> list[FacultyRequest]:
        stmt = select(FacultyRequest).where(
            FacultyRequest.request_type == request_type,
            FacultyRequest.is_deleted == False,  # noqa: E712
        )
        if status is not None:
            stmt = stmt.where(FacultyRequest.status == status)
        stmt = stmt.order_by(FacultyRequest.created_at.desc())
        return list(self._session.exec(stmt).all())

    def create(
        self,
        *,
        faculty_id: UUID,
        request_type: str,
        payload: dict | None,
        actor_id: UUID,
    ) -> FacultyRequest:
        now = datetime.now(UTC)
        row = FacultyRequest(
            faculty_id=faculty_id,
            request_type=request_type,
            payload_json=payload,
            status=STATUS_DRAFT,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row

    def update(
        self,
        request_id: UUID,
        fields: dict,
        actor_id: UUID,
    ) -> FacultyRequest:
        row = self._session.get(FacultyRequest, request_id)
        if row is None or row.is_deleted:
            raise ValueError(f"FacultyRequest {request_id} not found")
        for k, v in fields.items():
            setattr(row, k, v)
        row.updated_by = actor_id
        row.updated_at = datetime.now(UTC)
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row

    def soft_delete(self, request_id: UUID, actor_id: UUID) -> None:
        row = self._session.get(FacultyRequest, request_id)
        if row is None or row.is_deleted:
            raise ValueError(f"FacultyRequest {request_id} not found")
        now = datetime.now(UTC)
        row.is_deleted = True
        row.deleted_at = now
        row.deleted_by = actor_id
        row.updated_at = now
        row.updated_by = actor_id
        self._session.add(row)
        self._session.flush()
