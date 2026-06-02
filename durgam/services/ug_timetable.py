"""UGTimetableService — CRUD for Director's UG timetable grid (§9.3, line 152)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.config_anchors import UGTimetable
from durgam.repositories.ug_timetable import UGTimetableRepository
from durgam.services.org_exceptions import OrgServiceError

log = structlog.get_logger(__name__)


class UGTimetableError(OrgServiceError):
    pass


class UGTimetableService:
    def __init__(self, repo: UGTimetableRepository) -> None:
        self._repo = repo

    def list_by_ay_semester(
        self, academic_year_id: UUID, semester: str,
    ) -> list[UGTimetable]:
        return self._repo.list_by_ay_semester(academic_year_id, semester)

    def create(
        self,
        *,
        academic_year_id: UUID,
        semester: str,
        year_of_study: int,
        day_of_week: int,
        period_number: int,
        course_code: str,
        course_name: str,
        faculty_id_placeholder: str,
        actor_id: UUID,
        room: str | None = None,
        notes: str | None = None,
    ) -> UGTimetable:
        course_code = course_code.strip()
        course_name = course_name.strip()
        faculty_id_placeholder = faculty_id_placeholder.strip()
        if not course_code:
            raise UGTimetableError("Course code is required.")
        if not course_name:
            raise UGTimetableError("Course name is required.")
        if not faculty_id_placeholder:
            raise UGTimetableError("Faculty identifier is required.")
        if semester not in ("odd", "even"):
            raise UGTimetableError("Semester must be 'odd' or 'even'.")
        if year_of_study not in (1, 2):
            raise UGTimetableError("Year of study must be 1 or 2.")
        if not 1 <= day_of_week <= 6:
            raise UGTimetableError("Day of week must be 1 (Mon) to 6 (Sat).")
        if period_number < 1:
            raise UGTimetableError("Period number must be 1 or greater.")

        now = datetime.now(UTC)
        record = UGTimetable(
            academic_year_id=academic_year_id,
            semester=semester,
            year_of_study=year_of_study,
            day_of_week=day_of_week,
            period_number=period_number,
            course_code=course_code,
            course_name=course_name,
            faculty_id_placeholder=faculty_id_placeholder,
            room=room,
            notes=notes,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        record = self._repo.save(record)
        log.info("ug_timetable_slot_created", id=str(record.id), actor=str(actor_id))
        return record

    def update(
        self, record_id: UUID, fields: dict, actor_id: UUID,
    ) -> UGTimetable:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise UGTimetableError("Timetable slot not found.")
        for key, value in fields.items():
            setattr(record, key, value)
        record.updated_by = actor_id
        record = self._repo.save(record)
        log.info("ug_timetable_slot_updated", id=str(record_id), actor=str(actor_id))
        return record

    def soft_delete(self, record_id: UUID, actor_id: UUID) -> UGTimetable:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise UGTimetableError("Timetable slot not found.")
        record = self._repo.soft_delete(record, actor_id)
        log.info("ug_timetable_slot_deleted", id=str(record_id), actor=str(actor_id))
        return record
