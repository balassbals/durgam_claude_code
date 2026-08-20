"""AssignmentRepository — AY-locked repo for faculty/class assignment tables (§9.3).

Parameterised by model type. Used for FacultyMentorAssignment and
ClassTeacherAssignment.
"""

from uuid import UUID

from sqlmodel import Session, select

from durgam.models.base import TimestampedSoftDelete
from durgam.models.config_anchors import AcademicYear
from durgam.repositories.base import BaseRepository
from durgam.services.org_exceptions import AcademicYearLockedError


class AssignmentRepository[T: TimestampedSoftDelete](BaseRepository[T]):
    def __init__(self, model: type[T], session: Session) -> None:
        super().__init__(model, session)

    def _check_ay_locked(self, academic_year_id: UUID) -> None:
        ay = self._session.get(AcademicYear, academic_year_id)
        if ay is not None and ay.is_locked:
            raise AcademicYearLockedError()

    def list_by_ay(self, academic_year_id: UUID) -> list[T]:
        return list(
            self._session.exec(
                select(self._model).where(
                    self._model.academic_year_id == academic_year_id,  # type: ignore[attr-defined]
                    self._model.is_deleted == False,  # noqa: E712
                )
            ).all()
        )

    def list_by_ay_and_scope(
        self, academic_year_id: UUID, scope_id: UUID, scope_column: str,
    ) -> list[T]:
        col = getattr(self._model, scope_column)
        return list(
            self._session.exec(
                select(self._model).where(
                    self._model.academic_year_id == academic_year_id,  # type: ignore[attr-defined]
                    col == scope_id,
                    self._model.is_deleted == False,  # noqa: E712
                )
            ).all()
        )

    def save(self, record: T) -> T:
        self._check_ay_locked(record.academic_year_id)  # type: ignore[attr-defined]
        return super().save(record)

    def soft_delete(self, record: T, actor_id: UUID) -> T:
        self._check_ay_locked(record.academic_year_id)  # type: ignore[attr-defined]
        return super().soft_delete(record, actor_id)
