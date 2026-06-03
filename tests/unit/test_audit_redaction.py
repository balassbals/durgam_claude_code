"""Unit tests for sensitive-field redaction in audit snapshots."""

from typing import ClassVar
from uuid import uuid4

from sqlmodel import Field, SQLModel

from durgam.audit.snapshot import audit_snapshot


class _SensitiveModel(SQLModel, table=True):
    __tablename__ = "sensitive_redaction_test"

    _audit_redact_fields: ClassVar[set[str]] = {"password_hash", "aadhaar_enc", "pan_enc"}

    id: int = Field(default=None, primary_key=True)
    username: str = Field(max_length=64)
    password_hash: str = Field(max_length=256)
    aadhaar_enc: str | None = Field(default=None, max_length=512)
    pan_enc: str | None = Field(default=None, max_length=128)
    email: str = Field(default="user@test.com", max_length=254)


class TestAuditRedaction:
    def test_password_hash_redacted(self):
        entity = _SensitiveModel(
            id=1, username="alice", password_hash="$2b$12$secrethash",
            email="alice@test.com",
        )
        snap = audit_snapshot(entity)
        assert snap["password_hash"] == "<redacted>"

    def test_aadhaar_enc_redacted(self):
        entity = _SensitiveModel(
            id=1, username="bob", password_hash="hash",
            aadhaar_enc="encrypted_aadhaar_value",
            email="bob@test.com",
        )
        snap = audit_snapshot(entity)
        assert snap["aadhaar_enc"] == "<redacted>"

    def test_pan_enc_redacted(self):
        entity = _SensitiveModel(
            id=1, username="carol", password_hash="hash",
            pan_enc="encrypted_pan_value",
            email="carol@test.com",
        )
        snap = audit_snapshot(entity)
        assert snap["pan_enc"] == "<redacted>"

    def test_non_sensitive_fields_unaffected(self):
        entity = _SensitiveModel(
            id=1, username="dave", password_hash="hash",
            aadhaar_enc="enc_aadhaar", pan_enc="enc_pan",
            email="dave@test.com",
        )
        snap = audit_snapshot(entity)
        assert snap["username"] == "dave"
        assert snap["email"] == "dave@test.com"
        assert snap["id"] == 1

    def test_all_redact_fields_simultaneously(self):
        entity = _SensitiveModel(
            id=1, username="eve", password_hash="$hash$",
            aadhaar_enc="aadhaar_cipher", pan_enc="pan_cipher",
            email="eve@test.com",
        )
        snap = audit_snapshot(entity)
        assert snap["password_hash"] == "<redacted>"
        assert snap["aadhaar_enc"] == "<redacted>"
        assert snap["pan_enc"] == "<redacted>"
        assert snap["username"] == "eve"

    def test_none_redacted_field_still_shows_redacted(self):
        entity = _SensitiveModel(
            id=1, username="frank", password_hash="hash",
            aadhaar_enc=None, pan_enc=None,
            email="frank@test.com",
        )
        snap = audit_snapshot(entity)
        assert snap["aadhaar_enc"] == "<redacted>"
        assert snap["pan_enc"] == "<redacted>"
