"""HolidayService — AY-scoped holiday CRUD (§8.5 M4)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

import structlog

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
