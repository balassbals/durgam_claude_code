"""Repository for ApprovalStageOption — M10 Phase 3A OR-set schema."""

from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime, UTC

from sqlmodel import Session, select

from durgam.models.crosscutting import ApprovalStageOption


class ApprovalStageOptionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _active(self):
        return select(ApprovalStageOption).where(
            ApprovalStageOption.is_deleted == False  # noqa: E712
        )

    def get(self, option_id: UUID) -> ApprovalStageOption | None:
        stmt = self._active().where(ApprovalStageOption.id == option_id)
        return self._session.exec(stmt).first()

    def list_by_process_stage(
        self, process_id: UUID, stage_index: int
    ) -> list[ApprovalStageOption]:
        stmt = (
            self._active()
            .where(ApprovalStageOption.approval_process_id == process_id)
            .where(ApprovalStageOption.stage_index == stage_index)
            .order_by(ApprovalStageOption.sort_order)
        )
        return list(self._session.exec(stmt).all())

    def create(
        self,
        *,
        approval_process_id: UUID,
        stage_index: int,
        resolver_name: str,
        label: str,
        sort_order: int = 0,
        actor_id: UUID | None = None,
    ) -> ApprovalStageOption:
        now = datetime.now(UTC)
        option = ApprovalStageOption(
            id=uuid4(),
            approval_process_id=approval_process_id,
            stage_index=stage_index,
            resolver_name=resolver_name,
            label=label,
            sort_order=sort_order,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(option)
        self._session.flush()
        self._session.refresh(option)
        return option

    def update(
        self,
        option_id: UUID,
        *,
        label: str | None = None,
        sort_order: int | None = None,
        actor_id: UUID | None = None,
    ) -> ApprovalStageOption:
        option = self.get(option_id)
        if option is None:
            raise ValueError(f"ApprovalStageOption {option_id} not found")
        if label is not None:
            option.label = label
        if sort_order is not None:
            option.sort_order = sort_order
        option.updated_at = datetime.now(UTC)
        option.updated_by = actor_id
        self._session.add(option)
        self._session.flush()
        self._session.refresh(option)
        return option

    def soft_delete(self, option_id: UUID, *, actor_id: UUID | None = None) -> None:
        option = self.get(option_id)
        if option is None:
            raise ValueError(f"ApprovalStageOption {option_id} not found")
        now = datetime.now(UTC)
        option.is_deleted = True
        option.deleted_at = now
        option.deleted_by = actor_id
        self._session.add(option)
        self._session.flush()
