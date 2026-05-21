"""ConfigSingletonService — ClassTimingsConfig and WorkingDaysConfig (§9.3 M3).

Both configs are singletons: one row per table, no delete, configure action.
"""

from uuid import UUID

import structlog

from durgam.models.config_anchors import ClassTimingsConfig, WorkingDaysConfig
from durgam.repositories.config_singleton import ConfigSingletonRepository
from durgam.services.org_exceptions import OrgServiceError

log = structlog.get_logger(__name__)


class ConfigError(OrgServiceError):
    pass


class ConfigSingletonService:
    def __init__(self, config_repo: ConfigSingletonRepository) -> None:
        self._config = config_repo

    def get_class_timings(self) -> ClassTimingsConfig:
        return self._config.get_or_create_class_timings()

    def save_class_timings(
        self,
        ctc: ClassTimingsConfig,
        actor_id: UUID,
        *,
        periods_per_day: int | None = None,
        period_duration_minutes: int | None = None,
        first_period_start: str | None = None,
        break_after_period: int | None = None,
        break_duration_minutes: int | None = None,
    ) -> ClassTimingsConfig:
        """Apply validated field updates to the class-timings singleton."""
        if periods_per_day is not None:
            if periods_per_day < 1 or periods_per_day > 20:
                raise ConfigError("Periods per day must be between 1 and 20.")
            ctc.periods_per_day = periods_per_day
        if period_duration_minutes is not None:
            if period_duration_minutes < 10 or period_duration_minutes > 180:
                raise ConfigError("Period duration must be between 10 and 180 minutes.")
            ctc.period_duration_minutes = period_duration_minutes
        if first_period_start is not None:
            _validate_hhmm(first_period_start)
            ctc.first_period_start = first_period_start
        if break_after_period is not None:
            ctc.break_after_period = break_after_period
        if break_duration_minutes is not None:
            ctc.break_duration_minutes = break_duration_minutes
        ctc.updated_by = actor_id
        ctc = self._config.save_class_timings(ctc)
        log.info("class_timings_updated", actor=str(actor_id))
        return ctc

    def get_working_days(self) -> WorkingDaysConfig:
        return self._config.get_or_create_working_days()

    def save_working_days(
        self,
        wdc: WorkingDaysConfig,
        actor_id: UUID,
        *,
        days_per_week: int | None = None,
    ) -> WorkingDaysConfig:
        if days_per_week is not None:
            if days_per_week not in (5, 6):
                raise ConfigError("Days per week must be 5 or 6.")
            wdc.days_per_week = days_per_week
        wdc.updated_by = actor_id
        wdc = self._config.save_working_days(wdc)
        log.info("working_days_updated", actor=str(actor_id))
        return wdc


def _validate_hhmm(value: str) -> None:
    """Raise ConfigError if value is not a valid zero-padded HH:MM string."""
    parts = value.split(":")
    if len(parts) != 2 or len(parts[0]) != 2 or len(parts[1]) != 2:
        raise ConfigError(f"Time must be in HH:MM format, got: {value!r}")
    try:
        hh, mm = int(parts[0]), int(parts[1])
    except ValueError:
        raise ConfigError(f"Time must be in HH:MM format, got: {value!r}")
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ConfigError(f"Invalid time value: {value!r}")
