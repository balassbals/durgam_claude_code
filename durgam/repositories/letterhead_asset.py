"""Repository for LetterheadAsset — letterhead images bound to roles."""

from uuid import UUID

from sqlmodel import select

from durgam.models.config_anchors import LetterheadAsset
from durgam.repositories.base import BaseRepository


class LetterheadAssetRepository(BaseRepository[LetterheadAsset]):
    def __init__(self, session):
        super().__init__(LetterheadAsset, session)

    def list_active_ordered(self) -> list[LetterheadAsset]:
        stmt = (
            select(LetterheadAsset)
            .where(LetterheadAsset.is_deleted == False)  # noqa: E712
            .order_by(LetterheadAsset.role_code, LetterheadAsset.scope_type)
        )
        return list(self._session.exec(stmt).all())

    def get_active_by_role_and_scope(
        self,
        role_code: str,
        scope_type: str | None = None,
        scope_id: UUID | None = None,
    ) -> LetterheadAsset | None:
        stmt = select(LetterheadAsset).where(
            LetterheadAsset.role_code == role_code,
            LetterheadAsset.is_deleted == False,  # noqa: E712
        )
        if scope_type is None:
            stmt = stmt.where(LetterheadAsset.scope_type.is_(None))  # type: ignore[union-attr]
        else:
            stmt = stmt.where(
                LetterheadAsset.scope_type == scope_type,
                LetterheadAsset.scope_id == scope_id,
            )
        return self._session.exec(stmt).first()
