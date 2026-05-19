"""CourseService — basic CRUD for Course (§8.2, M3 field set, Refinement 3)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.course import Course
from durgam.repositories.course import CourseRepository
from durgam.services.org_exceptions import HardDeleteBlockedError, OrgServiceError

log = structlog.get_logger(__name__)


class CourseError(OrgServiceError):
    pass


class CourseService:
    def __init__(self, course_repo: CourseRepository) -> None:
        self._courses = course_repo

    def list(self, department_id: UUID | None = None) -> list[Course]:
        if department_id is not None:
            return self._courses.list_by_department(department_id)
        return self._courses.list_active()

    def get(self, course_id: UUID) -> Course:
        course = self._courses.get_by_id(course_id)
        if course is None:
            raise CourseError("Course not found.")
        return course

    def create(
        self,
        code: str,
        name: str,
        program_id: UUID,
        department_id: UUID,
        credits: int,
        lecture: int,
        tutorial: int,
        practical: int,
        evaluation: str,
        actor_id: UUID,
    ) -> Course:
        code = code.strip().upper()
        name = name.strip()
        evaluation = evaluation.strip().upper()
        if not code:
            raise CourseError("Course code is required.")
        if not name:
            raise CourseError("Course name is required.")
        if evaluation not in ("I", "E", "IE"):
            raise CourseError("Evaluation must be one of: I, E, IE.")
        if credits < 0:
            raise CourseError("Credits cannot be negative.")
        if self._courses.get_by_code(code) is not None:
            raise CourseError(f"Course code '{code}' is already in use.")
        now = datetime.now(UTC)
        course = Course(
            code=code,
            name=name,
            program_id=program_id,
            department_id=department_id,
            credits=credits,
            lecture=lecture,
            tutorial=tutorial,
            practical=practical,
            evaluation=evaluation,
            is_active=True,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        course = self._courses.save(course)
        log.info("course_created", course_id=str(course.id), actor=str(actor_id))
        return course

    def update(self, course_id: UUID, fields: dict, actor_id: UUID) -> Course:
        if "evaluation" in fields and fields["evaluation"] not in ("I", "E", "IE"):
            raise CourseError("Evaluation must be one of: I, E, IE.")
        course = self.get(course_id)
        for key, value in fields.items():
            setattr(course, key, value)
        course.updated_by = actor_id
        return self._courses.save(course)

    def soft_delete(self, course_id: UUID, actor_id: UUID) -> Course:
        course = self.get(course_id)
        n_scheme = self._courses.count_scheme_usages(course_id)
        if n_scheme > 0:
            raise CourseError(
                f"Course is used in {n_scheme} scheme(s) and cannot be deactivated. "
                "Remove it from all schemes first."
            )
        return self._courses.soft_delete(course, actor_id)

    def hard_delete(self, course_id: UUID, actor_id: UUID) -> None:
        course = self._courses._session.get(Course, course_id)
        if course is None:
            raise CourseError("Course not found.")
        if not course.is_deleted:
            raise CourseError("Course must be deactivated before permanent deletion.")

        n_scheme = self._courses.count_scheme_usages(course_id)
        if n_scheme > 0:
            raise HardDeleteBlockedError(
                f"Course appears in {n_scheme} scheme(s) and cannot be permanently deleted."
            )

        from durgam.models.crosscutting import AuditLog
        from sqlmodel import func, select

        n_audit: int = self._courses._session.exec(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.resource == "course",
                AuditLog.resource_id == str(course_id),
            )
        ).one()
        if n_audit > 0:
            raise HardDeleteBlockedError(
                f"Course has {n_audit} audit record(s) and cannot be permanently deleted."
            )

        self._courses.hard_delete(course)
        log.info("course_hard_deleted", course_id=str(course_id), actor=str(actor_id))
