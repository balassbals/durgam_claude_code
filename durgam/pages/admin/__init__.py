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
    label="Faculty",
    href="/admin/faculty",
    icon="graduation-cap",
    group="Admin",
    permission_action="read",
    permission_resource="faculty",
))
register(NavEntry(
    label="Faculty Import",
    href="/admin/faculty/import",
    icon="file-up",
    group="Admin",
    permission_action="bulk_import",
    permission_resource="faculty",
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
# ── M8.1 nav entries ────────────────────────────────────────────────────────────
register(NavEntry(
    label="CL Credit Policy",
    href="/admin/leave/credit-policy",
    icon="calendar-plus",
    group="Admin",
    permission_action="configure",
    permission_resource="leave_credit_policy",
))
register(NavEntry(
    label="Balance Import",
    href="/admin/leave/balance-import",
    icon="file-up",
    group="Admin",
    permission_action="write",
    permission_resource="leave_balance_import",
))
register(NavEntry(
    label="Balance Edit",
    href="/admin/leave/balance-edit",
    icon="edit",
    group="Admin",
    permission_action="write",
    permission_resource="leave_balance_admin",
))
register(NavEntry(
    label="Request Edit",
    href="/admin/leave/request-edit",
    icon="edit-3",
    group="Admin",
    permission_action="write",
    permission_resource="leave_request_admin",
))
