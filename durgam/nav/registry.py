"""Navigation registry — module-contributed nav entries, filtered per user.

Each module registers its nav entries at import time via register(). The
nav shell reads visible_nav_entries from BaseState (cached at login time)
so no DB calls happen during rendering.

Pattern established at M2 (see CLAUDE.md "Patterns established at M2").
M3 extension: permission_any supports OR-list gates for entries that must
be visible to multiple roles with different permission paths.
"""

from __future__ import annotations

from collections.abc import Callable
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
    # Single-gate: entry visible if user passes can(action, resource, scope_type).
    # None → visible to all authenticated users (no permission check needed).
    permission_action: str | None = None
    permission_resource: str | None = None
    permission_scope_type: str | None = None
    # OR-list gate: entry visible if user passes any of the (action, resource, scope_type)
    # tuples. When set, permission_action / permission_resource / permission_scope_type
    # are ignored. Use for entries that multiple roles should see via different permissions
    # (e.g. Vision & Mission: Registrar via university_vision_mission:write AND HoD via
    # department_vision_mission:write:department). Must be a tuple (hashable) not a list.
    permission_any: tuple[tuple[str, str, str | None], ...] | None = None
    # Dynamic check: OR'd with the static permission gate. Entry is visible if EITHER
    # the static check passes OR dynamic_check(user_id, session) returns True.
    dynamic_check: Callable[[UUID, Session], bool] | None = None


def register(entry: NavEntry) -> None:
    """Add a nav entry to the global registry. Called at module import time."""
    _entries.append(entry)


def get_all() -> list[NavEntry]:
    return list(_entries)


def get_visible_entries(user_id: UUID, session: Session) -> list[dict]:
    """Return serializable dicts for entries the user can see.

    All permission checks use any_scope=True (nav visibility semantics):
    an HoD scoped to DMACS should see Vision & Mission because they have
    department_vision_mission:write for THAT department. The page itself
    does the specific scope authorization — nav is a discovery signal only.
    """
    visible = []
    for entry in _entries:
        if entry.permission_any is not None:
            # OR-list: show if user passes any tuple.
            include = any(
                can(
                    user_id=user_id,
                    action=a,
                    resource=r,
                    scope_type=s,
                    scope_id=None,
                    session=session,
                    any_scope=True,
                )
                for (a, r, s) in entry.permission_any
            )
        elif entry.permission_action is None or entry.permission_resource is None:
            include = True
        else:
            include = can(
                user_id=user_id,
                action=entry.permission_action,
                resource=entry.permission_resource,
                scope_type=entry.permission_scope_type,
                scope_id=None,
                session=session,
                any_scope=True,  # nav = "has permission for any scope"
            )
        if not include and entry.dynamic_check is not None:
            include = entry.dynamic_check(user_id, session)
        if include:
            visible.append({
                "label": entry.label,
                "href": entry.href,
                "icon": entry.icon or "",
                "group": entry.group or "",
            })
    return visible
