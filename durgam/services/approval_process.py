"""ApprovalProcessService — CRUD for approval process templates."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog

from durgam.models.crosscutting import ApprovalProcess
from durgam.repositories.approval_process import ApprovalProcessRepository
from durgam.services.org_exceptions import OrgServiceError

log = structlog.get_logger(__name__)


class ApprovalProcessError(OrgServiceError):
    pass


class ApprovalProcessService:
    def __init__(self, repo: ApprovalProcessRepository) -> None:
        self._repo = repo

    def list_all(self) -> list[ApprovalProcess]:
        return self._repo.list_all_active()

    def get_by_code(self, code: str) -> ApprovalProcess | None:
        return self._repo.get_by_code(code)

    def create(
        self,
        *,
        code: str,
        title: str,
        requestor_role_codes: list[str] | None = None,
        channel_role_codes: list[str] | None = None,
        is_finance: bool = False,
        informational_cc_role_codes: list[str] | None = None,
        requires_upward_attachments: bool = False,
        requires_downward_attachments: bool = False,
        max_upward_attachments: int = 0,
        max_downward_attachments: int = 0,
        max_attachment_mb: int = 5,
        allowed_attachment_mime_types_json: list[str] | None = None,
        actor_id: UUID,
    ) -> ApprovalProcess:
        code = code.strip()
        title = title.strip()
        if not code:
            raise ApprovalProcessError("Approval process code is required.")
        if not title:
            raise ApprovalProcessError("Approval process title is required.")

        now = datetime.now(UTC)
        record = ApprovalProcess(
            code=code,
            title=title,
            requestor_role_codes=requestor_role_codes,
            channel_role_codes=channel_role_codes,
            is_finance=is_finance,
            informational_cc_role_codes=informational_cc_role_codes,
            requires_upward_attachments=requires_upward_attachments,
            requires_downward_attachments=requires_downward_attachments,
            max_upward_attachments=max_upward_attachments,
            max_downward_attachments=max_downward_attachments,
            max_attachment_mb=max_attachment_mb,
            allowed_attachment_mime_types_json=allowed_attachment_mime_types_json,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        record = self._repo.save(record)
        log.info("approval_process_created", id=str(record.id), actor=str(actor_id))
        return record

    def update(
        self, record_id: UUID, fields: dict, actor_id: UUID,
    ) -> ApprovalProcess:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise ApprovalProcessError("Approval process not found.")
        for key, value in fields.items():
            setattr(record, key, value)
        record.updated_by = actor_id
        record = self._repo.save(record)
        log.info("approval_process_updated", id=str(record_id), actor=str(actor_id))
        return record

    def soft_delete(self, record_id: UUID, actor_id: UUID) -> ApprovalProcess:
        record = self._repo.get_by_id(record_id)
        if record is None:
            raise ApprovalProcessError("Approval process not found.")
        record = self._repo.soft_delete(record, actor_id)
        log.info("approval_process_deleted", id=str(record_id), actor=str(actor_id))
        return record
