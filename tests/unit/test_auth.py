"""Pure unit tests for auth module — no database required.

Tests that need real DB queries (can(), audit row creation) live in
tests/integration/test_auth.py.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from durgam.auth.decorators import audit_action, require_role
from durgam.auth.permissions import PermissionDenied


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
    def test_allowed_call_passes_through(self):
        """When can() returns True the decorated function runs normally."""
        session_mock = MagicMock()
        user_id = uuid4()

        @require_role(action="read", resource="user", scope="*")
        def handler(**kwargs):
            return "result"

        with patch("durgam.auth.decorators.can", return_value=True):
            assert handler(user_id=user_id, session=session_mock) == "result"

    def test_denied_call_raises_permission_denied(self):
        """When can() returns False the decorator raises PermissionDenied."""
        session_mock = MagicMock()
        user_id = uuid4()

        @require_role(action="delete", resource="user", scope="*")
        def handler(**kwargs):
            return "result"

        with patch("durgam.auth.decorators.can", return_value=False):
            with pytest.raises(PermissionDenied):
                handler(user_id=user_id, session=session_mock)

    def test_decorator_marks_function_with_metadata(self):
        @require_role(action="approve", resource="leave_request", scope="department")
        def handler(**kwargs):
            return {}

        assert hasattr(handler, "_require_role")
        assert handler._require_role == ("approve", "leave_request", "department")


class TestAuditActionDecorator:
    def test_audit_row_written_after_success(self):
        user_id = uuid4()
        session_mock = MagicMock()

        @audit_action(action="create", resource="thing")
        def handler(**kwargs):
            return {"resource_id": "t-1", "before": None, "after": {"x": 1}}

        with patch("durgam.auth.decorators.write_audit_row") as mock_write:
            handler(user_id=user_id, session=session_mock)

        mock_write.assert_called_once()
        call_kwargs = mock_write.call_args.kwargs
        assert call_kwargs["action"] == "create"
        assert call_kwargs["resource"] == "thing"
        assert call_kwargs["resource_id"] == "t-1"
        assert call_kwargs["before"] is None
        assert call_kwargs["after"] == {"x": 1}

    def test_no_audit_row_on_exception(self):
        user_id = uuid4()
        session_mock = MagicMock()

        @audit_action(action="delete", resource="thing")
        def handler(**kwargs):
            raise ValueError("boom")

        with patch("durgam.auth.decorators.write_audit_row") as mock_write:
            with pytest.raises(ValueError):
                handler(user_id=user_id, session=session_mock)

        mock_write.assert_not_called()

    def test_decorator_marks_function_with_metadata(self):
        @audit_action(action="update", resource="profile")
        def handler(**kwargs):
            return {}

        assert hasattr(handler, "_audit_action")
        assert handler._audit_action == ("update", "profile")
