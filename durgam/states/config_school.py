"""SchoolConfigState — school list, create, edit, soft-delete (/admin/config/schools)."""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.school import SchoolRepository
from durgam.services.org_exceptions import HardDeleteBlockedError
from durgam.services.school import SchoolError, SchoolService
from durgam.states.base import BaseState


def _svc(session) -> SchoolService:
    return SchoolService(school_repo=SchoolRepository(session))


class SchoolConfigState(BaseState):
    schools: list[dict[str, str]] = []
    loading: bool = True

    show_form: bool = False
    editing_id: str = ""
    form_code: str = ""
    form_name: str = ""
    form_dean_role_code: str = ""

    confirm_open: bool = False
    confirm_school_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    async def load_schools(self) -> None:
        guard = self._config_guard("school", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.schools = []
        self.show_form = False
        with open_session() as session:
            for s in _svc(session).list():
                self.schools.append({
                    "id": str(s.id),
                    "code": s.code,
                    "name": s.name,
                    "dean_role_code": s.dean_role_code,
                })
        self._load_nav_entries()
        self.loading = False

    def set_form_code(self, value: str) -> None:
        self.form_code = value

    def set_form_name(self, value: str) -> None:
        self.form_name = value

    def set_form_dean_role_code(self, value: str) -> None:
        self.form_dean_role_code = value

    def open_create(self) -> None:
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ""
        self.form_code = ""
        self.form_name = ""
        self.form_dean_role_code = ""
        self.show_form = True

    def open_edit(self, school_id: str, code: str, name: str, dean_role_code: str) -> None:
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = school_id
        self.form_code = code
        self.form_name = name
        self.form_dean_role_code = dean_role_code
        self.show_form = True

    def cancel_form(self) -> None:
        self.show_form = False
        self.editing_id = ""
        self.form_code = ""
        self.form_name = ""
        self.form_dean_role_code = ""

    @require_role(action="write", resource="school")
    @audit_action(action="write", resource="school")
    async def save_school(self, form_data: dict) -> None:
        code = form_data.get("form_code", "").strip()
        name = form_data.get("form_name", "").strip()
        dean_role_code = form_data.get("form_dean_role_code", "").strip()
        editing_id = form_data.get("editing_id", "").strip()
        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                if not editing_id:
                    svc.create(code, name, dean_role_code, actor_id)
                else:
                    svc.update(
                        UUID(editing_id),
                        {"name": name, "dean_role_code": dean_role_code},
                        actor_id,
                    )
                session.commit()  # open_session() does NOT auto-commit
            self.flash = "School saved."
            self.flash_type = "success"
        except SchoolError as e:
            self.flash = e.message
            self.flash_type = "error"
        self.show_form = False
        await self.load_schools()

    def open_soft_delete_confirm(self, school_id: str, name: str) -> None:
        self.confirm_school_id = school_id
        self.confirm_title = f"Deactivate '{name}'?"
        self.confirm_body = "This will deactivate the school."
        self.confirm_open = True

    @require_role(action="delete", resource="school")
    @audit_action(action="delete", resource="school")
    async def soft_delete_school(self) -> None:
        try:
            with open_session() as session:
                _svc(session).soft_delete(
                    UUID(self.confirm_school_id), UUID(self.current_user_id)
                )
                session.commit()  # open_session() does NOT auto-commit
            self.flash = "School deactivated."
            self.flash_type = "success"
        except (SchoolError, HardDeleteBlockedError) as e:
            self.flash = e.message
            self.flash_type = "error"
        self.confirm_open = False
        self.confirm_school_id = ""
        await self.load_schools()

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_school_id = ""
