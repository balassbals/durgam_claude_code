"""CentreConfigState — centre list, create, edit (/admin/config/centres)."""

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
    campus_options: list[dict[str, str]] = []  # for the campus dropdown

    show_form: bool = False
    editing_id: str = ""
    form_code: str = ""
    form_name: str = ""
    form_campus_id: str = ""

    confirm_open: bool = False
    confirm_centre_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    async def load_centres(self) -> None:
        guard = self._config_guard("centre")
        if guard is not None:
            return guard
        self.centres = []
        self.campus_options = []
        self.show_form = False
        with open_session() as session:
            campus_repo = CampusRepository(session)
            for camp in campus_repo.list_active():
                self.campus_options.append({"id": str(camp.id), "code": camp.code, "name": camp.name})
            for c in _svc(session).list():
                # Resolve campus code for display
                campus = campus_repo.get_by_id(c.campus_id)
                self.centres.append({
                    "id": str(c.id),
                    "code": c.code,
                    "name": c.name,
                    "campus": campus.code if campus else str(c.campus_id),
                    "campus_id": str(c.campus_id),
                })
        self._load_nav_entries()

    def open_create(self) -> None:
        self.editing_id = ""
        self.form_code = ""
        self.form_name = ""
        self.form_campus_id = self.campus_options[0]["id"] if self.campus_options else ""
        self.show_form = True

    def open_edit(self, centre_id: str, code: str, name: str, campus_id: str) -> None:
        self.editing_id = centre_id
        self.form_code = code
        self.form_name = name
        self.form_campus_id = campus_id
        self.show_form = True

    def cancel_form(self) -> None:
        self.show_form = False
        self.editing_id = ""
        self.form_code = ""
        self.form_name = ""
        self.form_campus_id = ""

    @require_role(action="write", resource="centre")
    @audit_action(action="write", resource="centre")
    async def save_centre(self) -> None:
        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                campus_id = UUID(self.form_campus_id)
                if not self.editing_id:
                    svc.create(self.form_code, self.form_name, campus_id, actor_id)
                else:
                    svc.update(
                        UUID(self.editing_id),
                        {"name": self.form_name, "campus_id": campus_id},
                        actor_id,
                    )
            self.flash = "Centre saved."
            self.flash_type = "success"
        except (CentreError, ValueError) as e:
            self.flash = str(e)
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
