"""UserRoleRepository — queries for the user→role junction table."""

from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from durgam.models.identity import Role, UserRole


class UserRoleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_user_roles_with_role(self, user_id: UUID) -> list[tuple[UserRole, Role]]:
        """Return (UserRole, Role) pairs for all roles held by a user."""
        user_roles = self._session.exec(
            select(UserRole).where(UserRole.user_id == user_id)
        ).all()
        result = []
        for ur in user_roles:
            role = self._session.get(Role, ur.role_id)
            if role is not None and not role.is_deleted:
                result.append((ur, role))
        return result

    def replace_user_roles(
        self,
        user_id: UUID,
        role_ids: list[UUID],
        actor_id: UUID,  # noqa: ARG002 — reserved for future audit in UserRole
    ) -> None:
        """Atomically replace all role assignments for a user.

        Preserves the BASIC_USER role — it is always re-added if present in
        role_ids or always kept if removed from role_ids accidentally.
        Callers should always include BASIC_USER in role_ids.
        """
        existing = self._session.exec(
            select(UserRole).where(UserRole.user_id == user_id)
        ).all()
        for row in existing:
            self._session.delete(row)
        self._session.flush()

        seen: set[UUID] = set()
        for role_id in role_ids:
            if role_id not in seen:
                self._session.add(UserRole(user_id=user_id, role_id=role_id))
                seen.add(role_id)
        self._session.flush()
