"""DesignationService — CRUD for the extensible faculty designation vocabulary."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.config_anchors import Designation
from durgam.repositories.designation import DesignationRepository
from durgam.services.org_exceptions import OrgServiceError

log = structlog.get_logger(__name__)


class DesignationError(OrgServiceError):
    pass


class DesignationService:
    def __init__(self, repo: DesignationRepository) -> None:
        self._repo = repo

    def list_all(self) -> list[Designation]:
        return self._repo.list_all_active()

    def create(
        self,
        *,
        code: str,
        name: str,
        rank: int,
        actor_id: UUID,
        notes: str | None = None,
    ) -> Designation:
        code = code.strip()
        name = name.strip()
        if not code:
            raise DesignationError("Designation code is required.")
        if not name:
            raise DesignationError("Designation name is required.")
        if rank < 1:
            raise DesignationError("Rank must be 1 or greater.")

        now = datetime.now(UTC)
        record = Designation(
            code=code,
            name=name,
            rank=rank,
            notes=notes,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        record = self._repo.save(record)
        log.info("designation_created", id=str(record.id), actor=str(actor_id))
        return record

    def update(
        self, record_id: UUID, fields: dict, actor_id: UUID,
    ) -> Designation:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise DesignationError("Designation not found.")
        for key, value in fields.items():
            setattr(record, key, value)
        record.updated_by = actor_id
        record = self._repo.save(record)
        log.info("designation_updated", id=str(record_id), actor=str(actor_id))
        return record

    def soft_delete(self, record_id: UUID, actor_id: UUID) -> Designation:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise DesignationError("Designation not found.")
        record = self._repo.soft_delete(record, actor_id)
        log.info("designation_deleted", id=str(record_id), actor=str(actor_id))
        return record
