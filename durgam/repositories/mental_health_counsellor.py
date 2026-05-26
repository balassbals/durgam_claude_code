"""MentalHealthCounsellorRepository — AY-scoped, campus-filtered (§9.3)."""

from uuid import UUID

from sqlmodel import Session, select

from durgam.models.config_anchors import AcademicYear, MentalHealthCounsellor
from durgam.repositories.base import BaseRepository
from durgam.services.org_exceptions import AcademicYearLockedError


class MentalHealthCounsellorRepository(BaseRepository[MentalHealthCounsellor]):
    def __init__(self, session: Session) -> None:
        super().__init__(MentalHealthCounsellor, session)

    def _check_ay_locked(self, academic_year_id: UUID) -> None:
        ay = self._session.get(AcademicYear, academic_year_id)
        if ay is not None and ay.is_locked:
            raise AcademicYearLockedError()

    def list_by_ay_campus(
        self, academic_year_id: UUID, campus_id: UUID,
    ) -> list[MentalHealthCounsellor]:
        return list(
            self._session.exec(
                select(MentalHealthCounsellor)
                .where(
                    MentalHealthCounsellor.academic_year_id == academic_year_id,
                    MentalHealthCounsellor.campus_id == campus_id,
                    MentalHealthCounsellor.is_deleted == False,  # noqa: E712
                )
                .order_by(MentalHealthCounsellor.display_order)  # type: ignore[attr-defined]
            ).all()
        )

    def save(self, record: MentalHealthCounsellor) -> MentalHealthCounsellor:
        self._check_ay_locked(record.academic_year_id)
        return super().save(record)

    def soft_delete(
        self, record: MentalHealthCounsellor, actor_id: UUID,
    ) -> MentalHealthCounsellor:
        self._check_ay_locked(record.academic_year_id)
        return super().soft_delete(record, actor_id)
