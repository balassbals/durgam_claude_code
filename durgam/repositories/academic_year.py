"""AcademicYearRepository — queries for AcademicYear (§8.5, §9.3 M4)."""

from datetime import date
from uuid import UUID

from sqlmodel import Session, select

from durgam.models.config_anchors import AcademicYear
from durgam.repositories.base import BaseRepository


class AcademicYearRepository(BaseRepository[AcademicYear]):
    def __init__(self, session: Session) -> None:
        super().__init__(AcademicYear, session)

    def list_active(self) -> list[AcademicYear]:
        return list(
            self._session.exec(
                select(AcademicYear)
                .where(AcademicYear.is_deleted == False)  # noqa: E712
                .order_by(AcademicYear.starts_on.desc())  # type: ignore[attr-defined]
            ).all()
        )

    def get_by_code(self, code: str) -> AcademicYear | None:
        return self._session.exec(
            select(AcademicYear).where(
                AcademicYear.code == code,
                AcademicYear.is_deleted == False,  # noqa: E712
            )
        ).first()

    def lock_master_calendar(self, ay_id: UUID) -> AcademicYear:
        ay = self.get_by_id(ay_id)
        if ay is None:
            raise ValueError("AcademicYear not found")
        ay.master_calendar_locked = True
        return self.save(ay)

    def confirm_iqac(self, ay_id: UUID) -> AcademicYear:
        ay = self.get_by_id(ay_id)
        if ay is None:
            raise ValueError("AcademicYear not found")
        ay.iqac_confirmed = True
        return self.save(ay)

    def lock_for_rollover(self, ay_id: UUID) -> AcademicYear:
        ay = self.get_by_id(ay_id)
        if ay is None:
            raise ValueError("AcademicYear not found")
        ay.is_locked = True
        return self.save(ay)

    def list_expired_unlocked(self, as_of: date | None = None) -> list[AcademicYear]:
        """Return AYs whose ends_on < as_of and is_locked is False."""
        if as_of is None:
            as_of = date.today()
        return list(
            self._session.exec(
                select(AcademicYear).where(
                    AcademicYear.ends_on < as_of,
                    AcademicYear.is_locked == False,  # noqa: E712
                    AcademicYear.is_deleted == False,  # noqa: E712
                )
            ).all()
        )
