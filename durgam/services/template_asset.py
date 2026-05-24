"""TemplateAssetService — upload, replace, deactivate document templates (§9.3)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.config_anchors import TemplateAsset
from durgam.repositories.template_asset import TemplateAssetRepository
from durgam.services.org_exceptions import OrgServiceError
from durgam.services.upload import UploadService

log = structlog.get_logger(__name__)

VALID_TEMPLATE_TYPES = frozenset({"bos", "mom", "vac"})

_TYPE_MIME_MAP: dict[str, frozenset[str]] = {
    "bos": frozenset({
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }),
    "mom": frozenset({
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }),
    "vac": frozenset({
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }),
}

_MAX_SIZE_MB = 2


class TemplateError(OrgServiceError):
    pass


class TemplateAssetService:
    def __init__(
        self,
        repo: TemplateAssetRepository,
        upload_svc: UploadService,
    ) -> None:
        self._repo = repo
        self._upload_svc = upload_svc

    def list_all(self) -> list[TemplateAsset]:
        return self._repo.list_active_ordered()

    def get(self, record_id: UUID) -> TemplateAsset:
        row = self._repo.get_by_id(record_id)
        if row is None:
            raise TemplateError("Template not found.")
        return row

    def upload_template(
        self,
        template_type: str,
        data: bytes,
        original_name: str,
        mime_type: str,
        actor_id: UUID,
    ) -> TemplateAsset:
        template_type = template_type.strip().lower()
        if template_type not in VALID_TEMPLATE_TYPES:
            raise TemplateError(
                f"Invalid template type '{template_type}'. "
                f"Valid types: {', '.join(sorted(VALID_TEMPLATE_TYPES))}"
            )
        allowed_mimes = _TYPE_MIME_MAP[template_type]
        if mime_type not in allowed_mimes:
            raise TemplateError(
                f"File type '{mime_type}' is not allowed for '{template_type}' templates. "
                f"Accepted: {', '.join(sorted(allowed_mimes))}"
            )
        if len(data) > _MAX_SIZE_MB * 1024 * 1024:
            raise TemplateError(f"File exceeds the {_MAX_SIZE_MB} MB size limit.")

        existing = self._repo.get_active_by_type(template_type)
        if existing is not None:
            self._repo.soft_delete(existing, actor_id)
            log.info("template_replaced", old_id=str(existing.id), type=template_type)

        file_asset = self._upload_svc.upload(
            data, original_name, mime_type, actor_id, purpose="template",
        )

        now = datetime.now(UTC)
        row = TemplateAsset(
            template_type=template_type,
            file_id=file_asset.id,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        row = self._repo.save(row)
        log.info("template_uploaded", id=str(row.id), type=template_type, actor=str(actor_id))
        return row

    def soft_delete(self, record_id: UUID, actor_id: UUID) -> TemplateAsset:
        row = self.get(record_id)
        row = self._repo.soft_delete(row, actor_id)
        log.info("template_soft_deleted", id=str(record_id), actor=str(actor_id))
        return row
