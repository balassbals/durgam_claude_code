"""Unit tests for DocumentTemplateService — letterhead upload, replace, deactivate (E-005)."""

from unittest.mock import ANY, MagicMock
from uuid import uuid4

import pytest

from durgam.services.document_template import DocumentTemplateError, DocumentTemplateService

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _make_svc(repo=None, upload_svc=None) -> DocumentTemplateService:
    return DocumentTemplateService(
        repo=repo or MagicMock(),
        upload_svc=upload_svc or MagicMock(),
    )


class TestUploadLetterhead:
    def test_empty_role_code_raises(self):
        svc = _make_svc()
        with pytest.raises(DocumentTemplateError, match="Role code is required"):
            svc.upload_letterhead("", b"data", "f.docx", _DOCX_MIME, uuid4())

    def test_invalid_mime_raises(self):
        svc = _make_svc()
        with pytest.raises(DocumentTemplateError, match="not allowed"):
            svc.upload_letterhead("REGISTRAR", b"data", "f.txt", "text/plain", uuid4())

    def test_image_mime_rejected(self):
        svc = _make_svc()
        with pytest.raises(DocumentTemplateError, match="not allowed"):
            svc.upload_letterhead("REGISTRAR", b"data", "f.png", "image/png", uuid4())

    def test_too_large_raises(self):
        svc = _make_svc()
        big = b"x" * (6 * 1024 * 1024)
        with pytest.raises(DocumentTemplateError, match="5 MB"):
            svc.upload_letterhead("REGISTRAR", big, "f.docx", _DOCX_MIME, uuid4())

    def test_replaces_existing(self):
        repo = MagicMock()
        old = MagicMock()
        repo.get_letterhead_by_role.return_value = old
        upload_svc = MagicMock()
        file_asset = MagicMock()
        file_asset.id = uuid4()
        upload_svc.upload.return_value = file_asset
        repo.save.side_effect = lambda r: r
        svc = _make_svc(repo, upload_svc)

        svc.upload_letterhead("REGISTRAR", b"data", "f.docx", _DOCX_MIME, uuid4())
        repo.soft_delete.assert_called_once_with(old, ANY)

    def test_success_saves_and_returns(self):
        repo = MagicMock()
        repo.get_letterhead_by_role.return_value = None
        upload_svc = MagicMock()
        file_asset = MagicMock()
        file_asset.id = uuid4()
        upload_svc.upload.return_value = file_asset
        repo.save.side_effect = lambda r: r
        svc = _make_svc(repo, upload_svc)

        result = svc.upload_letterhead("registrar", b"data", "f.docx", _DOCX_MIME, uuid4())
        assert result.role_code == "REGISTRAR"
        assert result.purpose == "letterhead"
        assert result.file_id == file_asset.id
        repo.save.assert_called_once()


class TestSoftDelete:
    def test_not_found_raises(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        svc = _make_svc(repo)
        with pytest.raises(DocumentTemplateError, match="not found"):
            svc.soft_delete(uuid4(), uuid4())

    def test_delegates_to_repo(self):
        repo = MagicMock()
        row = MagicMock()
        repo.get_by_id.return_value = row
        repo.soft_delete.return_value = row
        svc = _make_svc(repo)
        svc.soft_delete(uuid4(), uuid4())
        repo.soft_delete.assert_called_once()
