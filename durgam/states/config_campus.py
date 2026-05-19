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
    loading: bool = True

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
        # campus:write:* gates this page — SYSTEM_ADMIN only (Refinement viii).
        guard = self._config_guard("campus", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.campuses = []  # reset before query (page-on-load data refresh rule)
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
        self.loading = False

    # Explicit setters — Reflex 0.9.2 does not auto-generate set_* for
    # sub-state classes; on_change handlers require explicit methods.
    def set_form_code(self, value: str) -> None:
        self.form_code = value

    def set_form_name(self, value: str) -> None:
        self.form_name = value

    def set_form_address(self, value: str) -> None:
        self.form_address = value

    def open_create(self):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ""
        self.form_code = ""
        self.form_name = ""
        self.form_address = ""
        self.show_form = True
        return rx.scroll_to("campus-page-top")

    def open_edit(self, campus_id: str, code: str, name: str, address: str):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = campus_id
        self.form_code = code
        self.form_name = name
        self.form_address = address
        self.show_form = True
        return rx.scroll_to("campus-page-top")

    def cancel_form(self):
        self.show_form = False
        self.editing_id = ""
        self.form_code = ""
        self.form_name = ""
        self.form_address = ""
        return rx.scroll_to("campus-page-top")

    @require_role(action="write", resource="campus")
    @audit_action(action="write", resource="campus")
    async def save_campus(self, form_data: dict) -> None:
        """Receives form_data from rx.form on_submit — authoritative values."""
        code = form_data.get("form_code", "").strip()
        name = form_data.get("form_name", "").strip()
        address = form_data.get("form_address", "").strip()
        editing_id = form_data.get("editing_id", "").strip()
        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                if not editing_id:
                    svc.create(code, name, actor_id, address=address or None)
                else:
                    svc.update(
                        UUID(editing_id),
                        {"name": name, "address": address or None},
                        actor_id,
                    )
                session.commit()  # open_session() does NOT auto-commit
            self.flash = "Campus saved."
            self.flash_type = "success"
        except CampusError as e:
            self.flash = e.message
            self.flash_type = "error"
        self.show_form = False
        self.editing_id = ""
        await self.load_campuses()
        return rx.scroll_to("campus-page-top")

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
                session.commit()  # open_session() does NOT auto-commit
            self.flash = "Campus deactivated."
            self.flash_type = "success"
        except (CampusError, HardDeleteBlockedError) as e:
            self.flash = e.message
            self.flash_type = "error"
        self.confirm_open = False
        self.confirm_campus_id = ""
        await self.load_campuses()
        return rx.scroll_to("campus-page-top")

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_campus_id = ""
