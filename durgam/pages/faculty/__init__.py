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

register(
    NavEntry(
        label="My Experience",
        href="/faculty/profile/experience",
        icon="briefcase",
        group="Faculty",
        permission_action="write",
        permission_resource="faculty",
        permission_scope_type="own",
    )
)

register(
    NavEntry(
        label="My Expertise",
        href="/faculty/profile/expertise",
        icon="lightbulb",
        group="Faculty",
        permission_action="write",
        permission_resource="faculty",
        permission_scope_type="own",
    )
)

register(
    NavEntry(
        label="My Documents",
        href="/faculty/profile/documents",
        icon="file-text",
        group="Faculty",
        permission_action="write",
        permission_resource="faculty",
        permission_scope_type="own",
    )
)

# Phase 6: quick-access deep-link that pre-selects the FDP process on the unified
# submit page (/approvals/submit). Generic description-only payload per Q-P5.6;
# FDP-specific structured fields remain deferred to post-gate polish / M11.
register(
    NavEntry(
        label="Raise FDP Request",
        href="/approvals/submit?process=faculty_fdp",
        icon="file-plus",
        group="Faculty",
        permission_action="write",
        permission_resource="faculty",
        permission_scope_type="own",
    )
)
