"""AcademicYearConfigState — AY list, create, edit, lock master calendar."""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.academic_year import AcademicYearRepository
from durgam.services.academic_year import AcademicYearError, AcademicYearService
from durgam.services.org_exceptions import AcademicYearLockedError
from durgam.states.base import BaseState


def _svc(session) -> AcademicYearService:
    return AcademicYearService(ay_repo=AcademicYearRepository(session))


class AcademicYearConfigState(BaseState):
    # List
    academic_years: list[dict[str, str]] = []
    loading: bool = True

    # Form
    show_form: bool = False
    editing_id: str = ""
    form_code: str = ""
    form_starts_on: str = ""
    form_ends_on: str = ""

    # Confirmation dialogs
    confirm_open: bool = False
    confirm_ay_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""
    confirm_action: str = ""  # "lock_master" or "soft_delete"

    async def load_academic_years(self) -> None:
        guard = self._config_guard("academic_year", "configure")
        if guard is not None:
            return guard
        self.loading = True
        self.academic_years = []
        self.show_form = False
        with open_session() as session:
            for ay in _svc(session).list_all():
                self.academic_years.append({
                    "id": str(ay.id),
                    "code": ay.code,
                    "starts_on": str(ay.starts_on),
                    "ends_on": str(ay.ends_on),
                    "is_locked": "Yes" if ay.is_locked else "No",
                    "master_locked": "Yes" if ay.master_calendar_locked else "No",
                })
        self._load_nav_entries()
        self.loading = False

    def set_form_code(self, v: str) -> None:
        self.form_code = v

    def set_form_starts_on(self, v: str) -> None:
        self.form_starts_on = v

    def set_form_ends_on(self, v: str) -> None:
        self.form_ends_on = v

    def open_create(self):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ""
        self.form_code = ""
        self.form_starts_on = ""
        self.form_ends_on = ""
        self.show_form = True

    def open_edit(self, ay_id: str, code: str, starts_on: str, ends_on: str):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ay_id
        self.form_code = code
        self.form_starts_on = starts_on
        self.form_ends_on = ends_on
        self.show_form = True

    def cancel_form(self):
        self.show_form = False
        self.editing_id = ""
        self.form_code = ""
        self.form_starts_on = ""
        self.form_ends_on = ""
        self.flash = ""
        self.flash_type = "info"

    @require_role(action="configure", resource="academic_year")
    @audit_action(action="configure", resource="academic_year")
    async def save_academic_year(self, form_data: dict) -> None:
        from datetime import date

        code = form_data.get("form_code", "").strip()
        starts_on_raw = form_data.get("form_starts_on", "").strip()
        ends_on_raw = form_data.get("form_ends_on", "").strip()
        editing_id = form_data.get("editing_id", "").strip()

        if not starts_on_raw or not ends_on_raw:
            self.flash = "Start and end dates are required."
            self.flash_type = "error"
            return

        try:
            starts_on = date.fromisoformat(starts_on_raw)
            ends_on = date.fromisoformat(ends_on_raw)
        except ValueError:
            self.flash = "Invalid date format."
            self.flash_type = "error"
            return

        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                if not editing_id:
                    svc.create(code, starts_on, ends_on, actor_id)
                else:
                    svc.update(
                        UUID(editing_id),
                        {"starts_on": starts_on, "ends_on": ends_on},
                        actor_id,
                    )
                session.commit()
        except (AcademicYearError, AcademicYearLockedError) as e:
            self.flash = e.message if hasattr(e, "message") else str(e)
            self.flash_type = "error"
            self.show_form = False
            self.editing_id = ""
            return
        self.show_form = False
        self.editing_id = ""
        await self.load_academic_years()
        self.flash = "Academic year saved."
        self.flash_type = "success"

    def open_lock_master_confirm(self, ay_id: str, code: str) -> None:
        self.confirm_ay_id = ay_id
        self.confirm_action = "lock_master"
        self.confirm_title = f"Lock master calendar for '{code}'?"
        self.confirm_body = (
            "Once locked, the master calendar framework is finalized. "
            "IQAC, Directors, and other roles can then add their entries. "
            "This action cannot be undone."
        )
        self.confirm_open = True

    def open_soft_delete_confirm(self, ay_id: str, code: str) -> None:
        self.confirm_ay_id = ay_id
        self.confirm_action = "soft_delete"
        self.confirm_title = f"Deactivate academic year '{code}'?"
        self.confirm_body = (
            "This will deactivate the academic year. "
            "Existing data referencing it is preserved."
        )
        self.confirm_open = True

    @require_role(action="configure", resource="academic_year")
    @audit_action(action="configure", resource="academic_year")
    async def confirm_action_handler(self) -> None:
        action = self.confirm_action
        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                if action == "lock_master":
                    svc.lock_master_calendar(UUID(self.confirm_ay_id), actor_id)
                elif action == "soft_delete":
                    svc.update(
                        UUID(self.confirm_ay_id),
                        {"is_deleted": True},
                        actor_id,
                    )
                session.commit()
        except (AcademicYearError, AcademicYearLockedError) as e:
            self.flash = e.message if hasattr(e, "message") else str(e)
            self.flash_type = "error"
            self.confirm_open = False
            self.confirm_ay_id = ""
            self.confirm_action = ""
            return
        self.confirm_open = False
        self.confirm_ay_id = ""
        self.confirm_action = ""
        await self.load_academic_years()
        if action == "lock_master":
            self.flash = "Master calendar locked."
        else:
            self.flash = "Academic year deactivated."
        self.flash_type = "success"

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_ay_id = ""
        self.confirm_action = ""
