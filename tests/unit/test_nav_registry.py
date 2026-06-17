"""Unit tests for the nav registry (M2 pattern)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from durgam.nav.registry import NavEntry, get_all, get_visible_entries, register


class TestRegister:
    def test_registered_entry_appears_in_get_all(self):
        initial_count = len(get_all())
        entry = NavEntry(label="Test", href="/test", permission_action=None)
        register(entry)
        assert entry in get_all()
        assert len(get_all()) == initial_count + 1


class TestGetVisibleEntries:
    def test_public_entry_always_visible(self):
        """An entry with permission_action=None is visible to any authenticated user."""
        entry = NavEntry(label="Public", href="/public", permission_action=None)
        register(entry)

        user_id = uuid4()
        session = MagicMock()

        with patch("durgam.nav.registry.can", return_value=True):
            results = get_visible_entries(user_id, session)

        labels = [r["label"] for r in results]
        assert "Public" in labels

    def test_permission_checked_entry_shown_when_granted(self):
        entry = NavEntry(
            label="Admin Perm",
            href="/admin-perm",
            permission_action="read",
            permission_resource="user",
        )
        register(entry)

        user_id = uuid4()
        session = MagicMock()

        with patch("durgam.nav.registry.can", return_value=True):
            results = get_visible_entries(user_id, session)

        assert any(r["label"] == "Admin Perm" for r in results)

    def test_permission_checked_entry_hidden_when_denied(self):
        entry = NavEntry(
            label="Secret Section",
            href="/secret",
            permission_action="manage",
            permission_resource="system",
        )
        register(entry)

        user_id = uuid4()
        session = MagicMock()

        with patch("durgam.nav.registry.can", return_value=False):
            results = get_visible_entries(user_id, session)

        # "Secret Section" should not appear when can() returns False
        assert not any(r["label"] == "Secret Section" for r in results)


class TestApprovalsNavGate:
    @classmethod
    def setup_class(cls):
        import durgam.pages.approvals  # noqa: F401 — triggers nav registration

    def test_approvals_nav_gated_on_approve_permission(self):
        """Approvals nav entry uses permission_action='approve',
        permission_resource='approval_request'. A user with the permission
        sees it; a user without does not."""
        all_entries = get_all()
        approvals_entry = next(
            (e for e in all_entries if e.label == "Other Approvals" and e.href == "/approvals/inbox"),
            None,
        )
        assert approvals_entry is not None, "Other Approvals nav entry not registered"
        assert approvals_entry.permission_action == "approve"
        assert approvals_entry.permission_resource == "approval_request"

        user_id = uuid4()
        session = MagicMock()

        def _can_approve_only(*, user_id, action, resource, scope_type, scope_id, session, any_scope):
            return action == "approve" and resource == "approval_request"

        with patch("durgam.nav.registry.can", side_effect=_can_approve_only):
            visible = get_visible_entries(user_id, session)
        assert any(r["label"] == "Other Approvals" for r in visible)

        with patch("durgam.nav.registry.can", return_value=False):
            visible = get_visible_entries(user_id, session)
        assert not any(r["label"] == "Other Approvals" for r in visible)

    @pytest.mark.parametrize(
        "role_label, can_returns, expected_visible",
        [
            ("REGISTRAR", True, True),
            ("DEPUTY_REGISTRAR", True, True),
            ("REGISTRAR_OFFICE", False, False),
            ("VC_OFFICE", False, False),
            ("STUDENT", False, False),
        ],
        ids=[
            "registrar-sees-link",
            "deputy_registrar-sees-link",
            "registrar_office-hidden",
            "vc_office-hidden",
            "student-hidden",
        ],
    )
    def test_approvals_nav_visibility_by_role(
        self, role_label, can_returns, expected_visible
    ):
        """Approvals link visible only to roles holding approval_request:approve."""
        user_id = uuid4()
        session = MagicMock()
        with patch("durgam.nav.registry.can", return_value=can_returns):
            visible = get_visible_entries(user_id, session)
        result = any(r["label"] == "Other Approvals" for r in visible)
        assert result is expected_visible, f"{role_label} visibility mismatch"

    def test_my_requests_nav_visible_to_all(self):
        """My Requests nav entry uses permission_action=None — visible to all."""
        all_entries = get_all()
        my_req_entry = next(
            (e for e in all_entries if e.label == "Other Requests"),
            None,
        )
        assert my_req_entry is not None
        assert my_req_entry.permission_action is None
