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
    """Q4a fallback chain: HoD → AhoD → [] for the requestor's specific dept+campus.

    Uses Faculty.department_id and Faculty.campus_id (Phase 1A Faculty model) to
    identify the requestor's specific dept and campus. Returns at most ONE user:
    the HoD scoped to that dept whose Faculty.campus_id matches the requestor's;
    if no such HoD, the AhoD with the same filter; if neither, empty list.

    Note: UserRole has no is_deleted column (plain SQLModel junction, no
    TimestampedSoftDelete). There is no soft-delete filter on UserRole rows.
    """
    from durgam.models.faculty import Faculty

    # 1. Look up requestor's Faculty row for their specific dept + campus.
    faculty = session.exec(
        select(Faculty).where(
            Faculty.user_id == ctx.requestor_user_id,
            Faculty.is_deleted == False,  # noqa: E712
        )
    ).first()

    if faculty is None or faculty.department_id is None or faculty.campus_id is None:
        return []

    dept_id = faculty.department_id
    campus_id = faculty.campus_id

    # 2. Try HoD first, then AhoD.  Candidate must hold the role scoped to the
    #    requestor's exact dept AND have a Faculty record at the requestor's campus.
    for role_code in ("HOD", "AHOD"):
        role = session.exec(
            select(Role).where(
                Role.code == role_code,
                Role.is_deleted == False,  # noqa: E712
            )
        ).first()
        if role is None:
            continue

        stmt = (
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Faculty, Faculty.user_id == User.id)
            .where(UserRole.role_id == role.id)
            .where(UserRole.scope_type == "department")
            .where(UserRole.scope_id == dept_id)
            .where(User.is_deleted == False)  # noqa: E712
            .where(User.is_active == True)  # noqa: E712
            .where(Faculty.campus_id == campus_id)
            .where(Faculty.is_deleted == False)  # noqa: E712
        )
        result = session.exec(stmt).first()
        if result:
            return [result]

    return []


def _resolve_director_at_requestor_campus(
    ctx: ResolverContext, session: Session
) -> list[User]:
    """Resolve DIRECTOR role at requestor's Faculty.campus_id (partial E-019, Phase 5F).

    Returns all users holding DIRECTOR role (campus-scoped) whose Faculty.campus_id
    matches the requestor's Faculty.campus_id. Returns [] if requestor has no Faculty
    record or no DIRECTOR role exists in DB.
    """
    from durgam.models.faculty import Faculty

    faculty = session.exec(
        select(Faculty).where(
            Faculty.user_id == ctx.requestor_user_id,
            Faculty.is_deleted == False,  # noqa: E712
        )
    ).first()

    if faculty is None or faculty.campus_id is None:
        return []

    campus_id = faculty.campus_id

    role = session.exec(
        select(Role).where(
            Role.code == "DIRECTOR",
            Role.is_deleted == False,  # noqa: E712
        )
    ).first()
    if role is None:
        return []

    stmt = (
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Faculty, Faculty.user_id == User.id)
        .where(UserRole.role_id == role.id)
        .where(UserRole.scope_type == "campus")
        .where(UserRole.scope_id == campus_id)
        .where(User.is_deleted == False)  # noqa: E712
        .where(User.is_active == True)  # noqa: E712
        .where(Faculty.campus_id == campus_id)
        .where(Faculty.is_deleted == False)  # noqa: E712
    )
    return list(session.exec(stmt).all())


def _resolve_dean_at_requestor_campus(
    ctx: ResolverContext, session: Session
) -> list[User]:
    """Resolve DEAN role at requestor's Faculty.campus_id (partial E-019, Phase 5F).

    Returns all users holding DEAN role whose Faculty.campus_id matches the
    requestor's Faculty.campus_id. Multiple Deans at the same campus all qualify;
    the engine OR-set machinery routes to all of them and any can act.
    DEAN is school-scoped (UserRole); campus matching is via Faculty.campus_id.
    Returns [] if requestor has no Faculty record or no DEAN role exists in DB.
    """
    from durgam.models.faculty import Faculty

    faculty = session.exec(
        select(Faculty).where(
            Faculty.user_id == ctx.requestor_user_id,
            Faculty.is_deleted == False,  # noqa: E712
        )
    ).first()

    if faculty is None or faculty.campus_id is None:
        return []

    campus_id = faculty.campus_id

    role = session.exec(
        select(Role).where(
            Role.code == "DEAN",
            Role.is_deleted == False,  # noqa: E712
        )
    ).first()
    if role is None:
        return []

    stmt = (
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Faculty, Faculty.user_id == User.id)
        .where(UserRole.role_id == role.id)
        .where(User.is_deleted == False)  # noqa: E712
        .where(User.is_active == True)  # noqa: E712
        .where(Faculty.campus_id == campus_id)
        .where(Faculty.is_deleted == False)  # noqa: E712
    )
    return list(session.exec(stmt).all())


RESOLVERS: dict[str, ResolverFn] = {
    "dept_head_at_requestor_campus": _resolve_dept_head_at_requestor_campus,
    "director_at_requestor_campus": _resolve_director_at_requestor_campus,
    "dean_at_requestor_campus": _resolve_dean_at_requestor_campus,
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
