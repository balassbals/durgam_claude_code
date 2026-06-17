"""Approver-side faculty request pages (M10 Phase 7C).

Nav entry is gated behind the same `is_channel_approver` dynamic check as the
M7 approvals inbox — faculty_noc is one of the seeded processes and its channel
roles (HOD, REGISTRAR) are picked up by that check.
"""

from durgam.nav.registry import NavEntry, register
from durgam.pages.approvals import is_channel_approver

register(NavEntry(
    label="Faculty Inbox",
    href="/approver/inbox",
    icon="inbox",
    group="Faculty",
    permission_action="approve",
    permission_resource="approval_request",
    dynamic_check=is_channel_approver,
))
