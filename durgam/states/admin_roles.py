"""AdminRolesState — role CRUD and permission assignment."""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.repositories.permission import PermissionRepository
from durgam.repositories.role import RoleRepository
from durgam.services.role_admin import RoleAdminError, RoleAdminService
from durgam.states.base import BaseState


def _svc(session) -> RoleAdminService:
    return RoleAdminService(
        role_repo=RoleRepository(session),
        permission_repo=PermissionRepository(session),
    )


class AdminRolesState(BaseState):
    roles: list[dict[str, str]] = []

    # For the role detail / permission accordion
    current_role_id_str: str = ""
    current_role_code: str = ""  # overrides BaseState.current_role_code (shadow)
    current_role_name: str = ""
    current_role_level: int = 0
    current_role_description: str = ""

    # Flat list for rx.foreach — headers and perm rows interleaved.
    # Keys: type, resource, badge, action, scope, id (no "granted" — use role_perm_ids_checked).
    perm_table: list[dict[str, str]] = []
    perm_granted_count: int = 0
    perm_total_count: int = 0

    # Controlled checkbox state — IDs of permissions currently checked in the UI.
    # Initialized from the role's actual permissions on load; updated on toggle.
    # Source of truth for both the checkboxes and the save handler.
    role_perm_ids_checked: list[str] = []

    # Delete confirmation
    confirm_open: bool = False
    confirm_role_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""

    async def load_roles(self) -> None:
        """on_load for /admin/roles and /admin/roles/new — guards session."""
        guard = self._admin_guard()
        if guard is not None:
            return guard
        self.roles = []  # reset before query
        with open_session() as session:
            svc = _svc(session)
            role_list = svc.list_roles()
            result = []
            for r in role_list:
                perms = svc.get_role_permissions(r.id)
                result.append({
                    "id": str(r.id),
                    "code": r.code,
                    "name": r.name,
                    "level": str(r.level),
                    "permission_count": str(len(perms)),
                })
            self.roles = result
        self._load_nav_entries()

    @require_role(action="write", resource="role")
    @audit_action(action="create", resource="role")
    async def create_role(self, form_data: dict) -> None:
        self.flash = ""
        code = form_data.get("code", "").strip()
        name = form_data.get("name", "").strip()
        level_str = form_data.get("level", "0").strip()
        description = form_data.get("description", "").strip() or None
        try:
            level = int(level_str)
        except ValueError:
            self.flash = "Level must be a whole number."
            return
        try:
            with open_session() as session:
                svc = _svc(session)
                role = svc.create_role(code, name, level, description,
                                       UUID(self.current_user_id))
                role_id = str(role.id)
                session.commit()
            self.flash = f"Role '{code}' created."
            return rx.redirect(f"/admin/roles/{role_id}")  # type: ignore[return-value]
        except RoleAdminError as exc:
            self.flash = exc.message

    def toggle_perm(self, perm_id: str, checked: bool) -> None:
        """Toggle a single permission checkbox. Called by on_change on each checkbox."""
        if checked:
            if perm_id not in self.role_perm_ids_checked:
                self.role_perm_ids_checked = self.role_perm_ids_checked + [perm_id]
        else:
            self.role_perm_ids_checked = [p for p in self.role_perm_ids_checked
                                           if p != perm_id]

    @require_role(action="write", resource="role")
    @audit_action(action="update_permissions", resource="role")
    async def save_role_permissions(self) -> None:
        """Save the permission accordion — reads from role_perm_ids_checked (Bug H fix).

        Switched from form_data (unreliable with default_checked uncontrolled checkboxes)
        to a controlled state var. role_perm_ids_checked is the single source of truth.
        """
        self.flash = ""
        if not self.current_role_id_str:
            return
        perm_ids = [UUID(p) for p in self.role_perm_ids_checked]
        try:
            with open_session() as session:
                svc = _svc(session)
                svc.update_permissions(UUID(self.current_role_id_str), perm_ids,
                                       UUID(self.current_user_id))
                session.commit()
            self.flash = "Permissions updated."
        except RoleAdminError as exc:
            self.flash = exc.message

    @require_role(action="delete", resource="role")
    @audit_action(action="soft_delete", resource="role")
    async def soft_delete_role(self) -> None:
        role_id = self.confirm_role_id
        self.confirm_open = False
        if not role_id:
            return
        try:
            with open_session() as session:
                svc = _svc(session)
                svc.soft_delete_role(UUID(role_id), UUID(self.current_user_id))
                session.commit()
            self.flash = "Role deleted."
            await self.load_roles()
            return rx.redirect("/admin/roles")  # type: ignore[return-value]
        except RoleAdminError as exc:
            self.flash = exc.message

    async def load_role_detail(self) -> None:
        """on_load for /admin/roles/{role_id} — guards session then loads detail."""
        guard = self._admin_guard()
        if guard is not None:
            return guard
        role_id_str = self.router.page.params.get("role_id", "")
        if not role_id_str:
            return rx.redirect("/admin/roles")  # type: ignore[return-value]
        self.current_role_id_str = role_id_str
        with open_session() as session:
            svc = _svc(session)
            role = svc.get_role(UUID(role_id_str))
            if role is None:
                return rx.redirect("/admin/roles")  # type: ignore[return-value]
            self.current_role_code = role.code
            self.current_role_name = role.name
            self.current_role_level = role.level
            self.current_role_description = role.description or ""

            role_perm_ids = {str(p.id) for p in svc.get_role_permissions(role.id)}
            # role_perm_ids_checked is the SINGLE source of truth for checked state.
            # Both checkboxes and count badges read from it (count badge recomputed).
            self.role_perm_ids_checked = list(role_perm_ids)

            all_grouped = svc.get_permissions_grouped()
            table: list[dict[str, str]] = []
            total_granted = len(role_perm_ids)
            total_count = 0
            for resource in sorted(all_grouped.keys()):
                perms = sorted(all_grouped[resource], key=lambda p: (p.action, p.scope))
                n_granted = sum(1 for p in perms if str(p.id) in role_perm_ids)
                total_count += len(perms)
                table.append({
                    "type": "header",
                    "resource": resource,
                    "badge": f"{n_granted}/{len(perms)}",
                    "action": "", "scope": "", "id": "",
                })
                for p in perms:
                    # "granted" removed from perm rows — checkboxes use
                    # role_perm_ids_checked.contains(item["id"]) instead.
                    table.append({
                        "type": "perm",
                        "resource": resource,
                        "badge": "",
                        "action": p.action,
                        "scope": p.scope,
                        "id": str(p.id),
                    })
            self.perm_table = table
            self.perm_granted_count = total_granted
            self.perm_total_count = total_count
        self._load_nav_entries()

    def open_delete_confirm(self, role_id: str, role_name: str) -> None:
        self.confirm_role_id = role_id
        self.confirm_title = f"Delete role '{role_name}'?"
        self.confirm_body = (
            "This will remove the role. Users assigned this role will lose its permissions."
        )
        self.confirm_open = True

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_role_id = ""
