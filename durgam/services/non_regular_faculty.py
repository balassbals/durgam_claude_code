"""NonRegularFacultyService — CRUD + admin approval for non-regular faculty (§9.10, E-003)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

import structlog

from durgam.models.config_anchors import NonRegularFaculty
from durgam.repositories.non_regular_faculty import NonRegularFacultyRepository
from durgam.services.org_exceptions import OrgServiceError

log = structlog.get_logger(__name__)


class NonRegularFacultyError(OrgServiceError):
    pass


class NonRegularFacultyService:
    def __init__(self, repo: NonRegularFacultyRepository) -> None:
        self._repo = repo

    def list_by_department(self, department_id: UUID) -> list[NonRegularFaculty]:
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
        non_regular_type: str = "visiting",
    ) -> NonRegularFaculty:
        name = name.strip()
        designation = designation.strip()
        organization = organization.strip()
        expertise = expertise.strip()
        if not name:
            raise NonRegularFacultyError("Name is required.")
        if not designation:
            raise NonRegularFacultyError("Designation is required.")
        if not organization:
            raise NonRegularFacultyError("Organization is required.")
        if not expertise:
            raise NonRegularFacultyError("Expertise is required.")
        if available_to < available_from:
            raise NonRegularFacultyError(
                "Available-to date must be on or after available-from date."
            )
        valid_types = {"visiting", "adjunct", "guest", "contract", "honorary"}
        if non_regular_type not in valid_types:
            raise NonRegularFacultyError(
                f"Invalid type '{non_regular_type}'. Must be one of: {', '.join(sorted(valid_types))}."
            )

        now = datetime.now(UTC)
        record = NonRegularFaculty(
            department_id=department_id,
            name=name,
            designation=designation,
            organization=organization,
            expertise=expertise,
            available_from=available_from,
            available_to=available_to,
            is_admin_approved=False,
            non_regular_type=non_regular_type,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        record = self._repo.save(record)
        log.info("non_regular_faculty_created", id=str(record.id), actor=str(actor_id))
        return record

    def update(
        self, record_id: UUID, fields: dict, actor_id: UUID,
    ) -> NonRegularFaculty:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise NonRegularFacultyError("Non-regular faculty record not found.")
        for key, value in fields.items():
            setattr(record, key, value)
        record.updated_by = actor_id
        record = self._repo.save(record)
        log.info("non_regular_faculty_updated", id=str(record_id), actor=str(actor_id))
        return record

    def soft_delete(self, record_id: UUID, actor_id: UUID) -> NonRegularFaculty:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise NonRegularFacultyError("Non-regular faculty record not found.")
        record = self._repo.soft_delete(record, actor_id)
        log.info("non_regular_faculty_deleted", id=str(record_id), actor=str(actor_id))
        return record

    def set_approval(
        self, record_id: UUID, approved: bool, actor_id: UUID,
    ) -> NonRegularFaculty:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise NonRegularFacultyError("Non-regular faculty record not found.")
        record.is_admin_approved = approved
        record.updated_by = actor_id
        record = self._repo.save(record)
        log.info(
            "non_regular_faculty_approval_changed",
            id=str(record_id),
            approved=approved,
            actor=str(actor_id),
        )
        return record
