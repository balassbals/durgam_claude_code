"""CampusService — CRUD and hard-delete guard for the Campus entity (§8.2)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.campus import Campus
from durgam.repositories.campus import CampusRepository
from durgam.services.org_exceptions import HardDeleteBlockedError, OrgServiceError

log = structlog.get_logger(__name__)


class CampusError(OrgServiceError):
    """Domain errors specific to the Campus service."""


class CampusService:
    def __init__(self, campus_repo: CampusRepository) -> None:
        self._campuses = campus_repo

    def list(self) -> list[Campus]:
        return self._campuses.list_active()

    def get(self, campus_id: UUID) -> Campus:
        campus = self._campuses.get_by_id(campus_id)
        if campus is None:
            raise CampusError("Campus not found.")
        return campus

    def create(
        self,
        code: str,
        name: str,
        actor_id: UUID,
        *,
        address: str | None = None,
    ) -> Campus:
        code = code.strip().upper()
        name = name.strip()
        if not code:
            raise CampusError("Campus code is required.")
        if not name:
            raise CampusError("Campus name is required.")
        if self._campuses.get_by_code(code) is not None:
            raise CampusError(f"Campus code '{code}' is already in use.")
        now = datetime.now(UTC)
        campus = Campus(
            code=code,
            name=name,
            address=address or None,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        campus = self._campuses.save(campus)
        log.info("campus_created", campus_id=str(campus.id), actor=str(actor_id))
        return campus

    def update(self, campus_id: UUID, fields: dict, actor_id: UUID) -> Campus:
        """Update mutable fields (name, address). Code is immutable."""
        campus = self.get(campus_id)
        for key, value in fields.items():
            setattr(campus, key, value)
        campus.updated_by = actor_id
        campus = self._campuses.save(campus)
        log.info("campus_updated", campus_id=str(campus_id), actor=str(actor_id))
        return campus

    def soft_delete(self, campus_id: UUID, actor_id: UUID) -> Campus:
        campus = self.get(campus_id)
        campus = self._campuses.soft_delete(campus, actor_id)
        log.info("campus_soft_deleted", campus_id=str(campus_id), actor=str(actor_id))
        return campus

    def hard_delete(self, campus_id: UUID, actor_id: UUID) -> None:
        """Permanently delete a campus.

        Requires the campus to be soft-deleted first. Blocked if any department
        references this campus (main or via join) or if audit history exists.
        """
        campus = self._campuses._session.get(Campus, campus_id)
        if campus is None:
            raise CampusError("Campus not found.")
        if not campus.is_deleted:
            raise CampusError("Campus must be deactivated before permanent deletion.")

        n_deps = self._campuses.count_departments(campus_id)
        if n_deps > 0:
            raise HardDeleteBlockedError(
                f"Campus has {n_deps} department reference(s) and cannot be permanently deleted."
            )

        from durgam.models.crosscutting import AuditLog
        from sqlmodel import func, select

        n_audit: int = self._campuses._session.exec(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.resource == "campus",
                AuditLog.resource_id == str(campus_id),
            )
        ).one()
        if n_audit > 0:
            raise HardDeleteBlockedError(
                f"Campus has {n_audit} audit record(s) and cannot be permanently deleted."
            )

        self._campuses.hard_delete(campus)
        log.info("campus_hard_deleted", campus_id=str(campus_id), actor=str(actor_id))
