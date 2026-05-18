"""CampusConfigState — campus list, create, edit, soft-delete (/admin/config/campuses)."""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.campus import CampusRepository
from durgam.services.campus import CampusError, CampusService
from durgam.services.org_exceptions import HardDeleteBlockedError
from durgam.states.base import BaseState


def _svc(session) -> CampusService:
    return CampusService(campus_repo=CampusRepository(session))


class CampusConfigState(BaseState):
    # List
    campuses: list[dict[str, str]] = []

    # Inline form (shared for create and edit)
    show_form: bool = False
    editing_id: str = ""   # empty = create mode
    form_code: str = ""
    form_name: str = ""
    form_address: str = ""

    # Confirmation dialog
    confirm_open: bool = False
    confirm_campus_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    async def load_campuses(self) -> None:
        guard = self._config_guard("campus")
        if guard is not None:
            return guard
        self.campuses = []  # reset before query
        self.show_form = False
        with open_session() as session:
            for c in _svc(session).list():
                self.campuses.append({
                    "id": str(c.id),
                    "code": c.code,
                    "name": c.name,
                    "address": c.address or "",
                })
        self._load_nav_entries()

    def open_create(self) -> None:
        self.editing_id = ""
        self.form_code = ""
        self.form_name = ""
        self.form_address = ""
        self.show_form = True

    def open_edit(self, campus_id: str, code: str, name: str, address: str) -> None:
        self.editing_id = campus_id
        self.form_code = code
        self.form_name = name
        self.form_address = address
        self.show_form = True

    def cancel_form(self) -> None:
        self.show_form = False
        self.editing_id = ""
        self.form_code = ""
        self.form_name = ""
        self.form_address = ""

    @require_role(action="write", resource="campus")
    @audit_action(action="write", resource="campus")
    async def save_campus(self) -> None:
        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                if not self.editing_id:
                    svc.create(
                        self.form_code,
                        self.form_name,
                        actor_id,
                        address=self.form_address.strip() or None,
                    )
                else:
                    svc.update(
                        UUID(self.editing_id),
                        {"name": self.form_name, "address": self.form_address.strip() or None},
                        actor_id,
                    )
            self.flash = "Campus saved."
            self.flash_type = "success"
        except CampusError as e:
            self.flash = e.message
            self.flash_type = "error"
        self.show_form = False
        self.editing_id = ""
        await self.load_campuses()

    def open_soft_delete_confirm(self, campus_id: str, name: str) -> None:
        self.confirm_campus_id = campus_id
        self.confirm_title = f"Deactivate '{name}'?"
        self.confirm_body = (
            "This will deactivate the campus. Existing data referencing it is preserved."
        )
        self.confirm_open = True

    @require_role(action="delete", resource="campus")
    @audit_action(action="delete", resource="campus")
    async def soft_delete_campus(self) -> None:
        try:
            with open_session() as session:
                _svc(session).soft_delete(
                    UUID(self.confirm_campus_id), UUID(self.current_user_id)
                )
            self.flash = "Campus deactivated."
            self.flash_type = "success"
        except (CampusError, HardDeleteBlockedError) as e:
            self.flash = e.message
            self.flash_type = "error"
        self.confirm_open = False
        self.confirm_campus_id = ""
        await self.load_campuses()

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_campus_id = ""
