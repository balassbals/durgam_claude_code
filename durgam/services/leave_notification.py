"""Leave-module notification resolution (M8.1 E-017).

Provides `resolve_withdrawal_notification_recipients` — the authoritative list of
users to notify when an approved leave is withdrawn post-approval.
"""
from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from durgam.models.identity import Role, User, UserRole

# Roles whose holders are NEVER included in withdrawal notifications.
_EXCLUDED_ROLE_CODES = frozenset(
    {"REGISTRAR", "REGISTRAR_OFFICE", "VC", "DEPUTY_DIRECTOR", "HOD_OFFICE", "AHOD_OFFICE"}
)

# Roles always included (in addition to HOD/AHOD).
_ALWAYS_INCLUDE_CODES = frozenset({"DIRECTOR", "DIRECTOR_OFFICE"})


def _users_with_role_code(code: str, session: Session) -> list[User]:
    return list(
        session.exec(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                Role.code == code,
                Role.is_deleted == False,  # noqa: E712
                User.is_active == True,  # noqa: E712
                User.is_deleted == False,  # noqa: E712
            )
        ).all()
    )


def resolve_withdrawal_notification_recipients(
    requestor_user_id: UUID,
    session: Session,
) -> list[User]:
    """Return the deduplicated list of users to notify on post-approval withdrawal.

    Resolution order:
    1. All active HOD role holders (any scope). If found, use these as the dept-head tier.
    2. Else: all active AHOD role holders (any scope). (Either HOD or AHOD — not both.)
    3. Always include all active DIRECTOR and DIRECTOR_OFFICE role holders.
    Excluded roles: REGISTRAR, REGISTRAR_OFFICE, VC, DEPUTY_DIRECTOR, HOD_OFFICE, AHOD_OFFICE.
    Deduplicates by user_id (same user in multiple roles appears once).

    NOTE: Until M10 ships the faculty→department assignment model, dept-scope filtering
    is not applied. All HOD/AHOD/DIRECTOR users are included regardless of scope.
    """
    # Step 1+2: dept-head tier (HOD or AHOD fallback)
    hod_users = _users_with_role_code("HOD", session)
    head_users = hod_users if hod_users else _users_with_role_code("AHOD", session)

    # Step 3: always include DIRECTOR and DIRECTOR_OFFICE
    director_users: list[User] = []
    for code in _ALWAYS_INCLUDE_CODES:
        director_users.extend(_users_with_role_code(code, session))

    # Deduplicate
    seen: set[UUID] = set()
    result: list[User] = []
    for u in head_users + director_users:
        if u.id not in seen:
            seen.add(u.id)
            result.append(u)
    return result
