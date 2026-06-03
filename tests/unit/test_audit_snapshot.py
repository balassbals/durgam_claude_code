"""Unit tests for audit_snapshot() serialization."""

from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, Relationship, SQLModel

from durgam.audit.snapshot import audit_snapshot


class _FakeModel(SQLModel, table=True):
    __tablename__ = "fake_snapshot_test"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=64)
    count: int = Field(default=0)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=sa.DateTime(timezone=True),
    )
    extra_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    nullable_field: str | None = Field(default=None)


class _RedactedModel(SQLModel, table=True):
    __tablename__ = "redacted_snapshot_test"

    _audit_redact_fields: ClassVar[set[str]] = {"secret", "also_secret"}

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=64)
    secret: str = Field(max_length=256)
    also_secret: str | None = Field(default=None)
    public_field: str = Field(default="visible")


class _ModelWithRelationship(SQLModel, table=True):
    __tablename__ = "rel_snapshot_test"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=64)
    parent_id: UUID | None = Field(default=None, foreign_key="fake_snapshot_test.id")


class TestAuditSnapshot:
    def test_basic_fields_serialized(self):
        entity = _FakeModel(name="test", count=42)
        snap = audit_snapshot(entity)
        assert snap["name"] == "test"
        assert snap["count"] == 42

    def test_uuid_converted_to_string(self):
        uid = uuid4()
        entity = _FakeModel(id=uid, name="x", count=0)
        snap = audit_snapshot(entity)
        assert snap["id"] == str(uid)

    def test_datetime_converted_to_iso(self):
        dt = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)
        entity = _FakeModel(name="x", count=0, created_at=dt)
        snap = audit_snapshot(entity)
        assert snap["created_at"] == dt.isoformat()

    def test_none_preserved(self):
        entity = _FakeModel(name="x", count=0, nullable_field=None)
        snap = audit_snapshot(entity)
        assert snap["nullable_field"] is None

    def test_dict_json_passthrough(self):
        entity = _FakeModel(name="x", count=0, extra_json={"key": [1, 2]})
        snap = audit_snapshot(entity)
        assert snap["extra_json"] == {"key": [1, 2]}

    def test_redacted_fields(self):
        entity = _RedactedModel(
            name="alice", secret="s3cr3t", also_secret="hidden", public_field="ok"
        )
        snap = audit_snapshot(entity)
        assert snap["secret"] == "<redacted>"
        assert snap["also_secret"] == "<redacted>"
        assert snap["name"] == "alice"
        assert snap["public_field"] == "ok"

    def test_no_redact_attr_means_no_redaction(self):
        entity = _FakeModel(name="open", count=99)
        snap = audit_snapshot(entity)
        assert "<redacted>" not in snap.values()

    def test_relationship_fields_skipped(self):
        entity = _ModelWithRelationship(name="child", parent_id=uuid4())
        snap = audit_snapshot(entity)
        assert "id" in snap
        assert "name" in snap
        assert "parent_id" in snap
        for key in snap:
            assert not isinstance(snap[key], SQLModel)
