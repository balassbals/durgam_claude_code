"""Unit tests for @audit_action decorator — _set_audit pattern and _audit_pending lifecycle."""

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from durgam.auth.decorators import audit_action


class _FakeState:
    """Minimal State-like object for decorator tests."""

    def __init__(self):
        self.current_user_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        self.current_role_code = "ADMIN"
        self.request_id = "req-test"
        self.client_ip = "127.0.0.1"
        self.client_user_agent = "pytest"
        self._audit_pending: dict[str, Any] | None = None
        self._current_user_roles: list[dict[str, str | None]] = [
            {"role_code": "ADMIN", "scope_type": None, "scope_id": None},
        ]

    def _set_audit(
        self,
        *,
        resource_id: str | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        action: str | None = None,
    ) -> None:
        self._audit_pending = {
            "resource_id": resource_id,
            "before": before,
            "after": after,
        }
        if action is not None:
            self._audit_pending["action_override"] = action


class TestSetAudit:
    def test_populates_audit_pending(self):
        state = _FakeState()
        state._set_audit(resource_id="r1", before={"a": 1}, after={"a": 2})
        assert state._audit_pending is not None
        assert state._audit_pending["resource_id"] == "r1"
        assert state._audit_pending["before"] == {"a": 1}
        assert state._audit_pending["after"] == {"a": 2}

    def test_action_override(self):
        state = _FakeState()
        state._set_audit(resource_id="r1", action="login_failed")
        assert state._audit_pending["action_override"] == "login_failed"

    def test_no_action_override_by_default(self):
        state = _FakeState()
        state._set_audit(resource_id="r1")
        assert "action_override" not in state._audit_pending


def _run_decorated_handler(handler, state):
    """Run an async decorated handler synchronously, executing the audit in-band."""
    captured = {}

    def fake_write(**kwargs):
        captured.update(kwargs)
        return MagicMock(id=1)

    fake_session = MagicMock()

    with (
        patch("durgam.auth.decorators.write_audit_row", side_effect=fake_write),
        patch("durgam.auth.decorators._db_session") as mock_db,
        patch("asyncio.get_event_loop") as mock_loop,
    ):
        mock_db.return_value.__enter__ = MagicMock(return_value=fake_session)
        mock_db.return_value.__exit__ = MagicMock(return_value=False)

        # Make run_in_executor call the function synchronously
        mock_loop.return_value.run_in_executor = lambda _, fn: fn()

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(handler(state))
        finally:
            loop.close()

    return result, captured


class TestAuditActionDecorator:
    def test_reads_audit_pending(self):
        @audit_action(action="write", resource="campus")
        async def handler(state):
            state._set_audit(resource_id="c1", after={"name": "Main"})

        state = _FakeState()
        _, captured = _run_decorated_handler(handler, state)
        assert captured["resource_id"] == "c1"
        assert captured["after"] == {"name": "Main"}

    def test_resets_audit_pending_after_read(self):
        @audit_action(action="write", resource="campus")
        async def handler(state):
            state._set_audit(resource_id="c1")

        state = _FakeState()
        _run_decorated_handler(handler, state)
        assert state._audit_pending is None

    def test_action_override_used(self):
        @audit_action(action="login", resource="session")
        async def handler(state):
            state._set_audit(action="login_failed", resource_id="baduser")

        state = _FakeState()
        _, captured = _run_decorated_handler(handler, state)
        assert captured["action"] == "login_failed"

    def test_no_set_audit_produces_null_fields(self):
        @audit_action(action="login", resource="session")
        async def handler(state):
            pass

        state = _FakeState()
        _, captured = _run_decorated_handler(handler, state)
        assert captured["resource_id"] is None
        assert captured["before"] is None
        assert captured["after"] is None

    def test_actor_roles_json_passed(self):
        @audit_action(action="write", resource="campus")
        async def handler(state):
            state._set_audit(resource_id="c1")

        state = _FakeState()
        _, captured = _run_decorated_handler(handler, state)
        assert captured["actor_roles_json"] == [
            {"role_code": "ADMIN", "scope_type": None, "scope_id": None},
        ]

    def test_empty_roles_passed_as_none(self):
        @audit_action(action="login", resource="session")
        async def handler(state):
            pass

        state = _FakeState()
        state._current_user_roles = []
        _, captured = _run_decorated_handler(handler, state)
        assert captured["actor_roles_json"] is None

    def test_stale_audit_pending_cleared_before_handler(self):
        @audit_action(action="write", resource="campus")
        async def handler(state):
            pass

        state = _FakeState()
        state._audit_pending = {"resource_id": "STALE", "before": None, "after": None}
        _, captured = _run_decorated_handler(handler, state)
        assert captured["resource_id"] is None

    def test_handler_return_value_preserved(self):
        @audit_action(action="logout", resource="session")
        async def handler(state):
            return "redirect_result"

        state = _FakeState()
        result, _ = _run_decorated_handler(handler, state)
        assert result == "redirect_result"
