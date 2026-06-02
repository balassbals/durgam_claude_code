"""NonOwnedCourseRepository — AY-locked repo for departmentless courses (§9.3)."""

from uuid import UUID

from sqlmodel import Session, select

from durgam.models.config_anchors import AcademicYear, NonOwnedCourse
from durgam.repositories.base import BaseRepository
from durgam.services.org_exceptions import AcademicYearLockedError


class NonOwnedCourseRepository(BaseRepository[NonOwnedCourse]):
    def __init__(self, session: Session) -> None:
        super().__init__(NonOwnedCourse, session)

    def _check_ay_locked(self, academic_year_id: UUID) -> None:
        ay = self._session.get(AcademicYear, academic_year_id)
        if ay is not None and ay.is_locked:
            raise AcademicYearLockedError()

    def list_by_ay(self, academic_year_id: UUID) -> list[NonOwnedCourse]:
        return list(
            self._session.exec(
                select(NonOwnedCourse)
                .where(
                    NonOwnedCourse.academic_year_id == academic_year_id,
                    NonOwnedCourse.is_deleted == False,  # noqa: E712
                )
                .order_by(NonOwnedCourse.course_code)
            ).all()
        )

    def save(self, record: NonOwnedCourse) -> NonOwnedCourse:
        self._check_ay_locked(record.academic_year_id)
        return super().save(record)

    def soft_delete(
        self, record: NonOwnedCourse, actor_id: UUID,
    ) -> NonOwnedCourse:
        self._check_ay_locked(record.academic_year_id)
        return super().soft_delete(record, actor_id)
