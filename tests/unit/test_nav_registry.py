"""Unit tests for the nav registry (M2 pattern)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

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
