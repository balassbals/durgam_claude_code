"""SchoolService — CRUD and hard-delete guard for the School entity (§8.2)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.school import School
from durgam.repositories.school import SchoolRepository
from durgam.services.org_exceptions import HardDeleteBlockedError, OrgServiceError

log = structlog.get_logger(__name__)


class SchoolError(OrgServiceError):
    pass


class SchoolService:
    def __init__(self, school_repo: SchoolRepository) -> None:
        self._schools = school_repo

    def list(self) -> list[School]:
        return self._schools.list_active()

    def get(self, school_id: UUID) -> School:
        school = self._schools.get_by_id(school_id)
        if school is None:
            raise SchoolError("School not found.")
        return school

    def create(
        self,
        code: str,
        name: str,
        dean_role_code: str,
        actor_id: UUID,
    ) -> School:
        code = code.strip().upper()
        name = name.strip()
        dean_role_code = dean_role_code.strip().upper()
        if not code:
            raise SchoolError("School code is required.")
        if not name:
            raise SchoolError("School name is required.")
        if not dean_role_code:
            raise SchoolError("Dean role code is required.")
        if self._schools.get_by_code(code) is not None:
            raise SchoolError(f"School code '{code}' is already in use.")
        now = datetime.now(UTC)
        school = School(
            code=code,
            name=name,
            dean_role_code=dean_role_code,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        school = self._schools.save(school)
        log.info("school_created", school_id=str(school.id), actor=str(actor_id))
        return school

    def update(self, school_id: UUID, fields: dict, actor_id: UUID) -> School:
        school = self.get(school_id)
        for key, value in fields.items():
            setattr(school, key, value)
        school.updated_by = actor_id
        school = self._schools.save(school)
        log.info("school_updated", school_id=str(school_id), actor=str(actor_id))
        return school

    def soft_delete(self, school_id: UUID, actor_id: UUID) -> School:
        school = self.get(school_id)
        return self._schools.soft_delete(school, actor_id)

    def hard_delete(self, school_id: UUID, actor_id: UUID) -> None:
        school = self._schools._session.get(School, school_id)
        if school is None:
            raise SchoolError("School not found.")
        if not school.is_deleted:
            raise SchoolError("School must be deactivated before permanent deletion.")

        n_deps = self._schools.count_departments(school_id)
        if n_deps > 0:
            raise HardDeleteBlockedError(
                f"School has {n_deps} department(s) and cannot be permanently deleted."
            )

        from durgam.models.crosscutting import AuditLog
        from sqlmodel import func, select

        n_audit: int = self._schools._session.exec(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.resource == "school",
                AuditLog.resource_id == str(school_id),
            )
        ).one()
        if n_audit > 0:
            raise HardDeleteBlockedError(
                f"School has {n_audit} audit record(s) and cannot be permanently deleted."
            )

        self._schools.hard_delete(school)
        log.info("school_hard_deleted", school_id=str(school_id), actor=str(actor_id))
