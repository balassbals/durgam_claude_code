"""AdminUsersState — admin user CRUD, password reset, role assignment."""

from __future__ import annotations

import asyncio
from uuid import UUID

import reflex as rx

from durgam.auth.decorators import audit_action, require_role
from durgam.db import open_session
from durgam.notifications.admin_emails import (
    send_user_created_email,
    send_user_deleted_email,
    send_user_password_reset_email,
)
from durgam.repositories.role import RoleRepository
from durgam.repositories.user import UserRepository
from durgam.repositories.user_role import UserRoleRepository
from durgam.services.user_admin import HardDeleteBlockedError, UserAdminError, UserAdminService
from durgam.states.base import BaseState


def _svc(session) -> UserAdminService:
    return UserAdminService(
        user_repo=UserRepository(session),
        user_role_repo=UserRoleRepository(session),
    )


class AdminUsersState(BaseState):
    # List view — all values stored as strings for Reflex foreach compatibility.
    users: list[dict[str, str]] = []
    total_users: int = 0
    search_query: str = ""
    current_page: int = 1
    page_size: int = 25

    # Form fields (create / edit)
    form_username: str = ""
    form_email: str = ""
    form_role_ids: list[str] = []
    form_is_active: bool = True

    # One-time display of generated password
    generated_password: str = ""

    # Confirmation dialog state
    confirm_action: str = ""   # "soft_delete" | "hard_delete" | "reset_password"
    confirm_user_id: str = ""
    confirm_title: str = ""
    confirm_body: str = ""
    confirm_open: bool = False

    # Available roles for the role picker
    available_roles: list[dict[str, str]] = []

    @require_role(action="read", resource="user")
    @audit_action(action="search", resource="user")
    async def search_users(self, form_data: dict) -> None:
        """Search handler called from the search form on_submit."""
        self.search_query = form_data.get("search", "").strip()
        self.current_page = 1
        await self.load_users()

    async def load_users(self) -> None:
        """on_load for /admin/users — guards session then loads user list.

        Page-on-load data refresh rule (CLAUDE.md "Patterns established at M2"):
        every list page re-queries on every on_load, not only on first mount.
        self.users is reset to [] first so stale state never lingers between
        navigations within the same WebSocket session.
        """
        guard = self._admin_guard()
        if guard is not None:
            return guard
        self.users = []  # reset before query so stale rows never linger
        self.total_users = 0
        with open_session() as session:
            svc = _svc(session)
            page_users, total = svc.list_users(
                search=self.search_query or None,
                page=self.current_page,
                page_size=self.page_size,
            )
            # Read all attributes before session closes.
            # All values are strings for Reflex foreach (list[dict[str, str]]).
            self.users = [
                {
                    "id": str(u.id),
                    "username": u.username,
                    "email": u.email,
                    "is_active": str(u.is_active),
                    "must_change_password": str(u.must_change_password),
                    "last_login_at": str(u.last_login_at) if u.last_login_at else "",
                }
                for u in page_users
            ]
            self.total_users = total
        self._load_nav_entries()

    @require_role(action="write", resource="user")
    @audit_action(action="create", resource="user")
    async def create_user(self, form_data: dict) -> None:
        """Non-trivial handler: form validation, service call, temp-password display."""
        self.flash = ""
        self.generated_password = ""
        username = form_data.get("username", "").strip()
        email = form_data.get("email", "").strip()

        if not username or not email:
            self.flash = "Username and email are required."
            return

        try:
            role_ids = [UUID(r) for r in self.form_role_ids] if self.form_role_ids else []
            with open_session() as session:
                svc = _svc(session)
                user, temp_pw = svc.create_user(username, email, UUID(self.current_user_id),
                                                 role_ids=role_ids or None)
                user_id = str(user.id)
                user_email = user.email
                session.commit()

            self.generated_password = temp_pw
            self.flash = f"User '{username}' created. Temporary password shown below."
            asyncio.create_task(
                send_user_created_email(
                    type("U", (), {"id": user_id, "email": user_email, "username": username})(),
                    temp_pw,
                )
            )
            await self.load_users()
            return rx.redirect("/admin/users")  # type: ignore[return-value]
        except UserAdminError as exc:
            self.flash = exc.message

    @require_role(action="delete", resource="user")
    @audit_action(action="soft_delete", resource="user")
    async def soft_delete_user(self) -> None:
        user_id = self.confirm_user_id
        self.confirm_open = False
        if not user_id:
            return
        try:
            with open_session() as session:
                svc = _svc(session)
                user = svc.get_user(UUID(user_id))
                username = user.username if user else "unknown"
                email = user.email if user else ""
                svc.soft_delete_user(UUID(user_id), UUID(self.current_user_id))
                session.commit()
            self.flash = f"User '{username}' deactivated."
            if email:
                asyncio.create_task(
                    send_user_deleted_email(
                        type("U", (), {"id": user_id, "email": email, "username": username})(),
                    )
                )
            await self.load_users()
        except UserAdminError as exc:
            self.flash = exc.message

    @require_role(action="delete", resource="user")
    @audit_action(action="hard_delete", resource="user")
    async def hard_delete_user(self) -> None:
        user_id = self.confirm_user_id
        self.confirm_open = False
        if not user_id:
            return
        try:
            with open_session() as session:
                svc = _svc(session)
                svc.hard_delete_user(UUID(user_id), UUID(self.current_user_id))
                session.commit()
            self.flash = "User permanently deleted."
            await self.load_users()
        except HardDeleteBlockedError as exc:
            self.flash = exc.message
        except UserAdminError as exc:
            self.flash = exc.message

    @require_role(action="write", resource="user")
    @audit_action(action="reset_password", resource="user")
    async def reset_user_password(self) -> None:
        """Non-trivial handler: generates temp password, emails user, displays once."""
        user_id = self.confirm_user_id
        self.confirm_open = False
        self.generated_password = ""
        if not user_id:
            return
        try:
            with open_session() as session:
                svc = _svc(session)
                user, temp_pw = svc.reset_user_password(
                    UUID(user_id), UUID(self.current_user_id)
                )
                username = user.username
                email = user.email
                session.commit()

            self.generated_password = temp_pw
            self.flash = f"Password reset for '{username}'. New temporary password shown below."
            asyncio.create_task(
                send_user_password_reset_email(
                    type("U", (), {"id": user_id, "email": email, "username": username})(),
                    temp_pw,
                )
            )
        except UserAdminError as exc:
            self.flash = exc.message

    def open_soft_delete_confirm(self, user_id: str, username: str) -> None:
        self.confirm_user_id = user_id
        self.confirm_action = "soft_delete"
        self.confirm_title = f"Deactivate user '{username}'?"
        self.confirm_body = "This will deactivate the account. The user can no longer log in."
        self.confirm_open = True

    def open_hard_delete_confirm(self, user_id: str, username: str) -> None:
        self.confirm_user_id = user_id
        self.confirm_action = "hard_delete"
        self.confirm_title = f"Permanently delete '{username}'?"
        self.confirm_body = (
            "This will permanently delete the user. This action cannot be undone. "
            "If the user has audit history, the deletion will be blocked."
        )
        self.confirm_open = True

    def open_reset_password_confirm(self, user_id: str, username: str) -> None:
        self.confirm_user_id = user_id
        self.confirm_action = "reset_password"
        self.confirm_title = f"Reset password for '{username}'?"
        self.confirm_body = (
            "A new temporary password will be generated and emailed to the user. "
            "They must change it on next login."
        )
        self.confirm_open = True

    def cancel_confirm(self) -> None:
        self.confirm_open = False
        self.confirm_user_id = ""

    def dismiss_generated_password(self) -> None:
        self.generated_password = ""

    async def load_available_roles(self) -> None:
        """on_load for /admin/users/new — guards session then loads roles."""
        guard = self._admin_guard()
        if guard is not None:
            return guard
        with open_session() as session:
            roles = RoleRepository(session).list_active()
            self.available_roles = [
                {"id": str(r.id), "code": r.code, "name": r.name}
                for r in roles
            ]
