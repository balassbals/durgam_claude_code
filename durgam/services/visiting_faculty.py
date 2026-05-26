"""VisitingFacultyService — CRUD + admin approval for visiting faculty (§9.10)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

import structlog

from durgam.models.config_anchors import VisitingFaculty
from durgam.repositories.visiting_faculty import VisitingFacultyRepository
from durgam.services.org_exceptions import OrgServiceError

log = structlog.get_logger(__name__)


class VisitingFacultyError(OrgServiceError):
    pass


class VisitingFacultyService:
    def __init__(self, repo: VisitingFacultyRepository) -> None:
        self._repo = repo

    def list_by_department(self, department_id: UUID) -> list[VisitingFaculty]:
        return self._repo.list_by_department(department_id)

    def create(
        self,
        *,
        department_id: UUID,
        name: str,
        designation: str,
        organization: str,
        expertise: str,
        available_from: date,
        available_to: date,
        actor_id: UUID,
    ) -> VisitingFaculty:
        name = name.strip()
        designation = designation.strip()
        organization = organization.strip()
        expertise = expertise.strip()
        if not name:
            raise VisitingFacultyError("Name is required.")
        if not designation:
            raise VisitingFacultyError("Designation is required.")
        if not organization:
            raise VisitingFacultyError("Organization is required.")
        if not expertise:
            raise VisitingFacultyError("Expertise is required.")
        if available_to < available_from:
            raise VisitingFacultyError(
                "Available-to date must be on or after available-from date."
            )

        now = datetime.now(UTC)
        record = VisitingFaculty(
            department_id=department_id,
            name=name,
            designation=designation,
            organization=organization,
            expertise=expertise,
            available_from=available_from,
            available_to=available_to,
            is_admin_approved=False,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        record = self._repo.save(record)
        log.info("visiting_faculty_created", id=str(record.id), actor=str(actor_id))
        return record

    def update(
        self, record_id: UUID, fields: dict, actor_id: UUID,
    ) -> VisitingFaculty:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise VisitingFacultyError("Visiting faculty record not found.")
        for key, value in fields.items():
            setattr(record, key, value)
        record.updated_by = actor_id
        record = self._repo.save(record)
        log.info("visiting_faculty_updated", id=str(record_id), actor=str(actor_id))
        return record

    def soft_delete(self, record_id: UUID, actor_id: UUID) -> VisitingFaculty:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise VisitingFacultyError("Visiting faculty record not found.")
        record = self._repo.soft_delete(record, actor_id)
        log.info("visiting_faculty_deleted", id=str(record_id), actor=str(actor_id))
        return record

    def set_approval(
        self, record_id: UUID, approved: bool, actor_id: UUID,
    ) -> VisitingFaculty:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise VisitingFacultyError("Visiting faculty record not found.")
        record.is_admin_approved = approved
        record.updated_by = actor_id
        record = self._repo.save(record)
        log.info(
            "visiting_faculty_approval_changed",
            id=str(record_id),
            approved=approved,
            actor=str(actor_id),
        )
        return record
