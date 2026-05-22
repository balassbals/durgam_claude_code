"""CalendarEntryRepository — AY-scoped calendar entries with lock enforcement (§8.5 M4)."""

from uuid import UUID

from sqlmodel import Session, select

from durgam.models.config_anchors import AcademicYear, CalendarEntry
from durgam.repositories.base import BaseRepository
from durgam.services.org_exceptions import AcademicYearLockedError


class CalendarEntryRepository(BaseRepository[CalendarEntry]):
    def __init__(self, session: Session) -> None:
        super().__init__(CalendarEntry, session)

    def _check_ay_locked(self, academic_year_id: UUID) -> None:
        ay = self._session.get(AcademicYear, academic_year_id)
        if ay is not None and ay.is_locked:
            raise AcademicYearLockedError()

    def list_by_ay(self, academic_year_id: UUID) -> list[CalendarEntry]:
        return list(
            self._session.exec(
                select(CalendarEntry)
                .where(
                    CalendarEntry.academic_year_id == academic_year_id,
                    CalendarEntry.is_deleted == False,  # noqa: E712
                )
                .order_by(CalendarEntry.starts_at)  # type: ignore[attr-defined]
            ).all()
        )

    def list_by_ay_and_type(self, academic_year_id: UUID, entry_type: str) -> list[CalendarEntry]:
        return list(
            self._session.exec(
                select(CalendarEntry)
                .where(
                    CalendarEntry.academic_year_id == academic_year_id,
                    CalendarEntry.entry_type == entry_type,
                    CalendarEntry.is_deleted == False,  # noqa: E712
                )
                .order_by(CalendarEntry.starts_at)  # type: ignore[attr-defined]
            ).all()
        )

    def list_by_ay_and_owner(self, academic_year_id: UUID, owner_user_id: UUID) -> list[CalendarEntry]:
        return list(
            self._session.exec(
                select(CalendarEntry)
                .where(
                    CalendarEntry.academic_year_id == academic_year_id,
                    CalendarEntry.owner_user_id == owner_user_id,
                    CalendarEntry.is_deleted == False,  # noqa: E712
                )
                .order_by(CalendarEntry.starts_at)  # type: ignore[attr-defined]
            ).all()
        )

    def save(self, record: CalendarEntry) -> CalendarEntry:
        self._check_ay_locked(record.academic_year_id)
        return super().save(record)

    def soft_delete(self, record: CalendarEntry, actor_id: UUID) -> CalendarEntry:
        self._check_ay_locked(record.academic_year_id)
        return super().soft_delete(record, actor_id)
