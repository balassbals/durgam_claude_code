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
    label="Import Users",
    href="/admin/import",
    icon="upload",
    group="Admin",
    permission_action="write",
    permission_resource="user",
))
