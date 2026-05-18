"""CourseRepository — queries for the Course model (§8.2, M3 basic fields)."""

from uuid import UUID

from sqlmodel import Session, func, select

from durgam.models.course import Course
from durgam.repositories.base import BaseRepository


class CourseRepository(BaseRepository[Course]):
    def __init__(self, session: Session) -> None:
        super().__init__(Course, session)

    def list_active(self) -> list[Course]:
        """Return all active courses ordered by code."""
        return list(
            self._session.exec(
                select(Course)
                .where(Course.is_deleted == False)  # noqa: E712
                .order_by(Course.code)  # type: ignore[attr-defined]
            ).all()
        )

    def get_by_code(self, code: str) -> Course | None:
        return self._session.exec(
            select(Course).where(
                Course.code == code,
                Course.is_deleted == False,  # noqa: E712
            )
        ).first()

    def list_by_department(self, department_id: UUID) -> list[Course]:
        return list(
            self._session.exec(
                select(Course).where(
                    Course.department_id == department_id,
                    Course.is_deleted == False,  # noqa: E712
                ).order_by(Course.code)  # type: ignore[attr-defined]
            ).all()
        )

    def list_by_program(self, program_id: UUID) -> list[Course]:
        return list(
            self._session.exec(
                select(Course).where(
                    Course.program_id == program_id,
                    Course.is_deleted == False,  # noqa: E712
                ).order_by(Course.code)  # type: ignore[attr-defined]
            ).all()
        )

    def count_scheme_usages(self, course_id: UUID) -> int:
        """Count how many scheme-of-instruction rows reference this course.

        Used by the service-layer hard-delete guard.
        """
        from durgam.models.program import ProgramSchemeCourse

        return self._session.exec(
            select(func.count(ProgramSchemeCourse.scheme_id)).where(
                ProgramSchemeCourse.course_id == course_id
            )
        ).one()

    def hard_delete(self, course: Course) -> None:
        self._session.delete(course)
        self._session.flush()
