"""UGTimetableRepository — AY-locked repo for Director's UG timetable grid (§9.3)."""

from uuid import UUID

from sqlmodel import Session, select

from durgam.models.config_anchors import AcademicYear, UGTimetable
from durgam.repositories.base import BaseRepository
from durgam.services.org_exceptions import AcademicYearLockedError


class UGTimetableRepository(BaseRepository[UGTimetable]):
    def __init__(self, session: Session) -> None:
        super().__init__(UGTimetable, session)

    def _check_ay_locked(self, academic_year_id: UUID) -> None:
        ay = self._session.get(AcademicYear, academic_year_id)
        if ay is not None and ay.is_locked:
            raise AcademicYearLockedError()

    def list_by_ay_semester(
        self, academic_year_id: UUID, semester: str,
    ) -> list[UGTimetable]:
        return list(
            self._session.exec(
                select(UGTimetable)
                .where(
                    UGTimetable.academic_year_id == academic_year_id,
                    UGTimetable.semester == semester,
                    UGTimetable.is_deleted == False,  # noqa: E712
                )
                .order_by(
                    UGTimetable.year_of_study,
                    UGTimetable.day_of_week,
                    UGTimetable.period_number,
                )
            ).all()
        )

    def save(self, record: UGTimetable) -> UGTimetable:
        self._check_ay_locked(record.academic_year_id)
        return super().save(record)

    def soft_delete(
        self, record: UGTimetable, actor_id: UUID,
    ) -> UGTimetable:
        self._check_ay_locked(record.academic_year_id)
        return super().soft_delete(record, actor_id)
