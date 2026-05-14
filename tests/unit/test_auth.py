"""Pure unit tests for auth module — no database required.

M1 contract: decorators read current_user_id from args[0] (a Reflex State-like
object), not from kwargs. Tests verify the new contract. The old kwargs-based
contract is intentionally not backward-compatible; see docs/modules/auth.md.

Tests that need real DB queries (can(), audit row creation) live in
tests/integration/test_auth.py.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from durgam.auth.decorators import audit_action, public_handler, require_role
from durgam.auth.permissions import PermissionDenied


def _make_state(user_id: str = "", role_code: str | None = None) -> MagicMock:
    """Build a minimal Reflex State mock with auth attributes."""
    state = MagicMock()
    state.current_user_id = user_id
    state.current_role_code = role_code
    state.request_id = "req-test"
    state.client_ip = "127.0.0.1"
    state.client_user_agent = "pytest"
    state.scope_id = None

    db_session = MagicMock()
    db_session.__enter__ = lambda s: MagicMock()
    db_session.__exit__ = MagicMock(return_value=False)

    @contextmanager
    def _get_db_session():
        yield db_session

    state._get_db_session = _get_db_session
    return state


class TestPermissionDenied:
    def test_exception_carries_fields(self):
        uid = uuid4()
        exc = PermissionDenied(user_id=uid, action="delete", resource="leave_request")
        assert exc.user_id == uid
        assert exc.action == "delete"
        assert exc.resource == "leave_request"

    def test_str_contains_user_and_resource(self):
        uid = uuid4()
        exc = PermissionDenied(user_id=uid, action="approve", resource="claim")
        assert "approve" in str(exc)
        assert "claim" in str(exc)


class TestRequireRoleDecorator:
    @pytest.mark.asyncio
    async def test_allowed_call_passes_through(self):
        state = _make_state(user_id=str(uuid4()))

        @require_role(action="read", resource="user", scope="*")
        async def handler(state_obj):
            return "result"

        with patch("durgam.auth.decorators.can", return_value=True):
            result = await handler(state)
        assert result == "result"

    @pytest.mark.asyncio
    async def test_denied_call_raises_permission_denied(self):
        state = _make_state(user_id=str(uuid4()))

        @require_role(action="delete", resource="user", scope="*")
        async def handler(state_obj):
            return "result"

        with patch("durgam.auth.decorators.can", return_value=False):
            with pytest.raises(PermissionDenied):
                await handler(state)

    @pytest.mark.asyncio
    async def test_unauthenticated_raises_permission_denied(self):
        """Empty current_user_id must raise PermissionDenied without calling can()."""
        state = _make_state(user_id="")

        @require_role(action="read", resource="user", scope="*")
        async def handler(state_obj):
            return "result"

        with patch("durgam.auth.decorators.can") as mock_can:
            with pytest.raises(PermissionDenied):
                await handler(state)
        mock_can.assert_not_called()

    def test_decorator_marks_function_with_metadata(self):
        @require_role(action="approve", resource="leave_request", scope="department")
        async def handler(state_obj):
            return {}

        assert hasattr(handler, "_require_role")
        assert handler._require_role == ("approve", "leave_request", "department")


class TestPublicHandler:
    @pytest.mark.asyncio
    async def test_public_handler_passes_through(self):
        @public_handler
        async def login_handler(state_obj):
            return "logged_in"

        state = _make_state()
        result = await login_handler(state)
        assert result == "logged_in"

    def test_public_handler_marks_function(self):
        @public_handler
        async def login_handler(state_obj):
            return {}

        assert hasattr(login_handler, "_public_handler")
        assert login_handler._public_handler is True


class TestAuditActionDecorator:
    @pytest.mark.asyncio
    async def test_audit_row_written_after_success(self):
        state = _make_state(user_id=str(uuid4()), role_code="ADMIN")

        @audit_action(action="create", resource="thing")
        async def handler(state_obj):
            return {"resource_id": "t-1", "before": None, "after": {"x": 1}}

        with patch("durgam.auth.decorators.write_audit_row") as mock_write:
            await handler(state)

        mock_write.assert_called_once()
        call_kwargs = mock_write.call_args.kwargs
        assert call_kwargs["action"] == "create"
        assert call_kwargs["resource"] == "thing"
        assert call_kwargs["resource_id"] == "t-1"
        assert call_kwargs["before"] is None
        assert call_kwargs["after"] == {"x": 1}

    @pytest.mark.asyncio
    async def test_no_audit_row_on_exception(self):
        state = _make_state(user_id=str(uuid4()))

        @audit_action(action="delete", resource="thing")
        async def handler(state_obj):
            raise ValueError("boom")

        with patch("durgam.auth.decorators.write_audit_row") as mock_write:
            with pytest.raises(ValueError):
                await handler(state)

        mock_write.assert_not_called()

    @pytest.mark.asyncio
    async def test_unauthenticated_user_id_is_none_in_audit(self):
        """Unauthenticated (public) handlers may have no user_id; audit row still written."""
        state = _make_state(user_id="")

        @audit_action(action="login_attempt", resource="session")
        async def handler(state_obj):
            return {}

        with patch("durgam.auth.decorators.write_audit_row") as mock_write:
            await handler(state)

        call_kwargs = mock_write.call_args.kwargs
        assert call_kwargs["actor_user_id"] is None

    def test_decorator_marks_function_with_metadata(self):
        @audit_action(action="update", resource="profile")
        async def handler(state_obj):
            return {}

        assert hasattr(handler, "_audit_action")
        assert handler._audit_action == ("update", "profile")
