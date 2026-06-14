"""Nav registration for /announcements (M9 Phase 6b)."""

from durgam.nav.registry import NavEntry, register

register(
    NavEntry(
        label="Announcements",
        href="/announcements",
        icon="megaphone",
        group="Announcements",
        permission_action=None,  # visible to all authenticated users
    )
)
