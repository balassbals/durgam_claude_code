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


_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestUploadPipeline:
    def test_upload_creates_file_and_letterhead(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)
        lh = svc.upload_letterhead(
            "TEST_LH", _PNG_1X1, "test.png", "image/png", user.id,
        )
        assert lh.role_code == "TEST_LH"
        assert lh.file_id is not None
        fa = db_session.get(FileAsset, lh.file_id)
        assert fa is not None
        assert fa.mime_type == "image/png"

    def test_replace_soft_deletes_old(self, db_session):
        user = _user(db_session)
        svc = _svc(db_session)
        old = svc.upload_letterhead(
            "REPLACE_LH", _PNG_1X1, "old.png", "image/png", user.id,
        )
        new = svc.upload_letterhead(
            "REPLACE_LH", _PNG_1X1, "new.png", "image/png", user.id,
        )
        db_session.refresh(old)
        assert old.is_deleted is True
        assert new.is_deleted is False
        assert new.id != old.id


class TestPartialUniqueIndexes:
    def test_global_duplicate_prevented(self, db_session):
        """Two active NULL-scope rows for same role_code must be rejected."""
        user = _user(db_session)
        sha = hashlib.sha256(_PNG_1X1).hexdigest()

        def _make_fa():
            fa = FileAsset(
                storage_key=uuid4().hex,
                original_name="lh.png",
                mime_type="image/png",
                size_bytes=len(_PNG_1X1),
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
            "SD_LH", _PNG_1X1, "old.png", "image/png", user.id,
        )
        repo = LetterheadAssetRepository(db_session)
        repo.soft_delete(old, user.id)
        db_session.flush()
        new = svc.upload_letterhead(
            "SD_LH", _PNG_1X1, "new.png", "image/png", user.id,
        )
        assert new.id != old.id

    def test_scoped_duplicate_prevented(self, db_session):
        user = _user(db_session)
        sha = hashlib.sha256(_PNG_1X1).hexdigest()
        dept_id = uuid4()

        def _make_fa():
            fa = FileAsset(
                storage_key=uuid4().hex,
                original_name="lh.png",
                mime_type="image/png",
                size_bytes=len(_PNG_1X1),
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
            "HOD", _PNG_1X1, "lh1.png", "image/png", user.id,
            scope_type="department", scope_id=uuid4(),
        )
        svc.upload_letterhead(
            "HOD", _PNG_1X1, "lh2.png", "image/png", user.id,
            scope_type="department", scope_id=uuid4(),
        )
