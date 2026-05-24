"""FileAssetRepository — queries for the FileAsset cross-cutting model."""

from __future__ import annotations

from sqlmodel import select

from durgam.models.crosscutting import FileAsset
from durgam.repositories.base import BaseRepository


class FileAssetRepository(BaseRepository[FileAsset]):
    def __init__(self, session):
        super().__init__(FileAsset, session)

    def get_by_storage_key(self, storage_key: str) -> FileAsset | None:
        stmt = select(FileAsset).where(
            FileAsset.storage_key == storage_key,
            FileAsset.is_deleted == False,  # noqa: E712
        )
        return self._session.exec(stmt).first()
