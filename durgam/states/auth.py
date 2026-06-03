"""AuthState — orchestrates login, logout, and password flows.

States must not import SQLModel, SQLAlchemy, or any model (CLAUDE.md).
Database sessions are obtained via durgam.db.open_session().

Form handlers accept form_data: dict (Reflex's on_submit contract).
Page on_load handlers take no arguments and read URL params from self.router.
"""

from __future__ import annotations

from uuid import UUID

import reflex as rx

from durgam.auth.decorators import audit_action, public_handler
from durgam.config import settings
from durgam.db import open_session
from durgam.repositories.auth import PasswordResetTokenRepository, UserSessionRepository
from durgam.repositories.user import UserRepository
from durgam.repositories.user_role import UserRoleRepository
from durgam.services.auth import AuthError, AuthService, InvalidTokenError, PasswordService
from durgam.services.password import WeakPasswordError
from durgam.states.base import BaseState


def _auth_svc(session) -> AuthService:
    return AuthService(
        user_repo=UserRepository(session),
        session_repo=UserSessionRepository(session),
    )


def _pw_svc(session) -> PasswordService:
    return PasswordService(
        user_repo=UserRepository(session),
        token_repo=PasswordResetTokenRepository(session),
    )


class AuthState(BaseState):
    """Auth page state."""

    # Populated from URL query param ?token=... on the reset-password page.
    reset_token: str = ""
    is_loading: bool = False
    must_change_password: bool = False
    profile_incomplete: bool = False

    def _resolve_session_state(self) -> None:
        """Internal: populate current_user_id / username / must_change_password from cookie.

        All User attributes are read inside the with-block (before session.commit()
        or context exit) to prevent DetachedInstanceError — see CLAUDE.md.
        """
        if not self.session_token:
            self.current_user_id = ""
            self.current_username = ""
            self.must_change_password = False
            self._current_user_roles = []
            return
        with open_session() as session:
            user = _auth_svc(session).resolve_session(self.session_token)
            if user is None:
                self.session_token = ""
                self.current_user_id = ""
                self.current_username = ""
                self.must_change_password = False
                self._current_user_roles = []
            else:
                self.current_user_id = str(user.id)
                self.current_username = user.username
                self.must_change_password = user.must_change_password
                self.profile_incomplete = not user.profile_completed
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

    def resolve_session(self) -> None:
        """on_load for pages that show auth-aware UI but do NOT require login.

        Resolves the session cookie and populates state vars. Does NOT redirect.
        Use for /login, /forgot-password, /reset-password.
        """
        self._resolve_session_state()

    def home_on_load(self) -> None:
        """on_load for /: resolve session, then enforce route protection in one handler.

        (a) No session → redirect to /login.
        (b) Session present + must_change_password → redirect to /change-password.
        (c) Authenticated, no forced change → render normally.

        Using a single handler avoids sequencing uncertainty across multiple enqueued
        on_load events (the prior [resolve_session, check_forced_redirect] design
        relied on the second event seeing mutations from the first, which is guaranteed
        in theory but broke on fresh-compile server starts in Reflex 0.9.x).
        """
        self.flash = ""  # clear stale flash from prior navigation
        # Carry pending_success (e.g. "Password changed") into flash for display.
        if self.pending_success:
            self.flash = self.pending_success
            self.pending_success = ""
        self._resolve_session_state()
        if not self.current_user_id:
            return rx.redirect("/login")  # type: ignore[return-value]
        if self.must_change_password:
            return rx.redirect("/change-password")  # type: ignore[return-value]
        # Populate nav entries so the home page nav shell shows the correct links.
        # Without this call, visible_nav_entries stays [] and nav links are absent.
        self._load_nav_entries()

    def change_password_on_load(self) -> None:
        """on_load for /change-password: protect the route without a second DB lookup.

        Uses current_user_id already set by the login handler delta or a prior
        resolve_session call. Does NOT call _resolve_session_state() here because
        a second DB lookup in the same event chain can race with the session record
        being visible — _resolve_session_state() would then clear current_user_id and
        redirect to /login, creating a redirect loop for firstlogin_user.

        If current_user_id is empty (user arrived unauthenticated), redirect to /login.
        Does NOT redirect must_change_password users — they are already on the right page.
        """
        self.flash = ""  # clear stale flash from prior navigation (Bug C)
        if not self.current_user_id:
            # Session not yet resolved; resolve it now so the page has state.
            self._resolve_session_state()
            if not self.current_user_id:
                return rx.redirect("/login")  # type: ignore[return-value]

    def load_reset_token(self) -> None:
        """Read ?token= query param from the URL. Use as on_load on the reset-password page."""
        self.reset_token = self.router._page.params.get("token", "")

    @public_handler
    @audit_action(action="login", resource="session")
    async def login(self, form_data: dict) -> None:
        username = form_data.get("username", "").strip()
        password = form_data.get("password", "")
        self.is_loading = True
        self.flash = ""
        try:
            with open_session() as session:
                try:
                    user, _, raw_token = _auth_svc(session).login(
                        username,
                        password,
                        ip=self.client_ip or None,
                        user_agent=self.client_user_agent or None,
                    )
                except AuthError:
                    # Commit before re-raising so failed_login_count and locked_until
                    # are persisted despite the transaction rollback that would otherwise
                    # discard them when open_session() exits on exception.
                    session.commit()
                    raise
                # Read all user attributes BEFORE commit expires them and BEFORE
                # the session context closes and detaches the object.
                user_id = str(user.id)
                login_username = user.username
                must_change = user.must_change_password
                profile_done = user.profile_completed
                session.commit()
            self.session_token = raw_token
            self.current_user_id = user_id
            self.current_username = login_username
            self.must_change_password = must_change
            self.profile_incomplete = not profile_done
            self._set_audit(resource_id=user_id)
            if self.must_change_password:
                return rx.redirect("/change-password")  # type: ignore[return-value]
            return rx.redirect("/")  # type: ignore[return-value]
        except AuthError as exc:
            normalized = username.strip().lower()
            self._set_audit(
                action="login_failed",
                resource_id=normalized,
                after={"reason": exc.reason, "ip": self.client_ip or None},
            )
            self.flash = exc.message
            self.flash_type = "error"
        finally:
            self.is_loading = False

    @public_handler
    @audit_action(action="logout", resource="session")
    async def logout(self) -> None:
        token = self.session_token
        logout_user_id = self.current_user_id
        if token:
            with open_session() as session:
                _auth_svc(session).logout(token)
                session.commit()
        self._set_audit(resource_id=logout_user_id)
        self.session_token = ""
        self.current_user_id = ""
        self.current_username = ""
        self.must_change_password = False
        self.flash = ""            # clear stale flash (Bug 10)
        self.admin_authorized = False  # reset admin gate on logout
        return rx.redirect("/login")  # type: ignore[return-value]

    @public_handler
    @audit_action(action="change_password", resource="session")
    async def change_password(self, form_data: dict) -> None:
        current = form_data.get("password", "")
        new_pw = form_data.get("new_password", "")
        confirm = form_data.get("confirm_password", "")
        self.flash = ""
        if new_pw != confirm:
            self.flash = "New passwords do not match."
            self.flash_type = "error"
            return
        try:
            with open_session() as session:
                _pw_svc(session).change_password_for_user(
                    UUID(self.current_user_id), current, new_pw
                )
                session.commit()
            self._set_audit(
                resource_id=self.current_user_id,
                after={"changed": True},
            )
            self.must_change_password = False
            self.pending_success = "Password changed successfully."
            return rx.redirect("/")  # type: ignore[return-value]
        except AuthError as exc:
            self.flash = exc.message
            self.flash_type = "error"
        except WeakPasswordError as exc:
            self.flash = exc.reason
            self.flash_type = "error"

    @public_handler
    @audit_action(action="request_password_reset", resource="session")
    async def request_password_reset(self, form_data: dict) -> None:
        email = form_data.get("email", "").strip()
        self.flash = ""
        self.is_loading = True
        try:
            with open_session() as session:
                await _pw_svc(session).request_reset(
                    email,
                    ip=self.client_ip or None,
                    reset_url_base=settings.app_base_url,
                )
                session.commit()
            self._set_audit(resource_id=email, after={"email": email})
            self.flash = (
                "If that email is registered, a reset link has been sent. "
                "Check your inbox (or Mailpit in dev)."
            )
        finally:
            self.is_loading = False

    @public_handler
    @audit_action(action="reset_password", resource="session")
    async def reset_password(self, form_data: dict) -> None:
        import hashlib

        new_pw = form_data.get("new_password", "")
        confirm = form_data.get("confirm_password", "")
        self.flash = ""
        if new_pw != confirm:
            self.flash = "Passwords do not match."
            return
        try:
            with open_session() as session:
                user = _pw_svc(session).consume_reset_token(self.reset_token, new_pw)
                reset_user_id = str(user.id)
                session.commit()
            token_hash = hashlib.sha256(self.reset_token.encode()).hexdigest()
            self._set_audit(
                resource_id=reset_user_id,
                after={"token_hash": token_hash, "token_consumed": True},
            )
            self.flash = "Password reset successfully. You can now log in."
            self.reset_token = ""
            return rx.redirect("/login")  # type: ignore[return-value]
        except InvalidTokenError as exc:
            self._set_audit(resource_id="<invalid_token>")
            self.flash = str(exc)
        except WeakPasswordError as exc:
            self.flash = exc.reason
