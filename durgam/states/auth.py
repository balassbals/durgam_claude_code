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
from durgam.services.auth import AuthError, AuthService, InvalidTokenError, PasswordService
from durgam.services.password import WeakPasswordError
from durgam.states.base import BaseState


def _auth_svc(session) -> AuthService:  # type: ignore[no-untyped-def]
    return AuthService(
        user_repo=UserRepository(session),
        session_repo=UserSessionRepository(session),
    )


def _pw_svc(session) -> PasswordService:  # type: ignore[no-untyped-def]
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

    def resolve_session(self) -> None:
        """Resolve session_token → current_user_id. Use as on_load on every auth-aware page."""
        if not self.session_token:
            self.current_user_id = ""
            self.must_change_password = False
            return
        with open_session() as session:
            user = _auth_svc(session).resolve_session(self.session_token)
            if user is None:
                self.session_token = ""
                self.current_user_id = ""
                self.must_change_password = False
            else:
                self.current_user_id = str(user.id)
                self.must_change_password = user.must_change_password
                self.profile_incomplete = not user.profile_completed

    def load_reset_token(self) -> None:
        """Read ?token= query param from the URL. Use as on_load on the reset-password page."""
        self.reset_token = self.router._page.params.get("token", "")  # type: ignore[attr-defined]

    @public_handler
    @audit_action(action="login", resource="session")
    async def login(self, form_data: dict) -> None:
        username = form_data.get("username", "").strip()
        password = form_data.get("password", "")
        self.is_loading = True
        self.flash = ""
        try:
            with open_session() as session:
                user, _, raw_token = _auth_svc(session).login(
                    username,
                    password,
                    ip=self.client_ip or None,
                    user_agent=self.client_user_agent or None,
                )
                session.commit()
            self.session_token = raw_token
            self.current_user_id = str(user.id)
            self.must_change_password = user.must_change_password
            self.profile_incomplete = not user.profile_completed
            if self.must_change_password:
                return rx.redirect("/change-password")  # type: ignore[return-value]
            return rx.redirect("/")  # type: ignore[return-value]
        except AuthError as exc:
            self.flash = exc.message
        finally:
            self.is_loading = False

    @public_handler
    @audit_action(action="logout", resource="session")
    async def logout(self) -> None:
        token = self.session_token
        if token:
            with open_session() as session:
                _auth_svc(session).logout(token)
                session.commit()
        self.session_token = ""
        self.current_user_id = ""
        self.must_change_password = False
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
            return
        try:
            with open_session() as session:
                _pw_svc(session).change_password_for_user(
                    UUID(self.current_user_id), current, new_pw
                )
                session.commit()
            self.must_change_password = False
            return rx.redirect("/")  # type: ignore[return-value]
        except AuthError as exc:
            self.flash = exc.message
        except WeakPasswordError as exc:
            self.flash = exc.reason

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
            self.flash = (
                "If that email is registered, a reset link has been sent. "
                "Check your inbox (or Mailpit in dev)."
            )
        finally:
            self.is_loading = False

    @public_handler
    @audit_action(action="reset_password", resource="session")
    async def reset_password(self, form_data: dict) -> None:
        new_pw = form_data.get("new_password", "")
        confirm = form_data.get("confirm_password", "")
        self.flash = ""
        if new_pw != confirm:
            self.flash = "Passwords do not match."
            return
        try:
            with open_session() as session:
                _pw_svc(session).consume_reset_token(self.reset_token, new_pw)
                session.commit()
            self.flash = "Password reset successfully. You can now log in."
            self.reset_token = ""
            return rx.redirect("/login")  # type: ignore[return-value]
        except InvalidTokenError as exc:
            self.flash = str(exc)
        except WeakPasswordError as exc:
            self.flash = exc.reason
