"""AssignmentService — CRUD for faculty mentor, class teacher, class coordinator (§9.3).

Uses AssignmentRepository[T] parameterised per entity type.
ClassCoordinatorAssignment enforces max 2 per class per AY.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.config_anchors import (
    ClassCoordinatorAssignment,
    ClassTeacherAssignment,
    FacultyMentorAssignment,
)
from durgam.repositories.assignment import AssignmentRepository
from durgam.services.org_exceptions import OrgServiceError

log = structlog.get_logger(__name__)

MAX_COORDINATORS_PER_CLASS = 2


class AssignmentError(OrgServiceError):
    pass


def resolve_faculty_id_by_employee_id(session, employee_id: str) -> UUID:
    """Resolve a faculty employee_id (the Q-P11.2 lookup key) to a Faculty UUID.

    11A bridge: assignment forms accept an employee_id text input until the 11C
    Faculty picker dropdown replaces it. Raises AssignmentError if no active
    faculty has that employee_id.
    """
    from durgam.repositories.faculty import FacultyRepository

    employee_id = (employee_id or "").strip()
    if not employee_id:
        raise AssignmentError("Faculty employee ID is required.")
    faculty = FacultyRepository(session).get_by_employee_id(employee_id)
    if faculty is None:
        raise AssignmentError(f"No faculty found with employee ID '{employee_id}'.")
    return faculty.id


def faculty_display(session, faculty_id: UUID) -> str:
    """Return a human-readable label for a faculty_id: 'EMP-ID — Title First Last'."""
    from durgam.repositories.faculty import FacultyRepository

    faculty = FacultyRepository(session).get(faculty_id)
    if faculty is None:
        return str(faculty_id)
    name = " ".join(
        p for p in (faculty.title, faculty.first_name, faculty.last_name) if p
    )
    return f"{faculty.employee_id} — {name}"


class FacultyMentorService:
    def __init__(self, repo: AssignmentRepository[FacultyMentorAssignment]) -> None:
        self._repo = repo

    def list_by_ay_campus(
        self, academic_year_id: UUID, campus_id: UUID,
    ) -> list[FacultyMentorAssignment]:
        return self._repo.list_by_ay_and_scope(
            academic_year_id, campus_id, "campus_id",
        )

    def create(
        self,
        *,
        academic_year_id: UUID,
        campus_id: UUID,
        faculty_id: UUID,
        student_id_placeholder: str,
        actor_id: UUID,
        notes: str | None = None,
    ) -> FacultyMentorAssignment:
        student_id_placeholder = student_id_placeholder.strip()
        if not student_id_placeholder:
            raise AssignmentError("Student identifier is required.")

        now = datetime.now(UTC)
        record = FacultyMentorAssignment(
            academic_year_id=academic_year_id,
            campus_id=campus_id,
            faculty_id=faculty_id,
            student_id_placeholder=student_id_placeholder,
            notes=notes,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        record = self._repo.save(record)
        log.info("faculty_mentor_created", id=str(record.id), actor=str(actor_id))
        return record

    def update(
        self, record_id: UUID, fields: dict, actor_id: UUID,
    ) -> FacultyMentorAssignment:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise AssignmentError("Faculty mentor assignment not found.")
        for key, value in fields.items():
            setattr(record, key, value)
        record.updated_by = actor_id
        record = self._repo.save(record)
        log.info("faculty_mentor_updated", id=str(record_id), actor=str(actor_id))
        return record

    def soft_delete(self, record_id: UUID, actor_id: UUID) -> FacultyMentorAssignment:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise AssignmentError("Faculty mentor assignment not found.")
        record = self._repo.soft_delete(record, actor_id)
        log.info("faculty_mentor_deleted", id=str(record_id), actor=str(actor_id))
        return record


class ClassTeacherService:
    def __init__(self, repo: AssignmentRepository[ClassTeacherAssignment]) -> None:
        self._repo = repo

    def list_by_ay_dept(
        self, academic_year_id: UUID, department_id: UUID,
    ) -> list[ClassTeacherAssignment]:
        return self._repo.list_by_ay_and_scope(
            academic_year_id, department_id, "department_id",
        )

    def create(
        self,
        *,
        academic_year_id: UUID,
        department_id: UUID,
        faculty_id: UUID,
        class_identifier: str,
        actor_id: UUID,
        notes: str | None = None,
    ) -> ClassTeacherAssignment:
        class_identifier = class_identifier.strip()
        if not class_identifier:
            raise AssignmentError("Class identifier is required.")

        now = datetime.now(UTC)
        record = ClassTeacherAssignment(
            academic_year_id=academic_year_id,
            department_id=department_id,
            faculty_id=faculty_id,
            class_identifier=class_identifier,
            notes=notes,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        record = self._repo.save(record)
        log.info("class_teacher_created", id=str(record.id), actor=str(actor_id))
        return record

    def update(
        self, record_id: UUID, fields: dict, actor_id: UUID,
    ) -> ClassTeacherAssignment:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise AssignmentError("Class teacher assignment not found.")
        for key, value in fields.items():
            setattr(record, key, value)
        record.updated_by = actor_id
        record = self._repo.save(record)
        log.info("class_teacher_updated", id=str(record_id), actor=str(actor_id))
        return record

    def soft_delete(self, record_id: UUID, actor_id: UUID) -> ClassTeacherAssignment:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise AssignmentError("Class teacher assignment not found.")
        record = self._repo.soft_delete(record, actor_id)
        log.info("class_teacher_deleted", id=str(record_id), actor=str(actor_id))
        return record


class ClassCoordinatorService:
    def __init__(self, repo: AssignmentRepository[ClassCoordinatorAssignment]) -> None:
        self._repo = repo

    def list_by_ay_dept(
        self, academic_year_id: UUID, department_id: UUID,
    ) -> list[ClassCoordinatorAssignment]:
        return self._repo.list_by_ay_and_scope(
            academic_year_id, department_id, "department_id",
        )

    def create(
        self,
        *,
        academic_year_id: UUID,
        department_id: UUID,
        faculty_id: UUID,
        class_identifier: str,
        actor_id: UUID,
        notes: str | None = None,
    ) -> ClassCoordinatorAssignment:
        class_identifier = class_identifier.strip()
        if not class_identifier:
            raise AssignmentError("Class identifier is required.")

        current_count = self._repo.count_by_ay_class(
            academic_year_id, class_identifier,
        )
        if current_count >= MAX_COORDINATORS_PER_CLASS:
            raise AssignmentError(
                f"Maximum {MAX_COORDINATORS_PER_CLASS} coordinators per class per academic year."
            )

        now = datetime.now(UTC)
        record = ClassCoordinatorAssignment(
            academic_year_id=academic_year_id,
            department_id=department_id,
            faculty_id=faculty_id,
            class_identifier=class_identifier,
            notes=notes,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        record = self._repo.save(record)
        log.info("class_coordinator_created", id=str(record.id), actor=str(actor_id))
        return record

    def update(
        self, record_id: UUID, fields: dict, actor_id: UUID,
    ) -> ClassCoordinatorAssignment:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise AssignmentError("Class coordinator assignment not found.")
        for key, value in fields.items():
            setattr(record, key, value)
        record.updated_by = actor_id
        record = self._repo.save(record)
        log.info("class_coordinator_updated", id=str(record_id), actor=str(actor_id))
        return record

    def soft_delete(self, record_id: UUID, actor_id: UUID) -> ClassCoordinatorAssignment:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise AssignmentError("Class coordinator assignment not found.")
        record = self._repo.soft_delete(record, actor_id)
        log.info("class_coordinator_deleted", id=str(record_id), actor=str(actor_id))
        return record
