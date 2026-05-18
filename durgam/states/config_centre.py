"""CentreConfigState — centre list, create, edit (/admin/config/centres).

Campus selection uses codes (PSN/BRN/NDG/ATP) via rx.select (flat list[str]).
The campus UUID is resolved from code at save time via CampusRepository.get_by_code.
"""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.campus import CampusRepository
from durgam.repositories.centre import CentreRepository
from durgam.services.centre import CentreError, CentreService
from durgam.services.org_exceptions import HardDeleteBlockedError
from durgam.states.base import BaseState


def _svc(session) -> CentreService:
    return CentreService(centre_repo=CentreRepository(session))


class CentreConfigState(BaseState):
    centres: list[dict[str, str]] = []
    campus_codes: list[str] = []  # for rx.select — Reflex 0.9.2 accepts flat list[str]
    loading: bool = True

    show_form: bool = False
    editing_id: str = ""
    form_code: str = ""
    form_name: str = ""
    form_campus_code: str = ""

    confirm_open: bool = False
    confirm_centre_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    async def load_centres(self) -> None:
        guard = self._config_guard("centre", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.centres = []
        self.campus_codes = []
        self.show_form = False
        with open_session() as session:
            campus_repo = CampusRepository(session)
            campuses = campus_repo.list_active()
            self.campus_codes = [c.code for c in campuses]
            campus_by_id = {str(c.id): c for c in campuses}
            for c in _svc(session).list():
                campus = campus_by_id.get(str(c.campus_id))
                self.centres.append({
                    "id": str(c.id),
                    "code": c.code,
                    "name": c.name,
                    "campus": campus.code if campus else "",
                    "campus_code": campus.code if campus else "",
                })
        self._load_nav_entries()
        self.loading = False

    def set_form_code(self, value: str) -> None:
        self.form_code = value

    def set_form_name(self, value: str) -> None:
        self.form_name = value

    def set_form_campus_code(self, value: str) -> None:
        self.form_campus_code = value

    def open_create(self) -> None:
        self.editing_id = ""
        self.form_code = ""
        self.form_name = ""
        self.form_campus_code = self.campus_codes[0] if self.campus_codes else ""
        self.show_form = True

    def open_edit(self, centre_id: str, code: str, name: str, campus_code: str) -> None:
        self.editing_id = centre_id
        self.form_code = code
        self.form_name = name
        self.form_campus_code = campus_code
        self.show_form = True

    def cancel_form(self) -> None:
        self.show_form = False
        self.editing_id = ""
        self.form_code = ""
        self.form_name = ""
        self.form_campus_code = ""

    @require_role(action="write", resource="centre")
    @audit_action(action="write", resource="centre")
    async def save_centre(self, form_data: dict) -> None:
        code = form_data.get("form_code", "").strip()
        name = form_data.get("form_name", "").strip()
        # rx.select value comes via state var; form_data may not include it.
        # Use self.form_campus_code (updated by set_form_campus_code on_change).
        campus_code = self.form_campus_code.strip()
        editing_id = form_data.get("editing_id", "").strip()
        try:
            with open_session() as session:
                campus_repo = CampusRepository(session)
                campus = campus_repo.get_by_code(campus_code)
                if campus is None:
                    self.flash = f"Campus '{campus_code}' not found."
                    self.flash_type = "error"
                    return
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                if not editing_id:
                    svc.create(code, name, campus.id, actor_id)
                else:
                    svc.update(
                        UUID(editing_id),
                        {"name": name, "campus_id": campus.id},
                        actor_id,
                    )
                session.commit()  # open_session() does NOT auto-commit
            self.flash = "Centre saved."
            self.flash_type = "success"
        except CentreError as e:
            self.flash = e.message
            self.flash_type = "error"
        self.show_form = False
        await self.load_centres()

    def open_soft_delete_confirm(self, centre_id: str, name: str) -> None:
        self.confirm_centre_id = centre_id
        self.confirm_title = f"Deactivate '{name}'?"
        self.confirm_body = "This will deactivate the centre."
        self.confirm_open = True

    @require_role(action="delete", resource="centre")
    @audit_action(action="delete", resource="centre")
    async def soft_delete_centre(self) -> None:
        try:
            with open_session() as session:
                _svc(session).soft_delete(
                    UUID(self.confirm_centre_id), UUID(self.current_user_id)
                )
                session.commit()  # open_session() does NOT auto-commit
            self.flash = "Centre deactivated."
            self.flash_type = "success"
        except (CentreError, HardDeleteBlockedError) as e:
            self.flash = e.message
            self.flash_type = "error"
        self.confirm_open = False
        await self.load_centres()

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_centre_id = ""
