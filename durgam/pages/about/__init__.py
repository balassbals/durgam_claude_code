"""About module nav registration (M3).

Read-only pages visible to all authenticated users.
permission_action=None → no permission check, shown to everyone logged in.
"""

from durgam.nav.registry import NavEntry, register

register(NavEntry(
    label="University",
    href="/about/university",
    icon="info",
    group="About",
    permission_action=None,
))
register(NavEntry(
    label="Departments",
    href="/about/departments",
    icon="building-2",
    group="About",
    permission_action=None,
))
