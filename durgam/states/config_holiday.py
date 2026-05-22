"""HolidayConfigState — AY-scoped holiday list, create, edit, delete."""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.academic_year import AcademicYearRepository
from durgam.repositories.holiday import HolidayRepository
from durgam.services.holiday import HolidayError, HolidayService
from durgam.services.org_exceptions import AcademicYearLockedError
from durgam.states.base import BaseState


def _svc(session) -> HolidayService:
    return HolidayService(holiday_repo=HolidayRepository(session))


class HolidayConfigState(BaseState):
    # AY selector
    ay_options: list[dict[str, str]] = []
    selected_ay_id: str = ""
    ay_is_locked: bool = False

    # List
    holidays: list[dict[str, str]] = []
    loading: bool = True

    # Form
    show_form: bool = False
    editing_id: str = ""
    form_date: str = ""
    form_name: str = ""

    # Confirmation dialog
    confirm_open: bool = False
    confirm_holiday_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    async def load_holidays(self) -> None:
        guard = self._config_guard("holiday", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.holidays = []
        self.show_form = False
        self.ay_options = []

        with open_session() as session:
            ay_repo = AcademicYearRepository(session)
            for ay in ay_repo.list_active():
                self.ay_options.append({
                    "value": str(ay.id),
                    "label": ay.code,
                    "is_locked": "1" if ay.is_locked else "0",
                })
            if self.ay_options and not self.selected_ay_id:
                self.selected_ay_id = self.ay_options[0]["value"]

            self._load_holidays_for_ay(session)

        self._load_nav_entries()
        self.loading = False

    def _load_holidays_for_ay(self, session) -> None:
        self.holidays = []
        if not self.selected_ay_id:
            self.ay_is_locked = False
            return
        ay_repo = AcademicYearRepository(session)
        ay = ay_repo.get_by_id(UUID(self.selected_ay_id))
        self.ay_is_locked = ay.is_locked if ay else False

        svc = _svc(session)
        for h in svc.list_by_ay(UUID(self.selected_ay_id)):
            self.holidays.append({
                "id": str(h.id),
                "date": str(h.holiday_date),
                "name": h.name,
            })

    async def on_ay_change(self, value: str) -> None:
        self.selected_ay_id = value
        self.show_form = False
        self.flash = ""
        self.flash_type = "info"
        with open_session() as session:
            self._load_holidays_for_ay(session)
        matched = [o for o in self.ay_options if o["value"] == value]
        self.ay_is_locked = bool(matched and matched[0]["is_locked"] == "1")

    def set_form_date(self, v: str) -> None:
        self.form_date = v

    def set_form_name(self, v: str) -> None:
        self.form_name = v

    def open_create(self):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ""
        self.form_date = ""
        self.form_name = ""
        self.show_form = True

    def open_edit(self, holiday_id: str, date_str: str, name: str):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = holiday_id
        self.form_date = date_str
        self.form_name = name
        self.show_form = True

    def cancel_form(self):
        self.show_form = False
        self.editing_id = ""
        self.form_date = ""
        self.form_name = ""
        self.flash = ""
        self.flash_type = "info"

    @require_role(action="write", resource="holiday")
    @audit_action(action="write", resource="holiday")
    async def save_holiday(self, form_data: dict) -> None:
        from datetime import date

        name = form_data.get("form_name", "").strip()
        date_raw = form_data.get("form_date", "").strip()
        editing_id = form_data.get("editing_id", "").strip()

        if not date_raw:
            self.flash = "Date is required."
            self.flash_type = "error"
            return

        try:
            holiday_date = date.fromisoformat(date_raw)
        except ValueError:
            self.flash = "Invalid date format."
            self.flash_type = "error"
            return

        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                if not editing_id:
                    svc.create(
                        UUID(self.selected_ay_id),
                        holiday_date,
                        name,
                        actor_id,
                    )
                else:
                    svc.update(
                        UUID(editing_id),
                        {"holiday_date": holiday_date, "name": name},
                        actor_id,
                    )
                session.commit()
            self.flash = "Holiday saved."
            self.flash_type = "success"
        except (HolidayError, AcademicYearLockedError) as e:
            self.flash = e.message if hasattr(e, "message") else str(e)
            self.flash_type = "error"
        self.show_form = False
        self.editing_id = ""
        await self.load_holidays()

    def open_soft_delete_confirm(self, holiday_id: str, name: str) -> None:
        self.confirm_holiday_id = holiday_id
        self.confirm_title = f"Delete holiday '{name}'?"
        self.confirm_body = "This will remove the holiday from the calendar."
        self.confirm_open = True

    @require_role(action="delete", resource="holiday")
    @audit_action(action="delete", resource="holiday")
    async def soft_delete_holiday(self) -> None:
        try:
            with open_session() as session:
                _svc(session).soft_delete(
                    UUID(self.confirm_holiday_id), UUID(self.current_user_id)
                )
                session.commit()
            self.flash = "Holiday deleted."
            self.flash_type = "success"
        except (HolidayError, AcademicYearLockedError) as e:
            self.flash = e.message if hasattr(e, "message") else str(e)
            self.flash_type = "error"
        self.confirm_open = False
        self.confirm_holiday_id = ""
        await self.load_holidays()

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_holiday_id = ""
