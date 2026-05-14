"""Session and password-reset models for M1 Authentication (RFP §9.1)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

_TIMESTAMPTZ: type[Any] = cast(type[Any], sa.DateTime(timezone=True))


class UserSession(SQLModel, table=True):
    """Server-side session record — authoritative for session validity.

    The opaque session_token (UUID v4) is stored in the browser via rx.Cookie().
    Server-side invalidation (logout, admin force-logout, expiry check) always
    wins regardless of what the cookie holds.

    See docs/security_decisions.md SD-001 for the HttpOnly gap analysis.
    """

    __tablename__ = "user_sessions"
    __table_args__ = (
        sa.Index("ix_user_sessions_user_id", "user_id"),
        sa.Index("ix_user_sessions_token_hash", "token_hash", unique=True),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", nullable=False)
    token_hash: str = Field(max_length=64, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=_TIMESTAMPTZ,
        nullable=False,
    )
    last_active_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=_TIMESTAMPTZ,
        nullable=False,
    )
    expires_at: datetime = Field(sa_type=_TIMESTAMPTZ, nullable=False)
    is_invalidated: bool = Field(default=False, nullable=False)
    ip: str | None = Field(default=None, max_length=45)
    user_agent: str | None = Field(default=None, max_length=512)


class PasswordResetToken(SQLModel, table=True):
    """One-time password reset token (30-minute expiry, per RFP §9.1)."""

    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        sa.Index("ix_password_reset_tokens_user_id", "user_id"),
        sa.Index("ix_password_reset_tokens_token_hash", "token_hash", unique=True),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", nullable=False)
    token_hash: str = Field(max_length=64, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=_TIMESTAMPTZ,
        nullable=False,
    )
    expires_at: datetime = Field(sa_type=_TIMESTAMPTZ, nullable=False)
    is_used: bool = Field(default=False, nullable=False)
