"""LetterheadAssetService — upload, replace, deactivate letterheads (§9.3)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.config_anchors import LetterheadAsset
from durgam.models.crosscutting import FileAsset
from durgam.repositories.letterhead_asset import LetterheadAssetRepository
from durgam.services.org_exceptions import OrgServiceError
from durgam.services.upload import UploadService

log = structlog.get_logger(__name__)

_LETTERHEAD_MIMES = frozenset({
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
})
_MAX_SIZE_MB = 5


class LetterheadError(OrgServiceError):
    pass


class LetterheadAssetService:
    def __init__(
        self,
        repo: LetterheadAssetRepository,
        upload_svc: UploadService,
    ) -> None:
        self._repo = repo
        self._upload_svc = upload_svc

    def list_all(self) -> list[LetterheadAsset]:
        return self._repo.list_active_ordered()

    def get(self, record_id: UUID) -> LetterheadAsset:
        row = self._repo.get_by_id(record_id)
        if row is None:
            raise LetterheadError("Letterhead not found.")
        return row

    def upload_letterhead(
        self,
        role_code: str,
        data: bytes,
        original_name: str,
        mime_type: str,
        actor_id: UUID,
        *,
        scope_type: str | None = None,
        scope_id: UUID | None = None,
    ) -> LetterheadAsset:
        role_code = role_code.strip().upper()
        if not role_code:
            raise LetterheadError("Role code is required.")
        if mime_type not in _LETTERHEAD_MIMES:
            raise LetterheadError(
                f"File type '{mime_type}' is not allowed. "
                f"Accepted: {', '.join(sorted(_LETTERHEAD_MIMES))}"
            )
        if len(data) > _MAX_SIZE_MB * 1024 * 1024:
            raise LetterheadError(f"File exceeds the {_MAX_SIZE_MB} MB size limit.")
        self._check_scope_consistency(scope_type, scope_id)

        existing = self._repo.get_active_by_role_and_scope(role_code, scope_type, scope_id)
        if existing is not None:
            self._repo.soft_delete(existing, actor_id)
            log.info("letterhead_replaced", old_id=str(existing.id), role=role_code)

        file_asset = self._upload_svc.upload(
            data, original_name, mime_type, actor_id, purpose="letterhead",
        )

        now = datetime.now(UTC)
        row = LetterheadAsset(
            role_code=role_code,
            scope_type=scope_type,
            scope_id=scope_id,
            file_id=file_asset.id,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        row = self._repo.save(row)
        log.info("letterhead_uploaded", id=str(row.id), role=role_code, actor=str(actor_id))
        return row

    def soft_delete(self, record_id: UUID, actor_id: UUID) -> LetterheadAsset:
        row = self.get(record_id)
        row = self._repo.soft_delete(row, actor_id)
        log.info("letterhead_soft_deleted", id=str(record_id), actor=str(actor_id))
        return row

    @staticmethod
    def _check_scope_consistency(scope_type: str | None, scope_id: UUID | None) -> None:
        if (scope_type is None) != (scope_id is None):
            raise LetterheadError(
                "scope_type and scope_id must both be set or both be empty."
            )
