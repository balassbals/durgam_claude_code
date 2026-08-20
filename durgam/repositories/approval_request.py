"""ApprovalRequestRepository — queries for the ApprovalRequest model."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import Session, select

from durgam.models.crosscutting import ApprovalAction, ApprovalRequest
from durgam.repositories.base import BaseRepository


class ApprovalRequestRepository(BaseRepository[ApprovalRequest]):
    def __init__(self, session: Session) -> None:
        super().__init__(ApprovalRequest, session)

    def get_by_id_any(self, record_id: UUID) -> ApprovalRequest | None:
        """Return a row by PK regardless of soft-delete status."""
        return self._session.get(ApprovalRequest, record_id)

    def list_for_requestor(
        self,
        user_id: UUID,
        state_filter: str | None = None,
    ) -> list[ApprovalRequest]:
        stmt = (
            select(ApprovalRequest)
            .where(
                ApprovalRequest.requestor_user_id == user_id,
                ApprovalRequest.is_deleted == False,  # noqa: E712
            )
        )
        if state_filter is not None:
            stmt = stmt.where(ApprovalRequest.state == state_filter)
        stmt = stmt.order_by(ApprovalRequest.created_at.desc())  # type: ignore[union-attr]
        return list(self._session.exec(stmt).all())

    def list_by_states(self, states: list[str]) -> list[ApprovalRequest]:
        stmt = (
            select(ApprovalRequest)
            .where(
                ApprovalRequest.state.in_(states),  # type: ignore[union-attr]
                ApprovalRequest.is_deleted == False,  # noqa: E712
            )
            .order_by(ApprovalRequest.created_at.desc())  # type: ignore[union-attr]
        )
        return list(self._session.exec(stmt).all())

    def list_where_actor_acted(self, actor_user_id: UUID) -> list[ApprovalRequest]:
        """ApprovalRequests where the user has any approval_action row.

        No state filter — includes in-flight requests (submitted, in_review) AND
        terminal ones (approved, rejected, withdrawn, cancelled). Used by the approver
        inbox 'Past Actions' view to surface requests the viewer has acted on even if
        the workflow is still progressing at a later stage.
        """
        stmt = (
            select(ApprovalRequest)
            .join(ApprovalAction, ApprovalAction.approval_request_id == ApprovalRequest.id)
            .where(
                ApprovalAction.actor_user_id == actor_user_id,
                ApprovalAction.is_deleted == False,  # noqa: E712
                ApprovalRequest.is_deleted == False,  # noqa: E712
                # NO state filter — show all states where actor has acted
            )
            .distinct()
            .order_by(ApprovalRequest.updated_at.desc())  # type: ignore[union-attr]
        )
        return list(self._session.exec(stmt).all())

    def update_state(
        self,
        request: ApprovalRequest,
        new_state: str,
        decided_at: datetime | None = None,
    ) -> ApprovalRequest:
        request.state = new_state
        if decided_at is not None:
            request.decided_at = decided_at
        request.updated_at = datetime.now(UTC)
        self._session.add(request)
        self._session.flush()
        return request

    def advance_stage(self, request: ApprovalRequest) -> ApprovalRequest:
        request.current_stage += 1
        request.updated_at = datetime.now(UTC)
        self._session.add(request)
        self._session.flush()
        return request
