"""Integration tests for DocumentTemplate (type-based) — upload pipeline, partial unique, replace.

Uses db_session (transactional rollback) for isolation.
Replaces TemplateAsset tests per E-005 unification.
"""

import hashlib
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlmodel import select

from durgam.models.config_anchors import DocumentTemplate
from durgam.models.crosscutting import FileAsset
from durgam.models.identity import User
from durgam.repositories.document_template import DocumentTemplateRepository
from durgam.repositories.file_asset import FileAssetRepository
from durgam.services.document_template import DocumentTemplateService
from durgam.services.upload import UploadService
from durgam.storage import get_storage_backend


_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _user(session) -> User:
    u = User(
        username=f"tpl_{uuid4().hex[:8]}",
        email=f"tpl_{uuid4().hex[:8]}@example.dev",
        password_hash="not-a-real-hash",
    )
    session.add(u)
    session.flush()
    session.refresh(u)
    return u


def _svc(session) -> DocumentTemplateService:
    backend = get_storage_backend()
    return DocumentTemplateService(
        repo=DocumentTemplateRepository(session),
        upload_svc=UploadService(
            file_repo=FileAssetRepository(session),
            backend=backend,
        ),
    )


_DOCX_BYTES = b"PK\x03\x04" + b"\x00" * 100


class TestUploadPipeline:
    def test_upload_creates_file_and_template(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)
        tpl = svc.upload_template("bos", _DOCX_BYTES, "bos.docx", _DOCX_MIME, user.id)
        assert tpl.purpose == "bos"
        assert tpl.role_code is None
        assert tpl.file_id is not None
        fa = db_session.get(FileAsset, tpl.file_id)
        assert fa is not None
        assert fa.mime_type == _DOCX_MIME

    def test_replace_soft_deletes_old(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)
        old = svc.upload_template("mom", _DOCX_BYTES, "old.docx", _DOCX_MIME, user.id)
        new = svc.upload_template("mom", _DOCX_BYTES, "new.docx", _DOCX_MIME, user.id)
        db_session.refresh(old)
        assert old.is_deleted is True
        assert new.is_deleted is False
        assert new.id != old.id


class TestPartialUniqueIndex:
    def test_duplicate_active_type_prevented(self, db_session):
        """Two active rows with the same purpose (non-letterhead) must be rejected."""
        user = _user(db_session)
        sha = hashlib.sha256(_DOCX_BYTES).hexdigest()

        existing = db_session.exec(
            select(DocumentTemplate).where(
                DocumentTemplate.purpose == "mom",
                DocumentTemplate.role_code.is_(None),  # type: ignore[union-attr]
                DocumentTemplate.is_deleted == False,  # noqa: E712
            )
        ).first()
        if existing:
            existing.is_deleted = True
            db_session.add(existing)
            db_session.flush()

        def _make_fa():
            fa = FileAsset(
                storage_key=uuid4().hex,
                original_name="tpl.docx",
                mime_type=_DOCX_MIME,
                size_bytes=len(_DOCX_BYTES),
                sha256=sha,
                owner_user_id=user.id,
                purpose="template",
            )
            db_session.add(fa)
            db_session.flush()
            db_session.refresh(fa)
            return fa

        fa1 = _make_fa()
        t1 = DocumentTemplate(purpose="mom", role_code=None, file_id=fa1.id)
        db_session.add(t1)
        db_session.flush()

        fa2 = _make_fa()
        t2 = DocumentTemplate(purpose="mom", role_code=None, file_id=fa2.id)
        db_session.add(t2)
        with pytest.raises(
            sa.exc.IntegrityError,
            match="uq_document_templates_type",
        ):
            db_session.flush()

    def test_soft_deleted_excluded_from_unique(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)
        old = svc.upload_template("bos", _DOCX_BYTES, "old.docx", _DOCX_MIME, user.id)
        repo = DocumentTemplateRepository(db_session)
        repo.soft_delete(old, user.id)
        db_session.flush()
        new = svc.upload_template("bos", _DOCX_BYTES, "new.docx", _DOCX_MIME, user.id)
        assert new.id != old.id
