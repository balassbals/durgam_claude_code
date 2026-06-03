from typing import Any
from uuid import UUID

import reflex as rx

from durgam.auth.permissions import can
from durgam.db import open_session
from durgam.nav.registry import get_visible_entries


class BaseState(rx.State):
    """Shared state inherited by all page states."""

    # Audit context — backend vars (prefixed _), not sent to frontend.
    _audit_pending: dict[str, Any] | None = None
    _current_user_roles: list[dict[str, str | None]] = []

    # Opaque session token stored in the browser cookie (SD-001).
    # rx.Cookie is JS-set; see docs/security_decisions.md for HttpOnly gap analysis.
    session_token: str = rx.Cookie(
        name="dsession",
        same_site="lax",
        secure=True,
        max_age=7 * 24 * 3600,
        path="/",
    )

    # Populated by AuthState.resolve_session() on each page load.
    current_user_id: str = ""
    current_username: str = ""
    current_role_code: str = ""

    flash: str = ""
    flash_type: str = "info"  # "success" | "error" | "warning" | "info"

    # Request metadata populated by auth middleware / Reflex router data.
    client_ip: str = ""
    client_user_agent: str = ""
    request_id: str = ""

    # Nav entries visible to the current user (cached at login; re-populated on load).
    # Each entry is {"label": str, "href": str, "icon": str, "group": str}.
    visible_nav_entries: list[dict[str, str]] = []

    # Carries a success message across a single redirect. Set before rx.redirect();
    # picked up by the destination page's on_load which moves it into self.flash.
    pending_success: str = ""

    # True only after _admin_guard() confirms BOTH authentication AND authorization.
    # admin_page() gates on this so that authenticated-but-unauthorized users
    # (e.g. student_001) see a blank screen before redirect, not admin chrome.
    admin_authorized: bool = False

    # Live-sourced role/designation options for pickers (populated by _load_role_options).
    role_options: list[dict[str, str]] = []
    designation_options: list[dict[str, str]] = []

    # One-time temp-password display (set by create_user and reset_user_password).
    # Lives on BaseState so _admin_guard() can clear it on navigation away from
    # /admin/users — the only page where it should be visible.
    generated_password: str = ""

    def clear_flash(self) -> None:
        self.flash = ""

    def dismiss_flash(self) -> None:
        """Close-button handler: immediately clear the active notification."""
        self.flash = ""
        self.flash_type = "info"

    def _set_audit(
        self,
        *,
        resource_id: str | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        action: str | None = None,
    ) -> None:
        """Set audit emission data for the current handler invocation.

        The @audit_action decorator reads _audit_pending after the handler returns.
        Call AFTER session.commit() succeeds, never before.
        """
        self._audit_pending = {
            "resource_id": resource_id,
            "before": before,
            "after": after,
        }
        if action is not None:
            self._audit_pending["action_override"] = action

    def _resolve_session(self) -> None:
        """Resolve session cookie and populate current_user_id / current_username.

        Simpler than AuthState._resolve_session_state(): does not set
        must_change_password or profile_incomplete (those are AuthState vars).
        Used by admin page on_load handlers so they can do their own session
        check and redirect without depending on AuthState.
        """
        if not self.session_token:
            self.current_user_id = ""
            self.current_username = ""
            self._current_user_roles = []
            return
        from durgam.repositories.auth import UserSessionRepository
        from durgam.repositories.user import UserRepository
        from durgam.repositories.user_role import UserRoleRepository
        from durgam.services.auth import AuthService

        with open_session() as session:
            svc = AuthService(
                user_repo=UserRepository(session),
                session_repo=UserSessionRepository(session),
            )
            user = svc.resolve_session(self.session_token)
            if user is None:
                self.session_token = ""
                self.current_user_id = ""
                self.current_username = ""
                self._current_user_roles = []
            else:
                self.current_user_id = str(user.id)
                self.current_username = user.username
                ur_repo = UserRoleRepository(session)
                user_role_pairs = ur_repo.get_user_roles_with_role(user.id)
                self._current_user_roles = [
                    {
                        "role_code": role.code,
                        "scope_type": ur.scope_type,
                        "scope_id": str(ur.scope_id) if ur.scope_id else None,
                    }
                    for ur, role in user_role_pairs
                ]

    def _admin_guard(self):
        """Resolve session and verify admin (user:read:*) permission.

        Returns rx.redirect("/login") if unauthenticated,
        rx.redirect("/") with flash if authenticated but lacking admin
        permission, or None if access is allowed.

        Sets admin_authorized=True only when BOTH checks pass. admin_page()
        gates on admin_authorized so authenticated-but-unauthorized users
        (e.g. student_001) see a blank screen before redirect, not chrome.
        Clears flash on every admin navigation so stale notifications from
        a prior page do not persist.
        """
        self.admin_authorized = False  # require fresh auth+authz on every nav
        self.flash = ""               # clear stale flash from previous page
        self.flash_type = "info"
        # Clear the one-time temp password when navigating away from /admin/users.
        # On /admin/users itself this is a no-op; on any other admin page it clears.
        if getattr(self, "router", None) and self.router.page.path != "/admin/users":
            self.generated_password = ""
        self._resolve_session()
        if not self.current_user_id:
            return rx.redirect("/login")
        try:
            user_id = UUID(self.current_user_id)
        except ValueError:
            self.current_user_id = ""
            return rx.redirect("/login")
        with open_session() as session:
            if not can(user_id, "read", "user", None, None, session):
                self.flash = "You do not have admin access."
                self.flash_type = "warning"
                return rx.redirect("/")
        self.admin_authorized = True
        return None

    def _config_guard(self, resource: str, action: str = "write"):
        """Resolve session and verify config-level access.

        Parallel to _admin_guard() but checks can(action, resource) rather than
        can("read","user"). Defaults to action="write" so only users who can
        mutate the resource (not just read it) can reach config pages.
        Redirects to "/" (not "/admin") on permission failure.
        Sets admin_authorized=True on success so admin_page() shows content.
        """
        self.admin_authorized = False
        self.flash = ""
        self.flash_type = "info"
        self._resolve_session()
        if not self.current_user_id:
            return rx.redirect("/login")
        try:
            user_id = UUID(self.current_user_id)
        except ValueError:
            self.current_user_id = ""
            return rx.redirect("/login")
        with open_session() as session:
            if not can(user_id, action, resource, None, None, session):
                self.flash = "You do not have permission to access this page."
                self.flash_type = "warning"
                return rx.redirect("/")
        self.admin_authorized = True
        return None

    def _config_guard_any(
        self, gates: list[tuple[str, str, str | None]]
    ):
        """Guard that passes if user can perform ANY of the given (action, resource, scope_type).

        Uses any_scope=True so an HoD scoped to one department still passes when the
        gate includes department_vision_mission:write:department. Appropriate for pages
        that serve multiple roles with different permission paths.
        """
        self.admin_authorized = False
        self.flash = ""
        self.flash_type = "info"
        self._resolve_session()
        if not self.current_user_id:
            return rx.redirect("/login")
        try:
            user_id = UUID(self.current_user_id)
        except ValueError:
            self.current_user_id = ""
            return rx.redirect("/login")
        with open_session() as session:
            has_access = any(
                can(user_id, action, resource, scope_type, None, session, any_scope=True)
                for (action, resource, scope_type) in gates
            )
            if not has_access:
                self.flash = "You do not have permission to access this page."
                self.flash_type = "warning"
                return rx.redirect("/")
        self.admin_authorized = True
        return None

    def _dismiss_generated_password(self) -> None:
        """Clear the one-time temp-password display. Call from Dismiss button."""
        self.generated_password = ""

    def _resolve_user_dept_scope(self, session) -> UUID | None:
        """Return the department scope_id if the user has a dept-scoped role, else None."""
        from sqlmodel import select

        from durgam.models.identity import Role, UserRole

        stmt = (
            select(UserRole.scope_id)
            .join(Role, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == UUID(self.current_user_id),
                UserRole.scope_type == "department",
            )
            .limit(1)
        )
        result = session.exec(stmt).first()
        return result if result else None

    def _load_role_options(self, session) -> None:
        """Populate role_options from live roles table for role pickers."""
        from durgam.repositories.role import RoleRepository

        repo = RoleRepository(session)
        roles = repo.list_active()
        self.role_options = [
            {"code": r.code, "label": f"{r.name} ({r.code})"}
            for r in roles
        ]

    def _load_designation_options(self, session) -> None:
        """Populate designation_options from live designations table."""
        from durgam.repositories.designation import DesignationRepository

        repo = DesignationRepository(session)
        designations = repo.list_active()
        self.designation_options = [
            {"code": d.code, "label": f"{d.name} ({d.code})"}
            for d in designations
        ]

    def _load_nav_entries(self) -> None:
        """Populate visible_nav_entries for the current user.

        Called by page on_load handlers after _resolve_session_state() sets
        current_user_id. No-op if the user is not authenticated.
        """
        if not self.current_user_id:
            self.visible_nav_entries = []
            return
        try:
            user_id = UUID(self.current_user_id)
        except ValueError:
            self.visible_nav_entries = []
            return
        with open_session() as session:
            self.visible_nav_entries = get_visible_entries(user_id, session)
