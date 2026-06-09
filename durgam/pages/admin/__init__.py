"""Admin module nav registration (M2).

Import this module to register the admin nav entries. Called from durgam.py.
"""

from durgam.nav.registry import NavEntry, register

register(NavEntry(
    label="Admin",
    href="/admin",
    icon="settings",
    group="Admin",
    permission_action="read",
    permission_resource="user",
))
register(NavEntry(
    label="Users",
    href="/admin/users",
    icon="users",
    group="Admin",
    permission_action="read",
    permission_resource="user",
))
register(NavEntry(
    label="Roles",
    href="/admin/roles",
    icon="shield",
    group="Admin",
    permission_action="read",
    permission_resource="role",
))
register(NavEntry(
    label="Permissions",
    href="/admin/permissions",
    icon="key",
    group="Admin",
    permission_action="read",
    permission_resource="permission",
))
register(NavEntry(
    label="Bulk Import",
    href="/admin/import",
    icon="upload",
    group="Admin",
    permission_any=(
        ("write", "user", None),
        ("write", "program_import", None),
        ("write", "course_import", None),
    ),
))
# ── M8 nav entries ─────────────────────────────────────────────────────────────
register(NavEntry(
    label="Late Attendance",
    href="/admin/leave/late-attendance",
    icon="clock-alert",
    group="Admin",
    permission_action="write",
    permission_resource="late_attendance",
))
