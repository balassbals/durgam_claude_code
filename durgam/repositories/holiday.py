"""HolidayRepository — AY-scoped holidays with lock enforcement (§8.5 M4)."""

from datetime import date
from uuid import UUID

from sqlmodel import Session, select

from durgam.models.config_anchors import AcademicYear, Holiday
from durgam.repositories.base import BaseRepository
from durgam.services.org_exceptions import AcademicYearLockedError


class HolidayRepository(BaseRepository[Holiday]):
    def __init__(self, session: Session) -> None:
        super().__init__(Holiday, session)

    def _check_ay_locked(self, academic_year_id: UUID) -> None:
        ay = self._session.get(AcademicYear, academic_year_id)
        if ay is not None and ay.is_locked:
            raise AcademicYearLockedError()

    def list_by_ay(self, academic_year_id: UUID) -> list[Holiday]:
        return list(
            self._session.exec(
                select(Holiday)
                .where(
                    Holiday.academic_year_id == academic_year_id,
                    Holiday.is_deleted == False,  # noqa: E712
                )
                .order_by(Holiday.holiday_date)  # type: ignore[attr-defined]
            ).all()
        )

    def get_by_date_and_ay(self, holiday_date: date, academic_year_id: UUID) -> Holiday | None:
        return self._session.exec(
            select(Holiday).where(
                Holiday.holiday_date == holiday_date,
                Holiday.academic_year_id == academic_year_id,
                Holiday.is_deleted == False,  # noqa: E712
            )
        ).first()

    def save(self, record: Holiday) -> Holiday:
        self._check_ay_locked(record.academic_year_id)
        return super().save(record)

    def soft_delete(self, record: Holiday, actor_id: UUID) -> Holiday:
        self._check_ay_locked(record.academic_year_id)
        return super().soft_delete(record, actor_id)
