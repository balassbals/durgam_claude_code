"""Meta-test: every @require_role decorator in M9 state classes must reference
an (action, resource) pair that exists in the seeded permissions catalog.

Catches bugs like Phase 8b's 'write' action on 'announcement' — no such
Permission row existed; the correct action was 'soft_delete'.

This test does NOT use a DB fixture: it checks decorator metadata against a
hardcoded catalog extracted from scripts/seed.py lines 383-392. Keeping it
purely in-memory avoids fixture-ordering side effects (using seeded_session
initialises seeded_db_engine early, which leaves committed announcement
permission rows visible to subsequent db_session tests — triggering unique
constraint violations on test_auth.py::TestCan which inserts the same rows).
"""
from __future__ import annotations

from durgam.states.announcements import (
    AnnouncementBrowseState,
    AnnouncementComposerState,
    AnnouncementDetailState,
)
from durgam.states.config_announcement_category import AnnouncementCategoryConfigState
from durgam.states.config_announcement_composer import AnnouncementComposerConfigState
from durgam.states.config_audience_group import AudienceGroupConfigState

_M9_STATE_CLASSES = [
    AnnouncementBrowseState,
    AnnouncementComposerState,
    AnnouncementDetailState,
    AnnouncementComposerConfigState,
    AnnouncementCategoryConfigState,
    AudienceGroupConfigState,
]

# Announcement-module permission triples from scripts/seed.py lines 383-392.
# Format: (resource, action) — scope is checked separately by the @require_role
# decorator itself via can().
_SEEDED_ANNOUNCEMENT_PERMS: frozenset[tuple[str, str]] = frozenset(
    {
        ("announcement", "create"),
        ("announcement", "read"),
        ("announcement", "update"),
        ("announcement", "soft_delete"),
        ("announcement_composer_config", "read"),
        ("announcement_composer_config", "configure"),
        ("announcement_category", "read"),
        ("announcement_category", "configure"),
        ("audience_group", "read"),
        ("audience_group", "configure"),
    }
)


def test_every_m9_require_role_decorator_action_exists_in_permissions_seed() -> None:
    """Regression: every @require_role decorator's action must correspond to a
    seeded Permission row. Catches bugs like Phase 8b's 'write' on 'announcement'
    (no such permission row existed; correct was 'soft_delete').
    """
    mismatches: list[str] = []
    for state_cls in _M9_STATE_CLASSES:
        # Walk the MRO via __dict__ per class — avoids Reflex's __getattr__ which
        # returns synthetic Var objects for state vars rather than None.
        seen: set[str] = set()
        for klass in type.mro(state_cls):
            for attr_name, attr in klass.__dict__.items():
                if attr_name in seen or not callable(attr):
                    continue
                seen.add(attr_name)
                meta = getattr(attr, "_require_role", None)
                if not isinstance(meta, tuple) or len(meta) != 3:
                    continue
                action, resource, _scope = meta
                if (resource, action) not in _SEEDED_ANNOUNCEMENT_PERMS:
                    mismatches.append(
                        f"{state_cls.__name__}.{attr_name}: "
                        f"(resource={resource!r}, action={action!r}) "
                        f"not in seeded announcement permissions catalog"
                    )

    assert not mismatches, "\n".join(mismatches)
