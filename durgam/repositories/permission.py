"""PermissionRepository — read queries for the permissions table.

Permissions are seed-only at M2 (project policy). This repository provides
no create/update/delete methods — the permission catalog is managed via
scripts/seed.py only.
"""

from __future__ import annotations

from sqlmodel import Session, select

from durgam.models.identity import Permission
from durgam.repositories.base import BaseRepository


class PermissionRepository(BaseRepository[Permission]):
    def __init__(self, session: Session) -> None:
        super().__init__(Permission, session)

    def list_grouped_by_resource(self) -> dict[str, list[Permission]]:
        """Return all active permissions grouped by resource, sorted by action then scope."""
        perms = self._session.exec(
            select(Permission)
            .where(Permission.is_deleted == False)  # noqa: E712
            .order_by(Permission.resource, Permission.action, Permission.scope)
        ).all()
        grouped: dict[str, list[Permission]] = {}
        for perm in perms:
            grouped.setdefault(perm.resource, []).append(perm)
        return grouped

    def get_by_triple(self, resource: str, action: str, scope: str) -> Permission | None:
        return self._session.exec(
            select(Permission).where(
                Permission.resource == resource,
                Permission.action == action,
                Permission.scope == scope,
                Permission.is_deleted == False,  # noqa: E712
            )
        ).first()
