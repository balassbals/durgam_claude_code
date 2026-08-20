"""AssignmentService — CRUD for faculty mentor + class teacher (§9.3).

Uses AssignmentRepository[T] parameterised per entity type.

(class_coordinator_assignments was removed in M10 Phase 11D — Q-P11D.1 — because
class coordinators are STUDENTS, not faculty; re-introduce when the student
domain ships. See TD-088.)
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlmodel import Session, select

from durgam.models.config_anchors import (
    ClassTeacherAssignment,
    FacultyMentorAssignment,
    FacultyMentorConfirmation,
)
from durgam.repositories.assignment import AssignmentRepository
from durgam.services.org_exceptions import OrgServiceError

log = structlog.get_logger(__name__)


class AssignmentError(OrgServiceError):
    pass


def resolve_faculty_id_by_employee_id(session, employee_id: str) -> UUID:
    """Resolve a faculty employee_id (the Q-P11.2 lookup key) to a Faculty UUID.

    11A bridge: assignment forms accepted an employee_id text input until the
    11C Faculty picker dropdown replaced it. As of Phase 11C this helper is no
    longer called by any of the five admin forms (they emit faculty_id directly
    from the picker); it is retained because tests still exercise it as the
    canonical employee_id->faculty_id resolution. Raises AssignmentError if no
    active faculty has that employee_id.
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


def is_material_mentor_edit(
    existing: FacultyMentorAssignment, new_fields: dict,
) -> bool:
    """Return True if faculty_id or student_id_placeholder changes (material edit).

    Notes-only changes are cosmetic and do NOT invalidate the roster confirmation.
    Caller is responsible for passing the pre-update record as `existing`.
    """
    if "faculty_id" in new_fields and new_fields["faculty_id"] != existing.faculty_id:
        return True
    if (
        "student_id_placeholder" in new_fields
        and new_fields["student_id_placeholder"] != existing.student_id_placeholder
    ):
        return True
    return False


def invalidate_confirmation(
    ay_id: UUID, campus_id: UUID, actor_id: UUID, session: Session,
) -> str | None:
    """Soft-delete the active FacultyMentorConfirmation for an AY+campus pair.

    Returns the confirmation's id (str) if one was invalidated, or None if no
    active confirmation existed.  Caller must commit the session after this call.
    """
    confirmation = session.exec(
        select(FacultyMentorConfirmation).where(
            FacultyMentorConfirmation.academic_year_id == ay_id,
            FacultyMentorConfirmation.campus_id == campus_id,
            FacultyMentorConfirmation.is_deleted == False,  # noqa: E712
        )
    ).first()
    if confirmation is None:
        return None
    now = datetime.now(UTC)
    confirmation.is_deleted = True
    confirmation.deleted_at = now
    confirmation.deleted_by = actor_id
    session.add(confirmation)
    log.info(
        "faculty_mentor_confirmation_invalidated",
        confirmation_id=str(confirmation.id),
        ay_id=str(ay_id),
        campus_id=str(campus_id),
        actor=str(actor_id),
    )
    return str(confirmation.id)


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
