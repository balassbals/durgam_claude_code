"""ApprovalStepRepository — queries for the ApprovalStep model."""

from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from durgam.models.crosscutting import ApprovalStep


class ApprovalStepRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_request(self, request_id: UUID) -> list[ApprovalStep]:
        stmt = (
            select(ApprovalStep)
            .where(ApprovalStep.request_id == request_id)
            .order_by(ApprovalStep.decided_at.asc())  # type: ignore[union-attr]
        )
        return list(self._session.exec(stmt).all())

    def create(self, step: ApprovalStep) -> ApprovalStep:
        self._session.add(step)
        self._session.flush()
        return step
