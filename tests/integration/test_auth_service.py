"""Integration tests for AuthService and PasswordService against real PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import Session

from durgam.models.identity import User
from durgam.repositories.auth import PasswordResetTokenRepository, UserSessionRepository
from durgam.repositories.user import UserRepository
from durgam.services.auth import AuthError, AuthService, InvalidTokenError, PasswordService
from durgam.services.password import WeakPasswordError, hash_password


def _make_user(
    session: Session,
    *,
    active: bool = True,
    must_change: bool = False,
    password: str = "Tr0ub4dor&3!X",
) -> User:
    from uuid import uuid4

    user = User(
        username=f"u_{uuid4().hex[:8]}",
        email=f"u_{uuid4().hex[:8]}@test.sssihl.edu.in",
        password_hash=hash_password(password),
        is_active=active,
        must_change_password=must_change,
    )
    session.add(user)
    session.flush()
    return user


def _auth_service(session: Session) -> AuthService:
    return AuthService(
        user_repo=UserRepository(session),
        session_repo=UserSessionRepository(session),
    )


def _password_service(session: Session) -> PasswordService:
    return PasswordService(
        user_repo=UserRepository(session),
        token_repo=PasswordResetTokenRepository(session),
    )


class TestLogin:
    def test_successful_login_returns_user_and_token(self, db_session):
        user = _make_user(db_session, password="Tr0ub4dor&3!X")
        svc = _auth_service(db_session)
        returned_user, session_record, raw_token = svc.login(
            user.username, "Tr0ub4dor&3!X"
        )
        assert returned_user.id == user.id
        assert raw_token
        assert not session_record.is_invalidated

    def test_wrong_password_raises_auth_error(self, db_session):
        user = _make_user(db_session)
        svc = _auth_service(db_session)
        with pytest.raises(AuthError, match="Invalid username or password"):
            svc.login(user.username, "WrongPass!1A")

    def test_unknown_username_raises_auth_error(self, db_session):
        svc = _auth_service(db_session)
        with pytest.raises(AuthError, match="Invalid username or password"):
            svc.login("does_not_exist", "Tr0ub4dor&3!X")

    def test_inactive_user_raises_auth_error(self, db_session):
        user = _make_user(db_session, active=False)
        svc = _auth_service(db_session)
        with pytest.raises(AuthError, match="inactive"):
            svc.login(user.username, "Tr0ub4dor&3!X")

    def test_failed_logins_increment_counter(self, db_session):
        user = _make_user(db_session)
        svc = _auth_service(db_session)
        for _ in range(3):
            with pytest.raises(AuthError):
                svc.login(user.username, "WrongPass!1A")
        db_session.refresh(user)
        assert user.failed_login_count == 3

    def test_lockout_after_threshold(self, db_session):
        user = _make_user(db_session)
        svc = _auth_service(db_session)
        threshold = 5
        for _ in range(threshold):
            with pytest.raises(AuthError):
                svc.login(user.username, "WrongPass!1A")
        db_session.refresh(user)
        assert user.locked_until is not None
        assert user.locked_until > datetime.now(UTC)

    def test_locked_user_cannot_login_with_correct_password(self, db_session):
        user = _make_user(db_session)
        svc = _auth_service(db_session)
        for _ in range(6):
            with pytest.raises(AuthError):
                svc.login(user.username, "WrongPass!1A")
        with pytest.raises(AuthError, match="locked"):
            svc.login(user.username, "Tr0ub4dor&3!X")

    def test_successful_login_clears_failed_count(self, db_session):
        user = _make_user(db_session)
        svc = _auth_service(db_session)
        for _ in range(3):
            with pytest.raises(AuthError):
                svc.login(user.username, "WrongPass!1A")
        svc.login(user.username, "Tr0ub4dor&3!X")
        db_session.refresh(user)
        assert user.failed_login_count == 0

    def test_successful_login_stamps_last_login_at(self, db_session):
        user = _make_user(db_session)
        svc = _auth_service(db_session)
        svc.login(user.username, "Tr0ub4dor&3!X")
        db_session.refresh(user)
        assert user.last_login_at is not None


class TestLogoutAndSession:
    def test_logout_invalidates_session(self, db_session):
        user = _make_user(db_session)
        svc = _auth_service(db_session)
        _, session_record, raw_token = svc.login(user.username, "Tr0ub4dor&3!X")
        svc.logout(raw_token)
        db_session.refresh(session_record)
        assert session_record.is_invalidated

    def test_resolve_session_returns_user(self, db_session):
        user = _make_user(db_session)
        svc = _auth_service(db_session)
        _, _, raw_token = svc.login(user.username, "Tr0ub4dor&3!X")
        resolved = svc.resolve_session(raw_token)
        assert resolved is not None
        assert resolved.id == user.id

    def test_resolve_session_returns_none_after_logout(self, db_session):
        user = _make_user(db_session)
        svc = _auth_service(db_session)
        _, _, raw_token = svc.login(user.username, "Tr0ub4dor&3!X")
        svc.logout(raw_token)
        assert svc.resolve_session(raw_token) is None

    def test_resolve_session_slides_expiry(self, db_session):
        user = _make_user(db_session)
        svc = _auth_service(db_session)
        _, session_record, raw_token = svc.login(user.username, "Tr0ub4dor&3!X")
        original_expiry = session_record.expires_at
        resolved = svc.resolve_session(raw_token)
        assert resolved is not None
        db_session.refresh(session_record)
        assert session_record.expires_at >= original_expiry

    def test_expired_session_returns_none(self, db_session):
        user = _make_user(db_session)
        svc = _auth_service(db_session)
        _, session_record, raw_token = svc.login(user.username, "Tr0ub4dor&3!X")
        session_record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db_session.add(session_record)
        db_session.flush()
        assert svc.resolve_session(raw_token) is None


class TestChangePassword:
    def test_change_password_success(self, db_session):
        user = _make_user(db_session, password="Tr0ub4dor&3!X")
        svc = _password_service(db_session)
        svc.change_password(user, "Tr0ub4dor&3!X", "N3wSecure!Pass#Z")
        db_session.refresh(user)
        from durgam.services.password import verify_password

        assert verify_password("N3wSecure!Pass#Z", user.password_hash)

    def test_change_password_wrong_current_raises(self, db_session):
        user = _make_user(db_session)
        svc = _password_service(db_session)
        with pytest.raises(AuthError, match="Current password is incorrect"):
            svc.change_password(user, "WrongCurrentPa$$1A", "N3wSecure!Pass#Z")

    def test_change_password_weak_new_raises(self, db_session):
        user = _make_user(db_session)
        svc = _password_service(db_session)
        with pytest.raises(WeakPasswordError):
            svc.change_password(user, "Tr0ub4dor&3!X", "short")

    def test_change_password_clears_must_change_flag(self, db_session):
        user = _make_user(db_session, must_change=True)
        svc = _password_service(db_session)
        svc.change_password(user, "Tr0ub4dor&3!X", "N3wSecure!Pass#Z")
        db_session.refresh(user)
        assert not user.must_change_password


class TestPasswordReset:
    def test_consume_valid_token_sets_password(self, db_session):
        user = _make_user(db_session)
        svc = _password_service(db_session)
        import secrets

        raw_token = secrets.token_urlsafe(32)
        svc._tokens.create(user.id, raw_token)
        svc.consume_reset_token(raw_token, "N3wSecure!Pass#Z")
        db_session.refresh(user)
        from durgam.services.password import verify_password

        assert verify_password("N3wSecure!Pass#Z", user.password_hash)

    def test_consume_token_marks_as_used(self, db_session):
        user = _make_user(db_session)
        svc = _password_service(db_session)
        import secrets

        raw_token = secrets.token_urlsafe(32)
        token_record = svc._tokens.create(user.id, raw_token)
        svc.consume_reset_token(raw_token, "N3wSecure!Pass#Z")
        db_session.refresh(token_record)
        assert token_record.is_used

    def test_consume_token_twice_raises(self, db_session):
        user = _make_user(db_session)
        svc = _password_service(db_session)
        import secrets

        raw_token = secrets.token_urlsafe(32)
        svc._tokens.create(user.id, raw_token)
        svc.consume_reset_token(raw_token, "N3wSecure!Pass#Z")
        with pytest.raises(InvalidTokenError):
            svc.consume_reset_token(raw_token, "An0ther!Pass#99")

    def test_expired_token_raises(self, db_session):
        user = _make_user(db_session)
        svc = _password_service(db_session)
        import secrets

        raw_token = secrets.token_urlsafe(32)
        token_record = svc._tokens.create(user.id, raw_token)
        token_record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db_session.add(token_record)
        db_session.flush()
        with pytest.raises(InvalidTokenError):
            svc.consume_reset_token(raw_token, "N3wSecure!Pass#Z")

    def test_invalid_token_raises(self, db_session):
        svc = _password_service(db_session)
        with pytest.raises(InvalidTokenError):
            svc.consume_reset_token("not-a-real-token", "N3wSecure!Pass#Z")

    @pytest.mark.asyncio
    async def test_request_reset_sends_email(self, db_session):
        user = _make_user(db_session)
        svc = _password_service(db_session)
        with patch(
            "durgam.services.auth.send_email", new_callable=AsyncMock
        ) as mock_send:
            await svc.request_reset(user.email, ip="127.0.0.1", reset_url_base="http://localhost:3000")
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["to"] == user.email
        assert "Reset your DURGAM password" in call_kwargs["subject"]

    @pytest.mark.asyncio
    async def test_request_reset_unknown_email_silent(self, db_session):
        svc = _password_service(db_session)
        with patch("durgam.services.auth.send_email", new_callable=AsyncMock) as mock_send:
            await svc.request_reset("unknown@example.com")
        mock_send.assert_not_called()
