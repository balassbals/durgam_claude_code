from durgam.nav.registry import NavEntry, register

register(NavEntry(
    label="My Requests",
    href="/faculty/requests",
    icon="file-text",
    group="Faculty",
    permission_action=None,
))
