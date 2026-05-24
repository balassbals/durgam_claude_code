"""Unit tests for UploadService — validate/scan/store/record pipeline."""

import hashlib
from unittest.mock import MagicMock, call
from uuid import uuid4

import pytest

from durgam.services.upload import (
    FileScanner,
    NoOpScanner,
    UploadError,
    UploadService,
)


def _make_svc(
    *,
    repo=None,
    backend=None,
    scanner=None,
    allowed_mimes=None,
    max_size_mb=None,
) -> UploadService:
    return UploadService(
        file_repo=repo or MagicMock(),
        backend=backend or MagicMock(),
        scanner=scanner,
        allowed_mimes=allowed_mimes,
        max_size_mb=max_size_mb,
    )


class TestMimeValidation:
    def test_rejects_disallowed_mime(self):
        svc = _make_svc()
        with pytest.raises(UploadError, match="not allowed"):
            svc.upload(b"data", "file.exe", "application/x-msdownload", uuid4())

    def test_accepts_png(self):
        repo = MagicMock()
        repo.save.side_effect = lambda a: a
        svc = _make_svc(repo=repo)
        asset = svc.upload(b"data", "img.png", "image/png", uuid4())
        assert asset.mime_type == "image/png"

    def test_accepts_pdf(self):
        repo = MagicMock()
        repo.save.side_effect = lambda a: a
        svc = _make_svc(repo=repo)
        asset = svc.upload(b"data", "doc.pdf", "application/pdf", uuid4())
        assert asset.mime_type == "application/pdf"

    def test_custom_allowed_mimes(self):
        svc = _make_svc(allowed_mimes=frozenset({"text/csv"}))
        with pytest.raises(UploadError, match="not allowed"):
            svc.upload(b"data", "img.png", "image/png", uuid4())


class TestSizeValidation:
    def test_rejects_oversized_file(self):
        svc = _make_svc(max_size_mb=1)
        data = b"x" * (1 * 1024 * 1024 + 1)
        with pytest.raises(UploadError, match="size limit"):
            svc.upload(data, "big.png", "image/png", uuid4())

    def test_accepts_at_limit(self):
        repo = MagicMock()
        repo.save.side_effect = lambda a: a
        svc = _make_svc(repo=repo, max_size_mb=1)
        data = b"x" * (1 * 1024 * 1024)
        asset = svc.upload(data, "exact.png", "image/png", uuid4())
        assert asset.size_bytes == 1 * 1024 * 1024


class TestScannerIntegration:
    def test_scanner_called_before_store(self):
        scanner = MagicMock(spec=FileScanner)
        backend = MagicMock()
        repo = MagicMock()
        repo.save.side_effect = lambda a: a
        svc = _make_svc(repo=repo, backend=backend, scanner=scanner)
        svc.upload(b"safe", "file.png", "image/png", uuid4())
        scanner.scan.assert_called_once_with(b"safe", "file.png")
        backend.put.assert_called_once()

    def test_scanner_rejection_prevents_store(self):
        scanner = MagicMock(spec=FileScanner)
        scanner.scan.side_effect = UploadError("Infected!")
        backend = MagicMock()
        repo = MagicMock()
        svc = _make_svc(repo=repo, backend=backend, scanner=scanner)
        with pytest.raises(UploadError, match="Infected"):
            svc.upload(b"bad", "virus.png", "image/png", uuid4())
        backend.put.assert_not_called()
        repo.save.assert_not_called()

    def test_noop_scanner_does_not_raise(self):
        scanner = NoOpScanner()
        scanner.scan(b"data", "file.txt")


class TestPipeline:
    def test_sha256_computed_correctly(self):
        repo = MagicMock()
        repo.save.side_effect = lambda a: a
        svc = _make_svc(repo=repo)
        data = b"deterministic content"
        asset = svc.upload(data, "f.png", "image/png", uuid4())
        assert asset.sha256 == hashlib.sha256(data).hexdigest()

    def test_storage_key_is_uuid_hex(self):
        repo = MagicMock()
        repo.save.side_effect = lambda a: a
        svc = _make_svc(repo=repo)
        asset = svc.upload(b"x", "f.png", "image/png", uuid4())
        assert len(asset.storage_key) == 32
        int(asset.storage_key, 16)  # validates hex

    def test_owner_and_audit_fields_set(self):
        repo = MagicMock()
        repo.save.side_effect = lambda a: a
        actor = uuid4()
        svc = _make_svc(repo=repo)
        asset = svc.upload(b"x", "f.png", "image/png", actor, purpose="letterhead")
        assert asset.owner_user_id == actor
        assert asset.created_by == actor
        assert asset.updated_by == actor
        assert asset.purpose == "letterhead"

    def test_backend_put_called_with_key_and_data(self):
        repo = MagicMock()
        repo.save.side_effect = lambda a: a
        backend = MagicMock()
        svc = _make_svc(repo=repo, backend=backend)
        svc.upload(b"content", "f.pdf", "application/pdf", uuid4())
        backend.put.assert_called_once()
        args = backend.put.call_args
        assert args[0][1] == b"content"
        assert args[0][2] == "application/pdf"

    def test_repo_save_called(self):
        repo = MagicMock()
        repo.save.side_effect = lambda a: a
        svc = _make_svc(repo=repo)
        svc.upload(b"x", "f.png", "image/png", uuid4())
        repo.save.assert_called_once()
