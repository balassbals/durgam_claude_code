"""RoleEmailRepository — queries for the RoleEmail config entity."""

from __future__ import annotations

from uuid import UUID

from sqlmodel import select

from durgam.models.config_anchors import RoleEmail
from durgam.repositories.base import BaseRepository


class RoleEmailRepository(BaseRepository[RoleEmail]):
    def __init__(self, session):
        super().__init__(RoleEmail, session)

    def list_active_ordered(self) -> list[RoleEmail]:
        stmt = (
            select(RoleEmail)
            .where(RoleEmail.is_deleted == False)  # noqa: E712
            .order_by(RoleEmail.role_code, RoleEmail.scope_type)
        )
        return list(self._session.exec(stmt).all())

    def get_by_role_and_scope(
        self,
        role_code: str,
        scope_type: str | None,
        scope_id: UUID | None,
    ) -> RoleEmail | None:
        stmt = select(RoleEmail).where(
            RoleEmail.role_code == role_code,
            RoleEmail.is_deleted == False,  # noqa: E712
        )
        if scope_type is None:
            stmt = stmt.where(
                RoleEmail.scope_type.is_(None),  # type: ignore[union-attr]
            )
        else:
            stmt = stmt.where(
                RoleEmail.scope_type == scope_type,
                RoleEmail.scope_id == scope_id,
            )
        return self._session.exec(stmt).first()
