"""RoleRepository — CRUD and permission-assignment queries for roles."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import Session, select

from durgam.models.identity import Permission, Role, RolePermission
from durgam.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    def __init__(self, session: Session) -> None:
        super().__init__(Role, session)

    def get_by_code(self, code: str) -> Role | None:
        return self._session.exec(
            select(Role).where(Role.code == code, Role.is_deleted == False)  # noqa: E712
        ).first()

    def create(
        self,
        code: str,
        name: str,
        level: int,
        description: str | None,
        actor_id: UUID,
    ) -> Role:
        now = datetime.now(UTC)
        role = Role(
            code=code,
            name=name,
            level=level,
            description=description,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(role)
        self._session.flush()
        self._session.refresh(role)
        return role

    def get_permissions(self, role_id: UUID) -> list[Permission]:
        """Return all active permissions assigned to a role."""
        rp_rows = self._session.exec(
            select(RolePermission).where(RolePermission.role_id == role_id)
        ).all()
        perms = []
        for rp in rp_rows:
            perm = self._session.get(Permission, rp.permission_id)
            if perm is not None and not perm.is_deleted:
                perms.append(perm)
        return perms

    def replace_permissions(
        self, role_id: UUID, permission_ids: list[UUID], actor_id: UUID
    ) -> None:
        """Atomically replace all permissions for a role.

        Deletes existing RolePermission rows and inserts the new set.
        RolePermission has no soft-delete (it is a junction table).
        """
        existing = self._session.exec(
            select(RolePermission).where(RolePermission.role_id == role_id)
        ).all()
        for row in existing:
            self._session.delete(row)
        self._session.flush()

        for perm_id in permission_ids:
            self._session.add(RolePermission(role_id=role_id, permission_id=perm_id))
        self._session.flush()
