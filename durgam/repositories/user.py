"""UserRepository — auth-related queries on the users table."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from durgam.models.identity import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_username(self, username: str) -> User | None:
        """Return an active user by username (case-sensitive)."""
        return self._session.exec(
            select(User).where(
                User.username == username,
                User.is_deleted == False,  # noqa: E712
            )
        ).first()

    def get_by_email(self, email: str) -> User | None:
        """Return an active user by email (case-insensitive)."""
        return self._session.exec(
            select(User).where(
                User.email.ilike(email),  # type: ignore[union-attr]
                User.is_deleted == False,  # noqa: E712
            )
        ).first()

    def increment_failed_logins(self, user: User) -> User:
        """Increment failed_login_count and flush."""
        user.failed_login_count += 1
        self._session.add(user)
        self._session.flush()
        return user

    def clear_failed_logins(self, user: User) -> User:
        """Reset failed_login_count to 0 and clear lockout."""
        user.failed_login_count = 0
        user.locked_until = None
        self._session.add(user)
        self._session.flush()
        return user

    def set_locked_until(self, user: User, duration: timedelta) -> User:
        """Lock the account until now() + duration."""
        user.locked_until = datetime.now(UTC) + duration
        self._session.add(user)
        self._session.flush()
        return user

    def update_last_login(self, user: User) -> User:
        """Stamp last_login_at with the current UTC time."""
        user.last_login_at = datetime.now(UTC)
        self._session.add(user)
        self._session.flush()
        return user
