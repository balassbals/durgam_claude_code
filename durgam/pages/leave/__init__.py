from durgam.nav.registry import NavEntry, register

register(NavEntry(
    label="My Leave",
    href="/leave",
    icon="calendar-off",
    group="Personal",
    permission_action="create",
    permission_resource="leave_request",
))
