from durgam.nav.registry import NavEntry, register

register(NavEntry(
    label="My Requests",
    href="/approvals/my-requests",
    icon="file-check",
    group="Approvals",
    permission_action=None,
))
