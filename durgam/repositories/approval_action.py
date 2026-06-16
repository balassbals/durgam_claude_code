"""ApprovalActionRepository — queries for the ApprovalAction model (M10 Phase 7A)."""

from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from durgam.models.crosscutting import ApprovalAction


class ApprovalActionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, action: ApprovalAction) -> ApprovalAction:
        self._session.add(action)
        self._session.flush()
        return action

    def list_by_request_id(self, approval_request_id: UUID) -> list[ApprovalAction]:
        """Return all non-deleted ApprovalAction rows for a request, oldest first."""
        stmt = (
            select(ApprovalAction)
            .where(
                ApprovalAction.approval_request_id == approval_request_id,
                ApprovalAction.is_deleted == False,  # noqa: E712
            )
            .order_by(ApprovalAction.created_at.asc())  # type: ignore[union-attr]
        )
        return list(self._session.exec(stmt).all())
