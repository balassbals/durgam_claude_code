"""RoleEmailConfigState — role-email list, create, edit, deactivate (/admin/config/role-emails)."""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from sqlalchemy.exc import IntegrityError

from durgam.audit.snapshot import audit_snapshot
from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.permission import PermissionRepository
from durgam.repositories.role import RoleRepository
from durgam.repositories.role_email import RoleEmailRepository
from durgam.scopes.registry import get_scope_type_dropdown_options, load_scope_objects
from durgam.services.role_admin import RoleAdminService
from durgam.services.role_email import RoleEmailError, RoleEmailService
from durgam.states.base import BaseState


def _svc(session) -> RoleEmailService:
    return RoleEmailService(repo=RoleEmailRepository(session))


class RoleEmailConfigState(BaseState):
    role_emails: list[dict[str, str]] = []
    loading: bool = True

    show_form: bool = False
    editing_id: str = ""
    form_role_code: str = ""
    form_email: str = ""
    form_scope_type: str = ""
    form_scope_type_ui: str = "global"
    form_scope_id: str = ""

    roles_dropdown: list[dict] = []
    scope_objects_dropdown: list[dict] = []

    confirm_open: bool = False
    confirm_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    def _load_dropdowns(self) -> None:
        with open_session() as session:
            self.roles_dropdown = [
                {"id": r.code, "label": f"{r.code} — {r.name}"}
                for r in RoleAdminService(
                    RoleRepository(session), PermissionRepository(session),
                ).list_roles()
            ]

    def _load_scope_objects(self) -> None:
        if not self.form_scope_type or self.form_scope_type == "":
            self.scope_objects_dropdown = []
            return
        with open_session() as session:
            self.scope_objects_dropdown = load_scope_objects(
                self.form_scope_type, session,
            )

    async def load_role_emails(self) -> None:
        guard = self._config_guard("role_email", "write")
        if guard is not None:
            return guard
        self.loading = True
        self.role_emails = []
        self.show_form = False
        with open_session() as session:
            from durgam.scopes.registry import resolve_scope_label
            for r in _svc(session).list_all():
                scope_label = "Global"
                if r.scope_type and r.scope_id:
                    scope_label = resolve_scope_label(
                        r.scope_type, str(r.scope_id), session,
                    )
                self.role_emails.append({
                    "id": str(r.id),
                    "role_code": r.role_code,
                    "email": r.email,
                    "scope": scope_label,
                    "scope_type": r.scope_type or "",
                    "scope_id": str(r.scope_id) if r.scope_id else "",
                })
        self._load_dropdowns()
        self._load_nav_entries()
        self.loading = False

    def set_form_role_code(self, value: str) -> None:
        self.form_role_code = value

    def set_form_email(self, value: str) -> None:
        self.form_email = value

    def set_form_scope_type_ui(self, value: str) -> None:
        real = "" if value == "global" else value
        self.form_scope_type_ui = value
        self.form_scope_type = real
        self.form_scope_id = ""
        self._load_scope_objects()

    def set_form_scope_id(self, value: str) -> None:
        self.form_scope_id = value

    def open_create(self):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = ""
        self.form_role_code = ""
        self.form_email = ""
        self.form_scope_type = ""
        self.form_scope_type_ui = "global"
        self.form_scope_id = ""
        self.scope_objects_dropdown = []
        self.show_form = True

    def open_edit(
        self,
        record_id: str,
        role_code: str,
        email: str,
        scope_type: str,
        scope_id: str,
    ):
        self.flash = ""
        self.flash_type = "info"
        self.editing_id = record_id
        self.form_role_code = role_code
        self.form_email = email
        self.form_scope_type = scope_type
        self.form_scope_type_ui = scope_type if scope_type else "global"
        self.form_scope_id = scope_id
        if scope_type:
            self._load_scope_objects()
        else:
            self.scope_objects_dropdown = []
        self.show_form = True

    def cancel_form(self):
        self.show_form = False
        self.editing_id = ""
        self.flash = ""
        self.flash_type = "info"

    @require_role(action="write", resource="role_email")
    @audit_action(action="write", resource="role_email")
    async def save_role_email(self, form_data: dict) -> None:
        role_code = form_data.get("form_role_code", "").strip()
        email = form_data.get("form_email", "").strip()
        scope_type = form_data.get("form_scope_type", "").strip() or None
        scope_id_str = form_data.get("form_scope_id", "").strip()
        scope_id = UUID(scope_id_str) if scope_id_str else None
        editing_id = form_data.get("editing_id", "").strip()
        try:
            with open_session() as session:
                svc = _svc(session)
                actor_id = UUID(self.current_user_id)
                if not editing_id:
                    entity = svc.create(
                        role_code, email, actor_id,
                        scope_type=scope_type, scope_id=scope_id,
                    )
                    after_snap = audit_snapshot(entity)
                    session.commit()
                    self._set_audit(resource_id=str(entity.id), after=after_snap)
                else:
                    repo = RoleEmailRepository(session)
                    before_snap = audit_snapshot(repo.get_by_id(UUID(editing_id)))
                    entity = svc.update(
                        UUID(editing_id),
                        {"role_code": role_code, "email": email,
                         "scope_type": scope_type, "scope_id": scope_id},
                        actor_id,
                    )
                    after_snap = audit_snapshot(entity)
                    session.commit()
                    self._set_audit(resource_id=str(entity.id), before=before_snap, after=after_snap)
            self.show_form = False
            self.editing_id = ""
            await self.load_role_emails()
            self.flash = "Role email saved."
            self.flash_type = "success"
        except RoleEmailError as e:
            self.flash = e.message
            self.flash_type = "error"
        except IntegrityError:
            self.flash = (
                "A role email for this role and scope already exists. "
                "Edit the existing entry instead."
            )
            self.flash_type = "error"

    def open_deactivate_confirm(self, record_id: str, role_code: str) -> None:
        self.confirm_id = record_id
        self.confirm_title = f"Deactivate email for '{role_code}'?"
        self.confirm_body = "This will deactivate the role email. It can be re-created later."
        self.confirm_open = True

    @require_role(action="delete", resource="role_email")
    @audit_action(action="delete", resource="role_email")
    async def soft_delete_role_email(self) -> None:
        try:
            with open_session() as session:
                repo = RoleEmailRepository(session)
                entity = repo.get_by_id(UUID(self.confirm_id))
                before_snap = audit_snapshot(entity)
                _svc(session).soft_delete(
                    UUID(self.confirm_id), UUID(self.current_user_id)
                )
                session.commit()
                self._set_audit(resource_id=str(entity.id), before=before_snap)
            self.confirm_open = False
            self.confirm_id = ""
            await self.load_role_emails()
            self.flash = "Role email deactivated."
            self.flash_type = "success"
        except RoleEmailError as e:
            self.flash = e.message
            self.flash_type = "error"
            self.confirm_open = False
            self.confirm_id = ""

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_id = ""
