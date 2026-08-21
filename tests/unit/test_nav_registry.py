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
            (e for e in all_entries if e.label == "Approvals" and e.href == "/approvals/inbox"),
            None,
        )
        assert approvals_entry is not None, "Approvals nav entry not registered"
        assert approvals_entry.permission_action == "approve"
        assert approvals_entry.permission_resource == "approval_request"

        user_id = uuid4()
        session = MagicMock()

        def _can_approve_only(*, user_id, action, resource, scope_type, scope_id, session, any_scope):
            return action == "approve" and resource == "approval_request"

        with patch("durgam.nav.registry.can", side_effect=_can_approve_only):
            visible = get_visible_entries(user_id, session)
        assert any(r["label"] == "Approvals" for r in visible)

        with patch("durgam.nav.registry.can", return_value=False):
            visible = get_visible_entries(user_id, session)
        assert not any(r["label"] == "Approvals" for r in visible)

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
        result = any(r["label"] == "Approvals" for r in visible)
        assert result is expected_visible, f"{role_label} visibility mismatch"

    def test_my_requests_nav_visible_to_all(self):
        """My Requests nav entry uses permission_action=None — visible to all."""
        all_entries = get_all()
        my_req_entry = next(
            (e for e in all_entries if e.label == "My Requests"),
            None,
        )
        assert my_req_entry is not None
        assert my_req_entry.permission_action is None


class TestFacultyNavGate:
    @classmethod
    def setup_class(cls):
        import durgam.pages.faculty  # noqa: F401 — triggers nav registration

    def test_faculty_profile_nav_entry_registered(self):
        """'My Profile' entry must be present in the registry after module import."""
        entries = get_all()
        entry = next(
            (e for e in entries if e.label == "My Profile" and e.href == "/faculty/profile"),
            None,
        )
        assert entry is not None, "'My Profile' nav entry not found in registry"

    def test_faculty_profile_gated_by_faculty_write_own(self):
        """Entry must be gated by faculty:write:own — visible only to FACULTY role holders."""
        entries = get_all()
        entry = next(
            (e for e in entries if e.label == "My Profile" and e.href == "/faculty/profile"),
            None,
        )
        assert entry is not None
        assert entry.permission_action == "write"
        assert entry.permission_resource == "faculty"
        assert entry.permission_scope_type == "own"

    def test_faculty_profile_nav_group_is_faculty(self):
        """Entry must be in the 'Faculty' nav group."""
        entries = get_all()
        entry = next(
            (e for e in entries if e.label == "My Profile" and e.href == "/faculty/profile"),
            None,
        )
        assert entry is not None
        assert entry.group == "Faculty"

    def test_faculty_education_nav_entry_registered(self):
        """'My Education' entry must be present after module import."""
        entries = get_all()
        entry = next(
            (
                e
                for e in entries
                if e.label == "My Education" and e.href == "/faculty/profile/education"
            ),
            None,
        )
        assert entry is not None, "'My Education' nav entry not found in registry"
        assert entry.permission_action == "write"
        assert entry.permission_resource == "faculty"
        assert entry.permission_scope_type == "own"
        assert entry.group == "Faculty"

    def test_faculty_experience_nav_entry_registered(self):
        """'My Experience' entry must be present after module import."""
        entries = get_all()
        entry = next(
            (
                e
                for e in entries
                if e.label == "My Experience" and e.href == "/faculty/profile/experience"
            ),
            None,
        )
        assert entry is not None, "'My Experience' nav entry not found in registry"
        assert entry.permission_action == "write"
        assert entry.permission_resource == "faculty"
        assert entry.permission_scope_type == "own"
        assert entry.group == "Faculty"

    def test_faculty_expertise_nav_entry_registered(self):
        """'My Expertise' entry must be present after module import."""
        entries = get_all()
        entry = next(
            (
                e
                for e in entries
                if e.label == "My Expertise" and e.href == "/faculty/profile/expertise"
            ),
            None,
        )
        assert entry is not None, "'My Expertise' nav entry not found in registry"
        assert entry.permission_action == "write"
        assert entry.permission_resource == "faculty"
        assert entry.permission_scope_type == "own"
        assert entry.group == "Faculty"

    def test_faculty_documents_nav_entry_registered(self):
        """'My Documents' entry must be present after module import."""
        entries = get_all()
        entry = next(
            (
                e
                for e in entries
                if e.label == "My Documents" and e.href == "/faculty/profile/documents"
            ),
            None,
        )
        assert entry is not None, "'My Documents' nav entry not found in registry"
        assert entry.permission_action == "write"
        assert entry.permission_resource == "faculty"
        assert entry.permission_scope_type == "own"
        assert entry.group == "Faculty"

    def test_raise_fdp_request_nav_entry_registered(self):
        """Phase 6: 'Raise FDP Request' deep-link under Faculty, faculty:write:own."""
        entries = get_all()
        entry = next(
            (
                e
                for e in entries
                if e.label == "Raise FDP Request"
                and e.href == "/approvals/submit?process=faculty_fdp"
            ),
            None,
        )
        assert entry is not None, "'Raise FDP Request' nav entry not found in registry"
        assert entry.permission_action == "write"
        assert entry.permission_resource == "faculty"
        assert entry.permission_scope_type == "own"
        assert entry.group == "Faculty"

    def test_faculty_directory_nav_entry_registered(self):
        """Phase 8A: 'Faculty Directory' peer-view entry under Faculty, faculty:read."""
        entries = get_all()
        entry = next(
            (
                e
                for e in entries
                if e.label == "Faculty Directory" and e.href == "/faculty"
            ),
            None,
        )
        assert entry is not None, "'Faculty Directory' nav entry not found in registry"
        assert entry.permission_action == "read"
        assert entry.permission_resource == "faculty"
        assert entry.group == "Faculty"

    def test_faculty_requests_nav_entry_registered(self):
        """Phase 8B: 'Faculty Requests' overlay entry under Faculty, faculty:write:own."""
        entries = get_all()
        entry = next(
            (
                e
                for e in entries
                if e.label == "Faculty Requests" and e.href == "/faculty/requests"
            ),
            None,
        )
        assert entry is not None, "'Faculty Requests' nav entry not found in registry"
        assert entry.permission_action == "write"
        assert entry.permission_resource == "faculty"
        assert entry.permission_scope_type == "own"
        assert entry.group == "Faculty"


