"""NonOwnedCourseService — CRUD for departmentless courses (§9.3, line 151)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.config_anchors import NonOwnedCourse
from durgam.repositories.non_owned_course import NonOwnedCourseRepository
from durgam.services.org_exceptions import OrgServiceError

log = structlog.get_logger(__name__)


class NonOwnedCourseError(OrgServiceError):
    pass


class NonOwnedCourseService:
    def __init__(self, repo: NonOwnedCourseRepository) -> None:
        self._repo = repo

    def list_by_ay(self, academic_year_id: UUID) -> list[NonOwnedCourse]:
        return self._repo.list_by_ay(academic_year_id)

    def create(
        self,
        *,
        academic_year_id: UUID,
        course_code: str,
        course_name: str,
        credits: int,
        semester: str,
        faculty_id: UUID,
        actor_id: UUID,
        notes: str | None = None,
    ) -> NonOwnedCourse:
        course_code = course_code.strip()
        course_name = course_name.strip()
        if not course_code:
            raise NonOwnedCourseError("Course code is required.")
        if not course_name:
            raise NonOwnedCourseError("Course name is required.")
        if semester not in ("odd", "even"):
            raise NonOwnedCourseError("Semester must be 'odd' or 'even'.")

        now = datetime.now(UTC)
        record = NonOwnedCourse(
            academic_year_id=academic_year_id,
            course_code=course_code,
            course_name=course_name,
            credits=credits,
            semester=semester,
            faculty_id=faculty_id,
            notes=notes,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        record = self._repo.save(record)
        log.info("non_owned_course_created", id=str(record.id), actor=str(actor_id))
        return record

    def update(
        self, record_id: UUID, fields: dict, actor_id: UUID,
    ) -> NonOwnedCourse:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise NonOwnedCourseError("Non-owned course not found.")
        for key, value in fields.items():
            setattr(record, key, value)
        record.updated_by = actor_id
        record = self._repo.save(record)
        log.info("non_owned_course_updated", id=str(record_id), actor=str(actor_id))
        return record

    def soft_delete(self, record_id: UUID, actor_id: UUID) -> NonOwnedCourse:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise NonOwnedCourseError("Non-owned course not found.")
        record = self._repo.soft_delete(record, actor_id)
        log.info("non_owned_course_deleted", id=str(record_id), actor=str(actor_id))
        return record
