"""Cross-cutting infrastructure models: audit, files, notifications, approvals (§8.4)."""

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel

from .base import TimestampedSoftDelete

_TIMESTAMPTZ: type[Any] = cast(type[Any], sa.DateTime(timezone=True))


class AuditLog(SQLModel, table=True):
    """Append-only audit log — application DB role has INSERT + SELECT only."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        sa.Index("ix_audit_logs_actor_occurred_at", "actor_user_id", "occurred_at"),
        sa.Index("ix_audit_logs_resource", "resource", "resource_id"),
        sa.Index("ix_audit_logs_diff_json", "diff_json", postgresql_using="gin"),
        sa.Index("ix_audit_logs_actor_roles_gin", "actor_roles_json", postgresql_using="gin"),
    )

    id: int = Field(default=None, primary_key=True)
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=_TIMESTAMPTZ,
        nullable=False,
    )
    actor_user_id: UUID | None = Field(default=None)
    actor_role_code: str | None = Field(default=None, max_length=64)
    action: str = Field(max_length=64, nullable=False)
    resource: str = Field(max_length=64, nullable=False)
    resource_id: str | None = Field(default=None, max_length=128)
    request_id: str | None = Field(default=None, max_length=64)
    ip: str | None = Field(default=None, max_length=45)
    user_agent: str | None = Field(default=None, max_length=512)
    diff_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    actor_roles_json: list[dict[str, Any]] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )


class FileAsset(TimestampedSoftDelete, table=True):
    __tablename__ = "file_assets"

    storage_key: str = Field(max_length=512, nullable=False)
    original_name: str = Field(max_length=255, nullable=False)
    mime_type: str = Field(max_length=128, nullable=False)
    size_bytes: int = Field(nullable=False)
    sha256: str = Field(max_length=64, nullable=False)
    owner_user_id: UUID | None = Field(default=None, foreign_key="users.id")
    purpose: str | None = Field(default=None, max_length=64)
    metadata_json: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )


class Notification(TimestampedSoftDelete, table=True):
    __tablename__ = "notifications"
    __table_args__ = (
        sa.Index("ix_notifications_recipient_sent_at", "recipient_user_id", "sent_at"),
    )

    recipient_user_id: UUID = Field(foreign_key="users.id", nullable=False)
    channel: str = Field(max_length=16, nullable=False)  # in_app | email
    subject: str = Field(max_length=255, nullable=False)
    body_html: str | None = Field(default=None)
    body_text: str | None = Field(default=None)
    payload_json: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    sent_at: datetime | None = Field(
        default=None, sa_type=_TIMESTAMPTZ, nullable=True
    )
    read_at: datetime | None = Field(
        default=None, sa_type=_TIMESTAMPTZ, nullable=True
    )
    delivery_status: str | None = Field(default=None, max_length=32)


class ApprovalProcess(TimestampedSoftDelete, table=True):
    __tablename__ = "approval_processes"
    __table_args__ = (sa.UniqueConstraint("code", name="uq_approval_processes_code"),)

    code: str = Field(max_length=64, nullable=False)
    title: str = Field(max_length=255, nullable=False)
    requestor_role_codes: list[str] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    channel_role_codes: list[str] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    requires_upward_attachments: bool = Field(default=False)
    requires_downward_attachments: bool = Field(default=False)
    max_upward_attachments: int = Field(default=0)
    max_downward_attachments: int = Field(default=0)
    max_attachment_mb: int = Field(default=5)
    is_finance: bool = Field(default=False)
    informational_cc_role_codes: list[str] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )


class ApprovalRequest(TimestampedSoftDelete, table=True):
    __tablename__ = "approval_requests"
    __table_args__ = (
        sa.Index("ix_approval_requests_requestor", "requestor_user_id"),
        sa.Index("ix_approval_requests_state", "state"),
    )

    process_id: UUID = Field(foreign_key="approval_processes.id", nullable=False)
    requestor_user_id: UUID = Field(foreign_key="users.id", nullable=False)
    title: str = Field(max_length=255, nullable=False)
    payload_json: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    state: str = Field(
        default="submitted", max_length=32, nullable=False
    )  # submitted|in_review|approved|rejected|withdrawn|cancelled
    current_stage: int = Field(default=1, nullable=False)
    decided_at: datetime | None = Field(
        default=None, sa_type=_TIMESTAMPTZ, nullable=True
    )
    # M8 Path-A dynamic channel: leave (and future processes) may resolve a
    # per-request channel at submit-time rather than reading process.channel_role_codes.
    # Each entry: {"role_code": str, "recommend_only": bool, "scope_type": str | None}
    # When None, the engine falls back to process.channel_role_codes (all M7 processes).
    resolved_channel_json: list[dict[str, Any]] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )


class ApprovalStep(SQLModel, table=True):
    """One approver decision within an ApprovalRequest."""

    __tablename__ = "approval_steps"

    id: int = Field(default=None, primary_key=True)
    request_id: UUID = Field(foreign_key="approval_requests.id", nullable=False, ondelete="CASCADE")
    stage: int = Field(nullable=False)
    approver_role_code: str = Field(max_length=64, nullable=False)
    approver_user_id: UUID | None = Field(default=None, foreign_key="users.id")
    decision: str | None = Field(default=None, max_length=16)  # approved|rejected|forwarded
    comment: str | None = Field(default=None)
    decided_at: datetime | None = Field(
        default=None, sa_type=_TIMESTAMPTZ, nullable=True
    )