class TestAdminFacultyNavGate:
    @classmethod
    def setup_class(cls):
        import durgam.pages.admin  # noqa: F401 — triggers admin nav registration

    def test_admin_faculty_nav_entry_registered(self):
        """'Faculty' admin directory entry gated by faculty:read:* (P6)."""
        entries = get_all()
        entry = next(
            (
                e
                for e in entries
                if e.label == "Faculty" and e.href == "/admin/faculty"
            ),
            None,
        )
        assert entry is not None, "'Faculty' admin nav entry not found in registry"
        assert entry.permission_action == "read"
        assert entry.permission_resource == "faculty"
        assert entry.group == "Admin"


class TestGroupOrderingPhase2a:
    """M10.5 Phase 2a — NavEntry.order + GROUP_ORDER sorting in get_visible_entries()."""

    def test_order_defaults_to_100(self):
        entry = NavEntry(label="Def Order Entry", href="/def-order-2a")
        assert entry.order == 100

    def test_group_order_constant_matches_spec(self):
        from durgam.nav.registry import GROUP_ORDER

        assert GROUP_ORDER == (
            "Personal", "Faculty", "Approvals", "Announcements", "Admin", "Config", "About",
        )

    def test_entries_sorted_within_group_by_order_ascending(self):
        register(NavEntry(label="ZZZ Second 2a", href="/zzz-second-2a",
                           group="TestGroupA2a", order=20))
        register(NavEntry(label="AAA First 2a", href="/aaa-first-2a",
                           group="TestGroupA2a", order=10))
        user_id = uuid4()
        session = MagicMock()
        with patch("durgam.nav.registry.can", return_value=True):
            visible = get_visible_entries(user_id, session)
        group_labels = [r["label"] for r in visible if r["group"] == "TestGroupA2a"]
        assert group_labels == ["AAA First 2a", "ZZZ Second 2a"]

    def test_entries_with_tied_order_sort_by_label(self):
        register(NavEntry(label="Zeta Tie 2a", href="/zeta-tie-2a", group="TestGroupB2a"))
        register(NavEntry(label="Alpha Tie 2a", href="/alpha-tie-2a", group="TestGroupB2a"))
        user_id = uuid4()
        session = MagicMock()
        with patch("durgam.nav.registry.can", return_value=True):
            visible = get_visible_entries(user_id, session)
        group_labels = [r["label"] for r in visible if r["group"] == "TestGroupB2a"]
        assert group_labels == ["Alpha Tie 2a", "Zeta Tie 2a"]

    def test_group_order_sequence_respected(self):
        """Admin sorts before Config per GROUP_ORDER, regardless of registration order."""
        register(NavEntry(label="Test Config Entry 2a", href="/test-config-2a", group="Config"))
        register(NavEntry(label="Test Admin Entry 2a", href="/test-admin-2a", group="Admin"))
        user_id = uuid4()
        session = MagicMock()
        with patch("durgam.nav.registry.can", return_value=True):
            visible = get_visible_entries(user_id, session)
        labels_in_order = [r["label"] for r in visible]
        assert (
            labels_in_order.index("Test Admin Entry 2a")
            < labels_in_order.index("Test Config Entry 2a")
        )

    def test_unlisted_groups_sort_after_listed_groups(self):
        register(NavEntry(label="Unlisted Group Entry 2a", href="/unlisted-entry-2a",
                           group="ZzzUnlistedGroup2a"))
        register(NavEntry(label="Listed About Entry 2a", href="/listed-about-2a", group="About"))
        user_id = uuid4()
        session = MagicMock()
        with patch("durgam.nav.registry.can", return_value=True):
            visible = get_visible_entries(user_id, session)
        labels_in_order = [r["label"] for r in visible]
        assert (
            labels_in_order.index("Listed About Entry 2a")
            < labels_in_order.index("Unlisted Group Entry 2a")
        )

    def test_unlisted_groups_sort_alphabetically_among_themselves(self):
        register(NavEntry(label="Unlisted B Entry 2a", href="/unlisted-b-2a", group="ZUnlisted2a"))
        register(NavEntry(label="Unlisted A Entry 2a", href="/unlisted-a-2a",
                           group="AUnlistedGroupZ2a"))
        user_id = uuid4()
        session = MagicMock()
        with patch("durgam.nav.registry.can", return_value=True):
            visible = get_visible_entries(user_id, session)
        labels_in_order = [r["label"] for r in visible]
        assert (
            labels_in_order.index("Unlisted A Entry 2a")
            < labels_in_order.index("Unlisted B Entry 2a")
        )

    def test_visible_entry_includes_order_field(self):
        register(NavEntry(label="Order Field Entry 2a", href="/order-field-2a",
                           group="TestGroupC2a", order=42))
        user_id = uuid4()
        session = MagicMock()
        with patch("durgam.nav.registry.can", return_value=True):
            visible = get_visible_entries(user_id, session)
        entry = next(r for r in visible if r["label"] == "Order Field Entry 2a")
        assert entry["order"] == "42"

    def test_single_entry_group_returns_correctly(self):
        register(NavEntry(label="Solo Entry 2a", href="/solo-entry-2a", group="SoloTestGroup2a"))
        user_id = uuid4()
        session = MagicMock()
        with patch("durgam.nav.registry.can", return_value=True):
            visible = get_visible_entries(user_id, session)
        solo_entries = [r for r in visible if r["group"] == "SoloTestGroup2a"]
        assert len(solo_entries) == 1
        assert solo_entries[0]["label"] == "Solo Entry 2a"

    def test_permission_filtering_unaffected_by_ordering(self):
        register(NavEntry(
            label="Gated Order Entry 2a", href="/gated-order-2a", group="TestGroupD2a",
            permission_action="write", permission_resource="some_resource_xyz_2a",
        ))
        user_id = uuid4()
        session = MagicMock()
        with patch("durgam.nav.registry.can", return_value=False):
            visible = get_visible_entries(user_id, session)
        assert not any(r["label"] == "Gated Order Entry 2a" for r in visible)
