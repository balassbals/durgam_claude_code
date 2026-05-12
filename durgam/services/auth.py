"""Auth service — login, logout, session management, password reset (RFP §9.1)."""

from __future__ import annotations

import secrets
from datetime import timedelta

import structlog

from durgam.auth.rate_limit import check_and_record, reset
from durgam.config import settings
from durgam.models.auth import UserSession
from durgam.models.identity import User
from durgam.notifications.email import send_email
from durgam.repositories.auth import PasswordResetTokenRepository, UserSessionRepository
from durgam.repositories.user import UserRepository
from durgam.services.password import (
    hash_password,
    validate_policy,
    verify_password,
)

log = structlog.get_logger(__name__)


class AuthError(Exception):
    """Raised for user-visible auth failures (invalid credentials, lockout, etc.)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidTokenError(Exception):
    """Raised when a password-reset token is invalid, expired, or already used."""


def _ip_rl_key(ip: str) -> str:
    return f"rl:login:ip:{ip}"


def _user_rl_key(username: str) -> str:
    return f"rl:login:user:{username}"


def _reset_rl_key(ip: str) -> str:
    return f"rl:reset:ip:{ip}"


class AuthService:
    def __init__(self, user_repo: UserRepository, session_repo: UserSessionRepository) -> None:
        self._users = user_repo
        self._sessions = session_repo

    def login(
        self,
        username: str,
        password: str,
        *,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, UserSession, str]:
        """Authenticate a user and create a new session.

        Returns (user, session_record, raw_token). The caller stores raw_token
        in the rx.Cookie(); only its SHA-256 hash is persisted in the DB.

        Raises AuthError for any visible failure (credentials, lockout, inactive).
        Raises RateLimitExceeded for IP-level throttling.
        """
        if ip:
            check_and_record(
                _ip_rl_key(ip),
                settings.auth_ip_throttle_limit,
                settings.auth_ip_throttle_window_minutes * 60,
            )

        user = self._users.get_by_username(username)
        if user is None:
            # Do not reveal whether the user exists.
            log.info("login_failed_unknown_user", username=username, ip=ip)
            raise AuthError("Invalid username or password.")

        if not user.is_active:
            log.info("login_failed_inactive", user_id=str(user.id), ip=ip)
            raise AuthError("Account is inactive. Contact the administrator.")

        if user.locked_until is not None:
            from datetime import UTC, datetime

            if datetime.now(UTC) < user.locked_until:
                log.info("login_blocked_lockout", user_id=str(user.id), ip=ip)
                remaining = int((user.locked_until - datetime.now(UTC)).total_seconds() // 60)
                raise AuthError(
                    f"Account temporarily locked. Try again in {remaining + 1} minute(s)."
                )

        if not verify_password(password, user.password_hash):
            self._users.increment_failed_logins(user)
            if user.failed_login_count >= settings.auth_user_failure_threshold:
                self._users.set_locked_until(
                    user, timedelta(minutes=settings.auth_user_lockout_minutes)
                )
                log.info("account_locked", user_id=str(user.id), ip=ip)
                raise AuthError(
                    f"Too many failed attempts. Account locked for "
                    f"{settings.auth_user_lockout_minutes} minute(s)."
                )
            log.info("login_failed_bad_password", user_id=str(user.id), ip=ip)
            raise AuthError("Invalid username or password.")

        # Successful authentication — clear counters and create session.
        self._users.clear_failed_logins(user)
        if ip:
            reset(_ip_rl_key(ip))
        self._users.update_last_login(user)

        raw_token = secrets.token_urlsafe(32)
        session_record = self._sessions.create(user.id, raw_token, ip=ip, user_agent=user_agent)
        log.info("login_success", user_id=str(user.id), session_id=str(session_record.id))
        return user, session_record, raw_token

    def logout(self, raw_token: str) -> None:
        """Invalidate the session identified by *raw_token*."""
        session_record = self._sessions.get_active(raw_token)
        if session_record is not None:
            self._sessions.invalidate(session_record)
            log.info("logout", session_id=str(session_record.id))

    def resolve_session(self, raw_token: str) -> User | None:
        """Return the User for an active session, sliding the expiry window.

        Returns None if the token is missing, invalid, or expired.
        """
        if not raw_token:
            return None
        session_record = self._sessions.get_active(raw_token)
        if session_record is None:
            return None
        self._sessions.slide_expiry(session_record)
        user = self._users._session.get(User, session_record.user_id)
        if user is None or user.is_deleted or not user.is_active:
            self._sessions.invalidate(session_record)
            return None
        return user


class PasswordService:
    """Handles change-password and password-reset flows."""

    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: PasswordResetTokenRepository,
    ) -> None:
        self._users = user_repo
        self._tokens = token_repo

    def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
    ) -> User:
        """Change password for an authenticated user.

        Raises AuthError if current_password is wrong.
        Raises WeakPasswordError if new_password fails policy.
        """
        if not verify_password(current_password, user.password_hash):
            raise AuthError("Current password is incorrect.")
        validate_policy(new_password, email=user.email, full_name="")
        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        self._users._session.add(user)
        self._users._session.flush()
        log.info("password_changed", user_id=str(user.id))
        return user

    def set_password(self, user: User, new_password: str) -> User:
        """Set password without verifying the current one (admin reset path)."""
        validate_policy(new_password, email=user.email, full_name="")
        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        self._users._session.add(user)
        self._users._session.flush()
        return user

    async def request_reset(
        self,
        email: str,
        *,
        ip: str | None = None,
        reset_url_base: str = "",
    ) -> None:
        """Send a password-reset email (rate-limited per IP).

        Always returns without error to avoid user enumeration — if the email
        is not found no email is sent but no error is raised either.
        """
        if ip:
            check_and_record(
                _reset_rl_key(ip),
                settings.auth_ip_throttle_limit,
                settings.auth_ip_throttle_window_minutes * 60,
            )

        user = self._users.get_by_email(email)
        if user is None:
            log.info("password_reset_requested_unknown_email", ip=ip)
            return

        raw_token = secrets.token_urlsafe(32)
        self._tokens.create(user.id, raw_token)

        reset_link = f"{reset_url_base}/reset-password?token={raw_token}"
        await send_email(
            to=user.email,
            subject="Reset your DURGAM password",
            body_html=_reset_email_html(reset_link),
            body_text=_reset_email_text(reset_link),
        )
        log.info("password_reset_email_sent", user_id=str(user.id))

    def consume_reset_token(self, raw_token: str, new_password: str) -> User:
        """Validate a reset token and set the new password.

        Raises InvalidTokenError if token is invalid/expired/used.
        Raises WeakPasswordError if new_password fails policy.
        """
        token_record = self._tokens.get_valid(raw_token)
        if token_record is None:
            raise InvalidTokenError("Reset link is invalid or has expired.")
        user = self._users._session.get(User, token_record.user_id)
        if user is None or user.is_deleted:
            raise InvalidTokenError("Reset link is invalid or has expired.")
        validate_policy(new_password, email=user.email, full_name="")
        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        self._users._session.add(user)
        self._tokens.mark_used(token_record)
        self._users._session.flush()
        log.info("password_reset_consumed", user_id=str(user.id))
        return user


def _reset_email_html(reset_link: str) -> str:
    return f"""
<html><body>
<p>You requested a password reset for your DURGAM account.</p>
<p><a href="{reset_link}">Click here to reset your password</a></p>
<p>This link expires in 30 minutes and can only be used once.</p>
<p>If you did not request a reset, ignore this email.</p>
</body></html>
"""


def _reset_email_text(reset_link: str) -> str:
    return (
        "You requested a password reset for your DURGAM account.\n\n"
        f"Reset link: {reset_link}\n\n"
        "This link expires in 30 minutes and can only be used once.\n"
        "If you did not request a reset, ignore this email."
    )
