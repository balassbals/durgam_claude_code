"""StudentCategoryCountRepository — per-AY singleton with lock enforcement (§8.5 M4)."""

from uuid import UUID

from sqlmodel import Session, select

from durgam.models.config_anchors import AcademicYear, StudentCategoryCount
from durgam.repositories.base import BaseRepository
from durgam.services.org_exceptions import AcademicYearLockedError


class StudentCategoryCountRepository(BaseRepository[StudentCategoryCount]):
    def __init__(self, session: Session) -> None:
        super().__init__(StudentCategoryCount, session)

    def _check_ay_locked(self, academic_year_id: UUID) -> None:
        ay = self._session.get(AcademicYear, academic_year_id)
        if ay is not None and ay.is_locked:
            raise AcademicYearLockedError()

    def get_by_ay(self, academic_year_id: UUID) -> StudentCategoryCount | None:
        return self._session.exec(
            select(StudentCategoryCount).where(
                StudentCategoryCount.academic_year_id == academic_year_id,
                StudentCategoryCount.is_deleted == False,  # noqa: E712
            )
        ).first()

    def save(self, record: StudentCategoryCount) -> StudentCategoryCount:
        self._check_ay_locked(record.academic_year_id)
        return super().save(record)
