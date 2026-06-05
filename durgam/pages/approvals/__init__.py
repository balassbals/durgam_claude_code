from durgam.nav.registry import NavEntry, register

register(NavEntry(
    label="My Requests",
    href="/approvals/my-requests",
    icon="file-check",
    group="Approvals",
    permission_action=None,
))

register(NavEntry(
    label="Approvals",
    href="/approvals/inbox",
    icon="inbox",
    group="Approvals",
    permission_action=None,
))
