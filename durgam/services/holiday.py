"""HolidayService — AY-scoped holiday CRUD (§8.5 M4)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

import structlog
from sqlmodel import Session, select

from durgam.models.config_anchors import Holiday
from durgam.repositories.holiday import HolidayRepository
from durgam.services.org_exceptions import OrgServiceError

log = structlog.get_logger(__name__)


class HolidayError(OrgServiceError):
    pass


class HolidayService:
    def __init__(self, holiday_repo: HolidayRepository) -> None:
        self._holidays = holiday_repo

    def list_by_ay(self, academic_year_id: UUID) -> list[Holiday]:
        return self._holidays.list_by_ay(academic_year_id)

    def create(
        self,
        academic_year_id: UUID,
        holiday_date: date,
        name: str,
        actor_id: UUID,
    ) -> Holiday:
        name = name.strip()
        if not name:
            raise HolidayError("Holiday name is required.")
        if self._holidays.get_by_date_and_ay(holiday_date, academic_year_id) is not None:
            raise HolidayError("A holiday already exists on this date for this academic year.")
        now = datetime.now(UTC)
        holiday = Holiday(
            academic_year_id=academic_year_id,
            holiday_date=holiday_date,
            name=name,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        holiday = self._holidays.save(holiday)
        log.info(
            "holiday_created",
            holiday_id=str(holiday.id),
            date=str(holiday_date),
            actor=str(actor_id),
        )
        return holiday

    def update(
        self,
        holiday_id: UUID,
        fields: dict,
        actor_id: UUID,
    ) -> Holiday:
        holiday = self._holidays.get_by_id(holiday_id)
        if holiday is None:
            raise HolidayError("Holiday not found.")
        for key, value in fields.items():
            setattr(holiday, key, value)
        holiday.updated_by = actor_id
        holiday = self._holidays.save(holiday)
        log.info("holiday_updated", holiday_id=str(holiday_id), actor=str(actor_id))
        return holiday

    def soft_delete(
        self,
        holiday_id: UUID,
        actor_id: UUID,
    ) -> Holiday:
        holiday = self._holidays.get_by_id(holiday_id)
        if holiday is None:
            raise HolidayError("Holiday not found.")
        holiday = self._holidays.soft_delete(holiday, actor_id)
        log.info("holiday_deleted", holiday_id=str(holiday_id), actor=str(actor_id))
        return holiday


def get_holiday_dates_in_window(
    session: Session,
    window_start: date,
    window_end: date,
) -> frozenset[date]:
    """Return distinct calendar dates that are declared holidays in any
    non-deleted Holiday row whose date falls in [window_start, window_end].

    Implements the Q4(a) AY-union semantics implicitly: the query is over
    all Holiday rows regardless of academic_year_id, so a date that appears
    as a Holiday in either AY1 or AY2 (when the window straddles a rollover)
    is included exactly once in the returned frozenset.

    window_start and window_end are INCLUSIVE bounds. Caller is responsible
    for choosing a sufficiently wide window — recommend scheduled_date to
    scheduled_date + 14 days as the safe upper bound (worst-case 2-working-day
    extension if every day were a holiday).
    """
    stmt = (
        select(Holiday.holiday_date)
        .where(
            Holiday.holiday_date >= window_start,
            Holiday.holiday_date <= window_end,
            Holiday.is_deleted == False,  # noqa: E712
        )
        .distinct()
    )
    return frozenset(session.exec(stmt).all())
