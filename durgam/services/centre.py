"""CentreService — CRUD and hard-delete guard for CentreOfExcellence (§8.2)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.centre import CentreOfExcellence
from durgam.repositories.centre import CentreRepository
from durgam.services.org_exceptions import HardDeleteBlockedError, OrgServiceError

log = structlog.get_logger(__name__)


class CentreError(OrgServiceError):
    pass


class CentreService:
    def __init__(self, centre_repo: CentreRepository) -> None:
        self._centres = centre_repo

    def list(self) -> list[CentreOfExcellence]:
        return self._centres.list_active()

    def list_by_campus(self, campus_id: UUID) -> list[CentreOfExcellence]:
        return self._centres.list_by_campus(campus_id)

    def get(self, centre_id: UUID) -> CentreOfExcellence:
        centre = self._centres.get_by_id(centre_id)
        if centre is None:
            raise CentreError("Centre of Excellence not found.")
        return centre

    def create(
        self,
        code: str,
        name: str,
        campus_id: UUID,
        actor_id: UUID,
    ) -> CentreOfExcellence:
        code = code.strip().upper()
        name = name.strip()
        if not code:
            raise CentreError("Centre code is required.")
        if not name:
            raise CentreError("Centre name is required.")
        if self._centres.get_by_code(code) is not None:
            raise CentreError(f"Centre code '{code}' is already in use.")
        now = datetime.now(UTC)
        centre = CentreOfExcellence(
            code=code,
            name=name,
            campus_id=campus_id,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        centre = self._centres.save(centre)
        log.info("centre_created", centre_id=str(centre.id), actor=str(actor_id))
        return centre

    def update(self, centre_id: UUID, fields: dict, actor_id: UUID) -> CentreOfExcellence:
        centre = self.get(centre_id)
        for key, value in fields.items():
            setattr(centre, key, value)
        centre.updated_by = actor_id
        return self._centres.save(centre)

    def soft_delete(self, centre_id: UUID, actor_id: UUID) -> CentreOfExcellence:
        centre = self.get(centre_id)
        return self._centres.soft_delete(centre, actor_id)

    def hard_delete(self, centre_id: UUID, actor_id: UUID) -> None:
        """CentreOfExcellence has no dependent entities at M3 — only audit check."""
        centre = self._centres._session.get(CentreOfExcellence, centre_id)
        if centre is None:
            raise CentreError("Centre of Excellence not found.")
        if not centre.is_deleted:
            raise CentreError("Centre must be deactivated before permanent deletion.")

        from durgam.models.crosscutting import AuditLog
        from sqlmodel import func, select

        n_audit: int = self._centres._session.exec(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.resource == "centre",
                AuditLog.resource_id == str(centre_id),
            )
        ).one()
        if n_audit > 0:
            raise HardDeleteBlockedError(
                f"Centre has {n_audit} audit record(s) and cannot be permanently deleted."
            )

        self._centres.hard_delete(centre)
        log.info("centre_hard_deleted", centre_id=str(centre_id), actor=str(actor_id))
