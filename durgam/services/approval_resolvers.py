"""Approval resolver registry — M10 Phase 3A OR-set support (STEP-A).

Resolvers are pure functions: (ResolverContext, Session) → list[User].
They are registered in RESOLVERS by name.  The engine helper looks up
resolver_name from ApprovalStageOption rows and dispatches here.

ADDITIVE: this module does NOT modify the legacy approval path in
approval_routing.py or approval_request.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import UUID

from sqlmodel import Session, select

from durgam.models.department import Department
from durgam.models.identity import Role, User, UserRole


class UnknownResolverError(Exception):
    """Raised when a resolver_name is not in the RESOLVERS registry."""


@dataclass
class ResolverContext:
    """Contextual data passed to every resolver function."""

    requestor_user_id: UUID
    process_id: UUID
    stage_index: int
    # Optional free-form payload from the ApprovalRequest (e.g. NRF fields).
    payload: dict[str, Any] = field(default_factory=dict)


ResolverFn = Callable[[ResolverContext, Session], list[User]]


def _resolve_dept_head_at_requestor_campus(
    ctx: ResolverContext, session: Session
) -> list[User]:
    """Return active HODs whose department belongs to the requestor's campus.

    Walk the requestor's department-scoped roles to find their campus,
    then collect all HOD UserRole rows scoped to departments on that campus.
    """
    # Find the requestor's campus via their department-scoped roles.
    requestor_roles = session.exec(
        select(UserRole).where(
            UserRole.user_id == ctx.requestor_user_id,
            UserRole.scope_type == "department",
        )
    ).all()

    campus_ids: set[UUID] = set()
    for ur in requestor_roles:
        if ur.scope_id is not None:
            dept = session.get(Department, ur.scope_id)
            if dept is not None and not dept.is_deleted:
                campus_ids.add(dept.main_campus_id)

    if not campus_ids:
        return []

    # Collect all departments on those campuses.
    dept_stmt = select(Department).where(
        Department.is_deleted == False,  # noqa: E712
        Department.main_campus_id.in_(campus_ids),  # type: ignore[attr-defined]
    )
    depts = session.exec(dept_stmt).all()
    dept_ids = {d.id for d in depts}
    if not dept_ids:
        return []

    # Find HOD role.
    hod_role = session.exec(
        select(Role).where(Role.code == "HOD", Role.is_deleted == False)  # noqa: E712
    ).first()
    if hod_role is None:
        return []

    # Find HOD UserRoles scoped to those departments.
    hod_urs = session.exec(
        select(UserRole).where(
            UserRole.role_id == hod_role.id,
            UserRole.scope_type == "department",
            UserRole.scope_id.in_(dept_ids),  # type: ignore[attr-defined]
        )
    ).all()

    users: list[User] = []
    seen: set[UUID] = set()
    for ur in hod_urs:
        if ur.user_id in seen:
            continue
        user = session.exec(
            select(User).where(
                User.id == ur.user_id,
                User.is_deleted == False,  # noqa: E712
                User.is_active == True,  # noqa: E712
            )
        ).first()
        if user is not None:
            users.append(user)
            seen.add(ur.user_id)

    return users


RESOLVERS: dict[str, ResolverFn] = {
    "dept_head_at_requestor_campus": _resolve_dept_head_at_requestor_campus,
}


def resolve(name: str, ctx: ResolverContext, session: Session) -> list[User]:
    """Dispatch to the named resolver, raising UnknownResolverError if missing."""
    fn = RESOLVERS.get(name)
    if fn is None:
        raise UnknownResolverError(
            f"Resolver '{name}' not found in registry. "
            f"Known resolvers: {sorted(RESOLVERS)}"
        )
    return fn(ctx, session)
