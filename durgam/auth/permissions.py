"""Permission resolution against the UserRole / RolePermission / Permission tables."""

from uuid import UUID

import structlog
from sqlmodel import Session, select

from durgam.models.identity import Permission, RolePermission, User, UserRole

log = structlog.get_logger(__name__)


class PermissionDenied(Exception):
    """Raised when a principal lacks the required permission."""

    def __init__(self, user_id: UUID | str, action: str, resource: str) -> None:
        super().__init__(f"User {user_id!s} cannot {action!r} on {resource!r}")
        self.user_id = user_id
        self.action = action
        self.resource = resource


def can(
    user_id: UUID,
    action: str,
    resource: str,
    scope_type: str | None,
    scope_id: UUID | None,
    session: Session,
) -> bool:
    """Return True iff the user holds a role that grants (action, resource, scope_type).

    Checks:
    1. User must exist and be active (not soft-deleted, not is_active=False).
    2. Walk user_roles → roles → role_permissions → permissions.
    3. A permission matches if resource, action match AND scope is '*' or matches scope_type.
    """
    user = session.exec(
        select(User).where(User.id == user_id, User.is_deleted == False, User.is_active == True)  # noqa: E712
    ).first()

    if user is None:
        log.warning("can(): user not found or inactive", user_id=str(user_id))
        return False

    user_role_rows = session.exec(select(UserRole).where(UserRole.user_id == user_id)).all()

    for user_role in user_role_rows:
        if user_role.scope_type is not None and scope_type is not None:
            if user_role.scope_type != scope_type:
                continue
            # A role with a specific scope_id only grants access when the check
            # provides the exact matching scope_id. scope_id=None in the check
            # means "unspecified scope" and must NOT match a role scoped to X.
            if user_role.scope_id is not None:
                if scope_id is None or user_role.scope_id != scope_id:
                    continue

        rp_rows = session.exec(
            select(RolePermission).where(RolePermission.role_id == user_role.role_id)
        ).all()

        for rp in rp_rows:
            perm = session.get(Permission, rp.permission_id)
            if perm is None or perm.is_deleted:
                continue
            if perm.action == action and perm.resource == resource:
                if perm.scope == "*" or perm.scope == scope_type:
                    log.debug(
                        "can(): granted",
                        user_id=str(user_id),
                        action=action,
                        resource=resource,
                        scope_type=scope_type,
                        role=str(user_role.role_id),
                    )
                    return True

    log.debug(
        "can(): denied",
        user_id=str(user_id),
        action=action,
        resource=resource,
        scope_type=scope_type,
    )
    return False
