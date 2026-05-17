"""UserRepository — auth-related and admin CRUD queries on the users table."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Session, func, select

from durgam.models.identity import User
from durgam.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: Session) -> None:
        super().__init__(User, session)

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
                User.email.ilike(email),  # type: ignore[attr-defined]
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

    # ── Admin CRUD ────────────────────────────────────────────────────────────

    def list_paginated(
        self,
        search: str | None,
        offset: int,
        limit: int,
        *,
        exclude_ephemeral: bool = False,
    ) -> tuple[list[User], int]:
        """Return (page, total) of active users, optionally filtered by search string.

        Search is a case-insensitive substring match on username or email.
        exclude_ephemeral: if True, excludes usernames starting with 'e2e_' (test users).
        """
        base = select(User).where(User.is_deleted == False)  # noqa: E712
        if exclude_ephemeral:
            # Filter out ephemeral test users (e2e_* pattern) from UI dropdowns.
            # The admin user list still shows them; only permission widgets filter.
            base = base.where(~User.username.like("e2e_%"))  # type: ignore[attr-defined]
        if search:
            pattern = f"%{search}%"
            base = base.where(
                sa.or_(
                    User.username.ilike(pattern),  # type: ignore[attr-defined]
                    User.email.ilike(pattern),  # type: ignore[attr-defined]
                )
            )
        total: int = self._session.exec(
            select(func.count()).select_from(base.subquery())
        ).one()
        # ORDER BY created_at DESC: newest users first; deterministic without it.
        ordered = base.order_by(User.created_at.desc())  # type: ignore[attr-defined]
        rows = list(self._session.exec(ordered.offset(offset).limit(limit)).all())
        return rows, total

    def create(
        self,
        username: str,
        email: str,
        password_hash: str,
        actor_id: UUID,
        *,
        must_change_password: bool = True,
        full_name: str | None = None,
    ) -> User:
        """Insert a new active user and return it with a populated id."""
        now = datetime.now(UTC)
        user = User(
            username=username,
            email=email,
            full_name=full_name or None,
            password_hash=password_hash,
            is_active=True,
            must_change_password=must_change_password,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(user)
        self._session.flush()
        self._session.refresh(user)
        return user

    def update_fields(self, user: User, fields: dict, actor_id: UUID) -> User:
        """Apply a dict of field updates to a user and flush."""
        for key, value in fields.items():
            setattr(user, key, value)
        user.updated_at = datetime.now(UTC)
        user.updated_by = actor_id
        self._session.add(user)
        self._session.flush()
        self._session.refresh(user)
        return user

    def hard_delete(self, user: User) -> None:
        """Permanently remove a user row.

        The caller (UserAdminService) is responsible for checking that no
        audit rows reference this user before calling this method.
        """
        self._session.delete(user)
        self._session.flush()
