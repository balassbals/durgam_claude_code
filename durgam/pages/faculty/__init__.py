"""Nav registration for Faculty module pages (M10)."""

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

register(
    NavEntry(
        label="My Education",
        href="/faculty/profile/education",
        icon="graduation-cap",
        group="Faculty",
        permission_action="write",
        permission_resource="faculty",
        permission_scope_type="own",
    )
)
