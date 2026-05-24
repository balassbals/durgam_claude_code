"""UploadService — validate → scan → store → record pipeline (§6.1)."""

from __future__ import annotations

import abc
import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog

from durgam.models.crosscutting import FileAsset
from durgam.repositories.file_asset import FileAssetRepository
from durgam.storage.backend import StorageBackend

log = structlog.get_logger(__name__)

DEFAULT_ALLOWED_MIMES: frozenset[str] = frozenset(
    {
        "image/png",
        "image/jpeg",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
)

DEFAULT_MAX_SIZE_MB = 10


class UploadError(Exception):
    pass


# ── Scanner interface (injectable; ClamAV drop-in at M20) ────────────────────


class FileScanner(abc.ABC):
    @abc.abstractmethod
    def scan(self, data: bytes, filename: str) -> None:
        """Raise UploadError if the file is infected or scan fails."""
        ...


class NoOpScanner(FileScanner):
    def scan(self, data: bytes, filename: str) -> None:
        log.info("clamav_scan_skipped", filename=filename, size=len(data))


# ── Service ──────────────────────────────────────────────────────────────────


class UploadService:
    def __init__(
        self,
        file_repo: FileAssetRepository,
        backend: StorageBackend,
        *,
        scanner: FileScanner | None = None,
        allowed_mimes: frozenset[str] | None = None,
        max_size_mb: int | None = None,
    ) -> None:
        self._repo = file_repo
        self._backend = backend
        self._scanner = scanner or NoOpScanner()
        self._allowed_mimes = allowed_mimes or DEFAULT_ALLOWED_MIMES
        self._max_size_mb = max_size_mb or DEFAULT_MAX_SIZE_MB

    def upload(
        self,
        data: bytes,
        original_name: str,
        mime_type: str,
        actor_id: UUID,
        *,
        purpose: str | None = None,
    ) -> FileAsset:
        self._validate_mime(mime_type)
        self._validate_size(data)
        self._scanner.scan(data, original_name)

        sha256 = hashlib.sha256(data).hexdigest()
        storage_key = uuid4().hex
        self._backend.put(storage_key, data, mime_type)

        now = datetime.now(UTC)
        asset = FileAsset(
            storage_key=storage_key,
            original_name=original_name,
            mime_type=mime_type,
            size_bytes=len(data),
            sha256=sha256,
            owner_user_id=actor_id,
            purpose=purpose,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        asset = self._repo.save(asset)
        log.info(
            "file_uploaded",
            file_id=str(asset.id),
            key=storage_key,
            mime=mime_type,
            size=len(data),
        )
        return asset

    def _validate_mime(self, mime_type: str) -> None:
        if mime_type not in self._allowed_mimes:
            raise UploadError(
                f"File type '{mime_type}' is not allowed. "
                f"Accepted: {', '.join(sorted(self._allowed_mimes))}"
            )

    def _validate_size(self, data: bytes) -> None:
        max_bytes = self._max_size_mb * 1024 * 1024
        if len(data) > max_bytes:
            raise UploadError(
                f"File exceeds the {self._max_size_mb} MB size limit."
            )
