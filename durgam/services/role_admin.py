"""RoleAdminService — admin-facing role CRUD and permission assignment (§9.2)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.identity import Permission, Role
from durgam.repositories.permission import PermissionRepository
from durgam.repositories.role import RoleRepository

log = structlog.get_logger(__name__)


class RoleAdminError(Exception):
    """Raised for user-visible role admin failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class RoleAdminService:
    def __init__(
        self,
        role_repo: RoleRepository,
        permission_repo: PermissionRepository,
    ) -> None:
        self._roles = role_repo
        self._perms = permission_repo

    def list_roles(self) -> list[Role]:
        return self._roles.list_active()

    def get_role(self, role_id: UUID) -> Role | None:
        return self._roles.get_by_id(role_id)

    def get_role_permissions(self, role_id: UUID) -> list[Permission]:
        return self._roles.get_permissions(role_id)

    def get_permissions_grouped(self) -> dict[str, list[Permission]]:
        return self._perms.list_grouped_by_resource()

    def create_role(
        self,
        code: str,
        name: str,
        level: int,
        description: str | None,
        actor_id: UUID,
    ) -> Role:
        code = code.strip().upper()
        name = name.strip()
        if not code:
            raise RoleAdminError("Role code is required.")
        if not name:
            raise RoleAdminError("Role name is required.")
        if self._roles.get_by_code(code) is not None:
            raise RoleAdminError(f"Role code '{code}' is already in use.")
        role = self._roles.create(code, name, level, description, actor_id)
        log.info("admin_role_created", role_id=str(role.id), code=code, actor=str(actor_id))
        return role

    def update_role(
        self,
        role_id: UUID,
        fields: dict,
        actor_id: UUID,
    ) -> Role:
        role = self._roles.get_by_id(role_id)
        if role is None:
            raise RoleAdminError("Role not found.")
        fields = {**fields, "updated_at": datetime.now(UTC), "updated_by": actor_id}
        for key, value in fields.items():
            setattr(role, key, value)
        self._roles._session.add(role)
        self._roles._session.flush()
        self._roles._session.refresh(role)
        log.info("admin_role_updated", role_id=str(role_id), actor=str(actor_id))
        return role

    def soft_delete_role(self, role_id: UUID, actor_id: UUID) -> Role:
        role = self._roles.get_by_id(role_id)
        if role is None:
            raise RoleAdminError("Role not found.")
        role = self._roles.soft_delete(role, actor_id)
        log.info("admin_role_soft_deleted", role_id=str(role_id), actor=str(actor_id))
        return role

    def update_permissions(
        self,
        role_id: UUID,
        permission_ids: list[UUID],
        actor_id: UUID,
    ) -> None:
        """Replace the permission set for a role."""
        role = self._roles.get_by_id(role_id)
        if role is None:
            raise RoleAdminError("Role not found.")
        # Validate all permission_ids exist.
        for pid in permission_ids:
            p = self._perms.get_by_id(pid)
            if p is None:
                raise RoleAdminError(f"Permission {pid} not found.")
        self._roles.replace_permissions(role_id, permission_ids, actor_id)
        log.info(
            "admin_role_permissions_updated",
            role_id=str(role_id),
            count=len(permission_ids),
            actor=str(actor_id),
        )
