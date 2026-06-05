"""Approval routing — scope-chain resolution and stage-approver matching.

Pure query functions, no DB writes. Used by ApprovalRequestService to
determine which users should approve at each stage of a channel.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlmodel import Session, select

from durgam.models.crosscutting import ApprovalProcess, ApprovalRequest
from durgam.models.department import Department
from durgam.models.identity import Role, User, UserRole

log = structlog.get_logger(__name__)


class ApprovalRoutingError(Exception):
    pass


def get_requestor_scope_chain(
    user_id: UUID,
    session: Session,
) -> list[tuple[str | None, UUID | None]]:
    """Return the user's scope chain as (scope_type, scope_id) tuples.

    Order: department scopes first, then school, then campus, then
    (None, None) for universitywide. Department-scoped roles derive
    implicit school and campus scopes from the Department model.
    """
    user_roles = session.exec(
        select(UserRole).where(UserRole.user_id == user_id)
    ).all()

    dept_ids: set[UUID] = set()
    school_ids: set[UUID] = set()
    campus_ids: set[UUID] = set()

    for ur in user_roles:
        if ur.scope_type == "department" and ur.scope_id is not None:
            dept_ids.add(ur.scope_id)
        elif ur.scope_type == "school" and ur.scope_id is not None:
            school_ids.add(ur.scope_id)
        elif ur.scope_type == "campus" and ur.scope_id is not None:
            campus_ids.add(ur.scope_id)

    for dept_id in list(dept_ids):
        dept = session.get(Department, dept_id)
        if dept is not None and not dept.is_deleted:
            school_ids.add(dept.school_id)
            campus_ids.add(dept.main_campus_id)

    chain: list[tuple[str | None, UUID | None]] = []
    for did in dept_ids:
        chain.append(("department", did))
    for sid in school_ids:
        chain.append(("school", sid))
    for cid in campus_ids:
        chain.append(("campus", cid))
    chain.append((None, None))

    return chain


def resolve_stage_approvers(
    *,
    request: ApprovalRequest,
    process: ApprovalProcess,
    session: Session,
) -> list[User]:
    """Return users who hold the channel role for the request's current stage.

    Walks the requestor's scope chain (dept → school → campus → universitywide)
    and returns users at the first tier where any holder exists.
    """
    channel = process.channel_role_codes or []
    stage_idx = request.current_stage - 1
    if stage_idx < 0 or stage_idx >= len(channel):
        raise ApprovalRoutingError(
            f"Stage {request.current_stage} out of bounds for channel "
            f"with {len(channel)} stages."
        )

    role_code = channel[stage_idx]

    role = session.exec(
        select(Role).where(
            Role.code == role_code,
            Role.is_deleted == False,  # noqa: E712
        )
    ).first()
    if role is None:
        log.warning("resolve_stage_approvers: role not found", role_code=role_code)
        return []

    scope_chain = get_requestor_scope_chain(request.requestor_user_id, session)

    for scope_type, scope_id in scope_chain:
        if scope_type is None:
            holders = session.exec(
                select(UserRole).where(
                    UserRole.role_id == role.id,
                    UserRole.scope_type.is_(None),  # type: ignore[union-attr]
                )
            ).all()
        else:
            holders = session.exec(
                select(UserRole).where(
                    UserRole.role_id == role.id,
                    UserRole.scope_type == scope_type,
                    UserRole.scope_id == scope_id,
                )
            ).all()

        if holders:
            users: list[User] = []
            seen_user_ids: set[UUID] = set()
            for h in holders:
                if h.user_id not in seen_user_ids:
                    user = session.exec(
                        select(User).where(
                            User.id == h.user_id,
                            User.is_deleted == False,  # noqa: E712
                            User.is_active == True,  # noqa: E712
                        )
                    ).first()
                    if user is not None:
                        users.append(user)
                        seen_user_ids.add(h.user_id)
            if users:
                log.info(
                    "resolve_stage_approvers: matched",
                    role_code=role_code,
                    scope_type=scope_type,
                    scope_id=str(scope_id) if scope_id else None,
                    count=len(users),
                )
                return users

    log.warning(
        "resolve_stage_approvers: no holder found",
        role_code=role_code,
        request_id=str(request.id),
    )
    return []
