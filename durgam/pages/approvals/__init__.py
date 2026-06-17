from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from durgam.nav.registry import NavEntry, register


def is_channel_approver(user_id: UUID, session: Session) -> bool:
    """True if user holds any role that appears in any active process's channel."""
    from durgam.models.crosscutting import ApprovalProcess
    from durgam.models.identity import Role, UserRole

    processes = session.exec(
        select(ApprovalProcess).where(
            ApprovalProcess.is_deleted == False,  # noqa: E712
        )
    ).all()
    user_role_codes = {
        r.code
        for r in session.exec(
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id,
                Role.is_deleted == False,  # noqa: E712
            )
        ).all()
    }
    return any(
        bool(set(p.channel_role_codes or []) & user_role_codes)
        for p in processes
    )


register(NavEntry(
    label="Other Requests",
    href="/approvals/my-requests",
    icon="file-check",
    group="Approvals",
    permission_action=None,
))

register(NavEntry(
    label="Other Approvals",
    href="/approvals/inbox",
    icon="inbox",
    group="Approvals",
    permission_action="approve",
    permission_resource="approval_request",
    dynamic_check=is_channel_approver,
))
