"""Auth repositories — UserSession and PasswordResetToken queries."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlmodel import Session, select

from durgam.models.auth import PasswordResetToken, UserSession

_SESSION_TTL_DAYS = 7
_RESET_TOKEN_TTL_MINUTES = 30


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class UserSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        user_id: UUID,
        raw_token: str,
        *,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> UserSession:
        """Persist a new session and return it."""
        now = datetime.now(UTC)
        record = UserSession(
            user_id=user_id,
            token_hash=_sha256(raw_token),
            created_at=now,
            last_active_at=now,
            expires_at=now + timedelta(days=_SESSION_TTL_DAYS),
            is_invalidated=False,
            ip=ip,
            user_agent=user_agent,
        )
        self._session.add(record)
        self._session.flush()
        self._session.refresh(record)
        return record

    def get_active(self, raw_token: str) -> UserSession | None:
        """Return the session if it is valid (not invalidated, not expired)."""
        token_hash = _sha256(raw_token)
        now = datetime.now(UTC)
        return self._session.exec(
            select(UserSession).where(
                UserSession.token_hash == token_hash,
                UserSession.is_invalidated == False,  # noqa: E712
                UserSession.expires_at > now,
            )
        ).first()

    def slide_expiry(self, session_record: UserSession) -> UserSession:
        """Extend the session by resetting last_active_at and expires_at."""
        now = datetime.now(UTC)
        session_record.last_active_at = now
        session_record.expires_at = now + timedelta(days=_SESSION_TTL_DAYS)
        self._session.add(session_record)
        self._session.flush()
        return session_record

    def invalidate(self, session_record: UserSession) -> UserSession:
        """Mark the session as invalidated (logout or admin action)."""
        session_record.is_invalidated = True
        self._session.add(session_record)
        self._session.flush()
        return session_record

    def invalidate_all_for_user(self, user_id: UUID) -> int:
        """Invalidate every active session for a user; returns count."""
        rows = self._session.exec(
            select(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.is_invalidated == False,  # noqa: E712
            )
        ).all()
        for row in rows:
            row.is_invalidated = True
            self._session.add(row)
        self._session.flush()
        return len(rows)


class PasswordResetTokenRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, user_id: UUID, raw_token: str) -> PasswordResetToken:
        """Persist a new reset token (one-time, 30-min expiry)."""
        now = datetime.now(UTC)
        record = PasswordResetToken(
            user_id=user_id,
            token_hash=_sha256(raw_token),
            created_at=now,
            expires_at=now + timedelta(minutes=_RESET_TOKEN_TTL_MINUTES),
            is_used=False,
        )
        self._session.add(record)
        self._session.flush()
        self._session.refresh(record)
        return record

    def get_valid(self, raw_token: str) -> PasswordResetToken | None:
        """Return the token record if unused and not expired."""
        token_hash = _sha256(raw_token)
        now = datetime.now(UTC)
        return self._session.exec(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.is_used == False,  # noqa: E712
                PasswordResetToken.expires_at > now,
            )
        ).first()

    def mark_used(self, token_record: PasswordResetToken) -> PasswordResetToken:
        """Consume the token so it cannot be used again."""
        token_record.is_used = True
        self._session.add(token_record)
        self._session.flush()
        return token_record
