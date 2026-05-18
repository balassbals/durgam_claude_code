"""ConfigSingletonRepository — ClassTimingsConfig and WorkingDaysConfig (§9.3 M3).

Both models are singletons (one row per table). get_or_create returns the
existing row or inserts a default. save updates the existing singleton row.
"""

from sqlmodel import Session, select

from durgam.models.config_anchors import ClassTimingsConfig, WorkingDaysConfig


class ConfigSingletonRepository:
    """Not a BaseRepository subclass — manages two distinct singleton models."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── ClassTimingsConfig ────────────────────────────────────────────────────

    def get_or_create_class_timings(self) -> ClassTimingsConfig:
        """Return the singleton class-timings row, creating a default if absent."""
        ctc = self._session.exec(
            select(ClassTimingsConfig).where(
                ClassTimingsConfig.is_deleted == False  # noqa: E712
            )
        ).first()
        if ctc is None:
            from datetime import UTC, datetime

            now = datetime.now(UTC)
            ctc = ClassTimingsConfig(
                periods_per_day=8,
                period_duration_minutes=50,
                first_period_start="08:00",
                break_after_period=4,
                break_duration_minutes=45,
                created_at=now,
                updated_at=now,
            )
            self._session.add(ctc)
            self._session.flush()
            self._session.refresh(ctc)
        return ctc

    def save_class_timings(self, ctc: ClassTimingsConfig) -> ClassTimingsConfig:
        from datetime import UTC, datetime

        ctc.updated_at = datetime.now(UTC)
        self._session.add(ctc)
        self._session.flush()
        self._session.refresh(ctc)
        return ctc

    # ── WorkingDaysConfig ─────────────────────────────────────────────────────

    def get_or_create_working_days(self) -> WorkingDaysConfig:
        """Return the singleton working-days row, creating a default if absent."""
        wdc = self._session.exec(
            select(WorkingDaysConfig).where(
                WorkingDaysConfig.is_deleted == False  # noqa: E712
            )
        ).first()
        if wdc is None:
            from datetime import UTC, datetime

            now = datetime.now(UTC)
            wdc = WorkingDaysConfig(
                days_per_week=5,
                created_at=now,
                updated_at=now,
            )
            self._session.add(wdc)
            self._session.flush()
            self._session.refresh(wdc)
        return wdc

    def save_working_days(self, wdc: WorkingDaysConfig) -> WorkingDaysConfig:
        from datetime import UTC, datetime

        wdc.updated_at = datetime.now(UTC)
        self._session.add(wdc)
        self._session.flush()
        self._session.refresh(wdc)
        return wdc
