"""Integration tests for LetterheadAsset — upload pipeline, partial unique, replace.

Uses db_session (transactional rollback) for isolation.
"""

import hashlib
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlmodel import select

from durgam.models.config_anchors import LetterheadAsset
from durgam.models.crosscutting import FileAsset
from durgam.models.identity import User
from durgam.repositories.file_asset import FileAssetRepository
from durgam.repositories.letterhead_asset import LetterheadAssetRepository
from durgam.services.letterhead_asset import LetterheadAssetService
from durgam.services.upload import UploadService
from durgam.storage import get_storage_backend


def _user(session) -> User:
    u = User(
        username=f"lh_{uuid4().hex[:8]}",
        email=f"lh_{uuid4().hex[:8]}@example.dev",
        password_hash="not-a-real-hash",
    )
    session.add(u)
    session.flush()
    session.refresh(u)
    return u


def _svc(session) -> LetterheadAssetService:
    backend = get_storage_backend()
    return LetterheadAssetService(
        repo=LetterheadAssetRepository(session),
        upload_svc=UploadService(
            file_repo=FileAssetRepository(session),
            backend=backend,
        ),
    )


_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_TEST_BYTES = b"PK\x03\x04fake-docx-bytes-for-testing"


class TestUploadPipeline:
    def test_upload_creates_file_and_letterhead(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)
        lh = svc.upload_letterhead(
            "TEST_LH", _TEST_BYTES, "test.docx", _DOCX_MIME, user.id,
        )
        assert lh.role_code == "TEST_LH"
        assert lh.file_id is not None
        fa = db_session.get(FileAsset, lh.file_id)
        assert fa is not None
        assert fa.mime_type == _DOCX_MIME

    def test_replace_soft_deletes_old(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)
        old = svc.upload_letterhead(
            "REPLACE_LH", _TEST_BYTES, "old.docx", _DOCX_MIME, user.id,
        )
        new = svc.upload_letterhead(
            "REPLACE_LH", _TEST_BYTES, "new.docx", _DOCX_MIME, user.id,
        )
        db_session.refresh(old)
        assert old.is_deleted is True
        assert new.is_deleted is False
        assert new.id != old.id


class TestPartialUniqueIndexes:
    def test_global_duplicate_prevented(self, db_session):
        """Two active NULL-scope rows for same role_code must be rejected."""
        user = _user(db_session)
        sha = hashlib.sha256(_TEST_BYTES).hexdigest()

        def _make_fa():
            fa = FileAsset(
                storage_key=uuid4().hex,
                original_name="lh.docx",
                mime_type=_DOCX_MIME,
                size_bytes=len(_TEST_BYTES),
                sha256=sha,
                owner_user_id=user.id,
                purpose="letterhead",
            )
            db_session.add(fa)
            db_session.flush()
            db_session.refresh(fa)
            return fa

        fa1 = _make_fa()
        lh1 = LetterheadAsset(role_code="DUP_LH", file_id=fa1.id)
        db_session.add(lh1)
        db_session.flush()

        fa2 = _make_fa()
        lh2 = LetterheadAsset(role_code="DUP_LH", file_id=fa2.id)
        db_session.add(lh2)
        with pytest.raises(sa.exc.IntegrityError, match="uq_letterhead_assets_global"):
            db_session.flush()

    def test_soft_deleted_excluded_from_unique(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)
        old = svc.upload_letterhead(
            "SD_LH", _TEST_BYTES, "old.docx", _DOCX_MIME, user.id,
        )
        repo = LetterheadAssetRepository(db_session)
        repo.soft_delete(old, user.id)
        db_session.flush()
        new = svc.upload_letterhead(
            "SD_LH", _TEST_BYTES, "new.docx", _DOCX_MIME, user.id,
        )
        assert new.id != old.id

    def test_scoped_duplicate_prevented(self, db_session):
        user = _user(db_session)
        sha = hashlib.sha256(_TEST_BYTES).hexdigest()
        dept_id = uuid4()

        def _make_fa():
            fa = FileAsset(
                storage_key=uuid4().hex,
                original_name="lh.docx",
                mime_type=_DOCX_MIME,
                size_bytes=len(_TEST_BYTES),
                sha256=sha,
                owner_user_id=user.id,
            )
            db_session.add(fa)
            db_session.flush()
            db_session.refresh(fa)
            return fa

        fa1 = _make_fa()
        lh1 = LetterheadAsset(
            role_code="HOD", scope_type="department", scope_id=dept_id,
            file_id=fa1.id,
        )
        db_session.add(lh1)
        db_session.flush()

        fa2 = _make_fa()
        lh2 = LetterheadAsset(
            role_code="HOD", scope_type="department", scope_id=dept_id,
            file_id=fa2.id,
        )
        db_session.add(lh2)
        with pytest.raises(sa.exc.IntegrityError, match="uq_letterhead_assets_scoped"):
            db_session.flush()

    def test_different_scopes_ok(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)
        svc.upload_letterhead(
            "HOD", _TEST_BYTES, "lh1.docx", _DOCX_MIME, user.id,
            scope_type="department", scope_id=uuid4(),
        )
        svc.upload_letterhead(
            "HOD", _TEST_BYTES, "lh2.docx", _DOCX_MIME, user.id,
            scope_type="department", scope_id=uuid4(),
        )
