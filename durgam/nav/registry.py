"""Navigation registry — module-contributed nav entries, filtered per user.

Each module registers its nav entries at import time via register(). The
nav shell reads visible_nav_entries from BaseState (cached at login time)
so no DB calls happen during rendering.

Pattern established at M2 (see CLAUDE.md "Patterns established at M2").
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlmodel import Session

from durgam.auth.permissions import can

_entries: list[NavEntry] = []


@dataclass(frozen=True)
class NavEntry:
    label: str
    href: str
    icon: str | None = None
    group: str | None = None
    # None → visible to all authenticated users (no permission check needed).
    permission_action: str | None = None
    permission_resource: str | None = None
    permission_scope_type: str | None = None


def register(entry: NavEntry) -> None:
    """Add a nav entry to the global registry. Called at module import time."""
    _entries.append(entry)


def get_all() -> list[NavEntry]:
    return list(_entries)


def get_visible_entries(user_id: UUID, session: Session) -> list[dict]:
    """Return serializable dicts for entries the user can see.

    Entries without a permission requirement are always included.
    Entries with a permission requirement are checked via can().
    """
    visible = []
    for entry in _entries:
        if entry.permission_action is None or entry.permission_resource is None:
            include = True
        else:
            include = can(
                user_id=user_id,
                action=entry.permission_action,
                resource=entry.permission_resource,
                scope_type=entry.permission_scope_type,
                scope_id=None,
                session=session,
            )
        if include:
            visible.append({
                "label": entry.label,
                "href": entry.href,
                "icon": entry.icon or "",
                "group": entry.group or "",
            })
    return visible
