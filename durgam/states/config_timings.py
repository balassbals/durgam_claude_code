"""ClassTimingsConfigState and WorkingDaysConfigState — singleton config pages."""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from durgam.audit.snapshot import audit_snapshot
from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.config_singleton import ConfigSingletonRepository
from durgam.services.config_singleton import ConfigError, ConfigSingletonService
from durgam.states.base import BaseState


def _svc(session) -> ConfigSingletonService:
    return ConfigSingletonService(config_repo=ConfigSingletonRepository(session))


class ClassTimingsConfigState(BaseState):
    # Displayed / form values (all stored as strings for rx.input compatibility)
    periods_per_day: str = ""
    period_duration_minutes: str = ""
    first_period_start: str = ""
    break_after_period: str = ""        # empty = no break
    break_duration_minutes: str = ""    # empty = no break

    loading: bool = True

    async def load_class_timings(self) -> None:
        guard = self._config_guard("class_timings_config", "configure")
        if guard is not None:
            return guard
        self.loading = True
        with open_session() as session:
            ctc = _svc(session).get_class_timings()
            self.periods_per_day = str(ctc.periods_per_day)
            self.period_duration_minutes = str(ctc.period_duration_minutes)
            self.first_period_start = ctc.first_period_start
            self.break_after_period = str(ctc.break_after_period) if ctc.break_after_period is not None else ""
            self.break_duration_minutes = str(ctc.break_duration_minutes) if ctc.break_duration_minutes is not None else ""
        self._load_nav_entries()
        self.loading = False

    def set_periods_per_day(self, v: str) -> None:
        self.periods_per_day = v

    def set_period_duration_minutes(self, v: str) -> None:
        self.period_duration_minutes = v

    def set_first_period_start(self, v: str) -> None:
        self.first_period_start = v

    def set_break_after_period(self, v: str) -> None:
        self.break_after_period = v

    def set_break_duration_minutes(self, v: str) -> None:
        self.break_duration_minutes = v

    @require_role(action="configure", resource="class_timings_config")
    @audit_action(action="configure", resource="class_timings_config")
    async def save_class_timings(self, form_data: dict) -> None:
        ppd_raw = form_data.get("periods_per_day", "").strip()
        pdm_raw = form_data.get("period_duration_minutes", "").strip()
        fps_raw = form_data.get("first_period_start", "").strip()
        bap_raw = form_data.get("break_after_period", "").strip()
        bdm_raw = form_data.get("break_duration_minutes", "").strip()

        errors: list[str] = []
        try:
            ppd = int(ppd_raw)
        except ValueError:
            errors.append("Periods per day must be a whole number.")
            ppd = None
        try:
            pdm = int(pdm_raw)
        except ValueError:
            errors.append("Period duration must be a whole number.")
            pdm = None

        bap: int | None = None
        if bap_raw:
            try:
                bap = int(bap_raw)
            except ValueError:
                errors.append("Break after period must be a whole number or left blank.")
        bdm: int | None = None
        if bdm_raw:
            try:
                bdm = int(bdm_raw)
            except ValueError:
                errors.append("Break duration must be a whole number or left blank.")

        if bap and not bdm:
            errors.append("Break duration is required when break after period is set.")
        if bap == 0:
            bap = None  # treat 0 as "no break"

        if errors:
            self.flash = " | ".join(errors)
            self.flash_type = "error"
            return

        try:
            with open_session() as session:
                svc = _svc(session)
                ctc = svc.get_class_timings()
                before_snap = audit_snapshot(ctc)
                ctc = svc.save_class_timings(
                    ctc,
                    UUID(self.current_user_id),
                    periods_per_day=ppd,
                    period_duration_minutes=pdm,
                    first_period_start=fps_raw,
                    break_after_period=bap,
                    break_duration_minutes=bdm,
                )
                after_snap = audit_snapshot(ctc)
                session.commit()
                self._set_audit(resource_id=str(ctc.id), before=before_snap, after=after_snap)
        except ConfigError as e:
            self.flash = e.message
            self.flash_type = "error"
            return

        await self.load_class_timings()
        self.flash = "Class timings saved."
        self.flash_type = "success"


class WorkingDaysConfigState(BaseState):
    days_per_week: str = "5"   # "5" or "6"
    loading: bool = True

    async def load_working_days(self) -> None:
        guard = self._config_guard("working_days_config", "configure")
        if guard is not None:
            return guard
        self.loading = True
        with open_session() as session:
            wdc = _svc(session).get_working_days()
            self.days_per_week = str(wdc.days_per_week)
        self._load_nav_entries()
        self.loading = False

    def set_days_per_week(self, v: str) -> None:
        self.days_per_week = v

    @require_role(action="configure", resource="working_days_config")
    @audit_action(action="configure", resource="working_days_config")
    async def save_working_days(self, form_data: dict) -> None:
        dpw_raw = form_data.get("days_per_week", "5").strip()
        try:
            dpw = int(dpw_raw)
        except ValueError:
            self.flash = "Days per week must be 5 or 6."
            self.flash_type = "error"
            return

        try:
            with open_session() as session:
                svc = _svc(session)
                wdc = svc.get_working_days()
                before_snap = audit_snapshot(wdc)
                wdc = svc.save_working_days(wdc, UUID(self.current_user_id), days_per_week=dpw)
                after_snap = audit_snapshot(wdc)
                session.commit()
                self._set_audit(resource_id=str(wdc.id), before=before_snap, after=after_snap)
        except ConfigError as e:
            self.flash = e.message
            self.flash_type = "error"
            return

        await self.load_working_days()
        self.flash = "Working days saved."
        self.flash_type = "success"
