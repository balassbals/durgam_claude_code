"""DocumentTemplateService — unified upload, replace, deactivate for letterheads + templates (E-005)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.config_anchors import DocumentTemplate
from durgam.repositories.document_template import DocumentTemplateRepository
from durgam.services.org_exceptions import OrgServiceError
from durgam.services.upload import UploadService

log = structlog.get_logger(__name__)

VALID_TEMPLATE_TYPES = frozenset({"bos", "mom", "vac"})
VALID_PURPOSES = frozenset({"letterhead"}) | VALID_TEMPLATE_TYPES

_LETTERHEAD_MIMES = frozenset({
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
})
_LETTERHEAD_MAX_MB = 5

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
_TEMPLATE_MAX_MB = 2


class DocumentTemplateError(OrgServiceError):
    pass


class DocumentTemplateService:
    def __init__(
        self,
        repo: DocumentTemplateRepository,
        upload_svc: UploadService,
    ) -> None:
        self._repo = repo
        self._upload_svc = upload_svc

    def list_letterheads(self) -> list[DocumentTemplate]:
        return self._repo.list_letterheads()

    def list_templates(self) -> list[DocumentTemplate]:
        return self._repo.list_templates()

    def get(self, record_id: UUID) -> DocumentTemplate:
        row = self._repo.get_by_id(record_id)
        if row is None:
            raise DocumentTemplateError("Document template not found.")
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
    ) -> DocumentTemplate:
        role_code = role_code.strip().upper()
        if not role_code:
            raise DocumentTemplateError("Role code is required.")
        if mime_type not in _LETTERHEAD_MIMES:
            raise DocumentTemplateError(
                f"File type '{mime_type}' is not allowed. "
                f"Accepted: {', '.join(sorted(_LETTERHEAD_MIMES))}"
            )
        if len(data) > _LETTERHEAD_MAX_MB * 1024 * 1024:
            raise DocumentTemplateError(
                f"File exceeds the {_LETTERHEAD_MAX_MB} MB size limit."
            )
        self._check_scope_consistency(scope_type, scope_id)

        existing = self._repo.get_letterhead_by_role_and_scope(
            role_code, scope_type, scope_id
        )
        if existing is not None:
            self._repo.soft_delete(existing, actor_id)
            log.info("letterhead_replaced", old_id=str(existing.id), role=role_code)

        file_asset = self._upload_svc.upload(
            data, original_name, mime_type, actor_id, purpose="letterhead",
        )

        now = datetime.now(UTC)
        row = DocumentTemplate(
            purpose="letterhead",
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

    def upload_template(
        self,
        template_type: str,
        data: bytes,
        original_name: str,
        mime_type: str,
        actor_id: UUID,
    ) -> DocumentTemplate:
        template_type = template_type.strip().lower()
        if template_type not in VALID_TEMPLATE_TYPES:
            raise DocumentTemplateError(
                f"Invalid template type '{template_type}'. "
                f"Valid types: {', '.join(sorted(VALID_TEMPLATE_TYPES))}"
            )
        allowed_mimes = _TYPE_MIME_MAP[template_type]
        if mime_type not in allowed_mimes:
            raise DocumentTemplateError(
                f"File type '{mime_type}' is not allowed for '{template_type}' templates. "
                f"Accepted: {', '.join(sorted(allowed_mimes))}"
            )
        if len(data) > _TEMPLATE_MAX_MB * 1024 * 1024:
            raise DocumentTemplateError(
                f"File exceeds the {_TEMPLATE_MAX_MB} MB size limit."
            )

        existing = self._repo.get_template_by_type(template_type)
        if existing is not None:
            self._repo.soft_delete(existing, actor_id)
            log.info("template_replaced", old_id=str(existing.id), type=template_type)

        file_asset = self._upload_svc.upload(
            data, original_name, mime_type, actor_id, purpose="template",
        )

        now = datetime.now(UTC)
        row = DocumentTemplate(
            purpose=template_type,
            role_code=None,
            scope_type=None,
            scope_id=None,
            file_id=file_asset.id,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        row = self._repo.save(row)
        log.info("template_uploaded", id=str(row.id), type=template_type, actor=str(actor_id))
        return row

    def soft_delete(self, record_id: UUID, actor_id: UUID) -> DocumentTemplate:
        row = self.get(record_id)
        row = self._repo.soft_delete(row, actor_id)
        log.info("document_template_soft_deleted", id=str(record_id), actor=str(actor_id))
        return row

    @staticmethod
    def _check_scope_consistency(scope_type: str | None, scope_id: UUID | None) -> None:
        if (scope_type is None) != (scope_id is None):
            raise DocumentTemplateError(
                "scope_type and scope_id must both be set or both be empty."
            )
