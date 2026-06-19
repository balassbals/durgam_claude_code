"""Nav registration for /faculty/profile (M10 Phase P1)."""

from durgam.nav.registry import NavEntry, register

register(
    NavEntry(
        label="My Profile",
        href="/faculty/profile",
        icon="user",
        group="Faculty",
        permission_action="write",
        permission_resource="faculty",
        permission_scope_type="own",
    )
)
