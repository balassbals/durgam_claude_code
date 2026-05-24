"""Integration tests for file upload pipeline — UploadService + LocalFS + real DB."""

from uuid import uuid4

import pytest

from durgam.models.crosscutting import FileAsset
from durgam.models.identity import User
from durgam.repositories.file_asset import FileAssetRepository
from durgam.services.upload import UploadError, UploadService
from durgam.storage.local import LocalFilesystemBackend


def _user(session) -> User:
    u = User(
        username=f"test_{uuid4().hex[:8]}",
        email=f"test_{uuid4().hex[:8]}@example.dev",
        password_hash="not-a-real-hash",
    )
    session.add(u)
    session.flush()
    session.refresh(u)
    return u


def _svc(session, tmp_path, **kwargs) -> UploadService:
    return UploadService(
        file_repo=FileAssetRepository(session),
        backend=LocalFilesystemBackend(str(tmp_path)),
        **kwargs,
    )


class TestUploadPipeline:
    def test_upload_creates_file_asset_row(self, db_session, tmp_path):
        user = _user(db_session)
        svc = _svc(db_session, tmp_path)
        asset = svc.upload(b"hello", "test.png", "image/png", user.id)
        assert asset.id is not None
        assert asset.storage_key
        assert asset.original_name == "test.png"
        assert asset.mime_type == "image/png"
        assert asset.size_bytes == 5
        assert asset.owner_user_id == user.id

    def test_upload_stores_file_on_backend(self, db_session, tmp_path):
        user = _user(db_session)
        svc = _svc(db_session, tmp_path)
        data = b"file-content-here"
        asset = svc.upload(data, "doc.pdf", "application/pdf", user.id)
        backend = LocalFilesystemBackend(str(tmp_path))
        assert backend.get(asset.storage_key) == data

    def test_get_by_storage_key_returns_uploaded(self, db_session, tmp_path):
        user = _user(db_session)
        svc = _svc(db_session, tmp_path)
        asset = svc.upload(b"x", "f.png", "image/png", user.id)
        repo = FileAssetRepository(db_session)
        found = repo.get_by_storage_key(asset.storage_key)
        assert found is not None
        assert found.id == asset.id

    def test_soft_deleted_excluded_from_get_by_storage_key(self, db_session, tmp_path):
        user = _user(db_session)
        svc = _svc(db_session, tmp_path)
        asset = svc.upload(b"x", "f.png", "image/png", user.id)
        repo = FileAssetRepository(db_session)
        repo.soft_delete(asset, user.id)
        db_session.flush()
        assert repo.get_by_storage_key(asset.storage_key) is None
