"""FileAssetRepository — queries for the FileAsset cross-cutting model."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
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

    def list_by_faculty_request_id(self, faculty_request_id: UUID) -> list[FileAsset]:
        """Return non-deleted FileAssets linked to a FacultyRequest via metadata_json."""
        stmt = select(FileAsset).where(
            FileAsset.is_deleted == False,  # noqa: E712
            FileAsset.purpose == "faculty_request_attachment",
            FileAsset.metadata_json.op("@>")(  # type: ignore[union-attr]
                sa.cast({"faculty_request_id": str(faculty_request_id)}, JSONB)
            ),
        )
        return list(self._session.exec(stmt).all())

    def list_by_announcement_id(self, announcement_id: UUID) -> list[FileAsset]:
        """Return non-deleted FileAssets linked to an announcement via metadata_json."""
        stmt = select(FileAsset).where(
            FileAsset.is_deleted == False,  # noqa: E712
            FileAsset.purpose == "announcement_attachment",
            FileAsset.metadata_json.op("@>")(  # type: ignore[union-attr]
                sa.cast({"announcement_id": str(announcement_id)}, JSONB)
            ),
        )
        return list(self._session.exec(stmt).all())
