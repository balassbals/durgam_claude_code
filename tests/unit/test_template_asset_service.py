"""Unit tests for TemplateAssetService — upload, replace, deactivate."""

from unittest.mock import ANY, MagicMock
from uuid import uuid4

import pytest

from durgam.services.template_asset import TemplateAssetService, TemplateError


def _make_svc(repo=None, upload_svc=None) -> TemplateAssetService:
    return TemplateAssetService(
        repo=repo or MagicMock(),
        upload_svc=upload_svc or MagicMock(),
    )


_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


class TestUploadTemplate:
    def test_invalid_type_raises(self):
        svc = _make_svc()
        with pytest.raises(TemplateError, match="Invalid template type"):
            svc.upload_template("xyz", b"data", "f.docx", _DOCX_MIME, uuid4())

    def test_wrong_mime_for_bos_raises(self):
        svc = _make_svc()
        with pytest.raises(TemplateError, match="not allowed"):
            svc.upload_template("bos", b"data", "f.pptx", _PPTX_MIME, uuid4())

    def test_wrong_mime_for_vac_raises(self):
        svc = _make_svc()
        with pytest.raises(TemplateError, match="not allowed"):
            svc.upload_template("vac", b"data", "f.docx", _DOCX_MIME, uuid4())

    def test_too_large_raises(self):
        svc = _make_svc()
        big = b"x" * (3 * 1024 * 1024)
        with pytest.raises(TemplateError, match="2 MB"):
            svc.upload_template("bos", big, "f.docx", _DOCX_MIME, uuid4())

    def test_replaces_existing(self):
        repo = MagicMock()
        old = MagicMock()
        repo.get_active_by_type.return_value = old
        upload_svc = MagicMock()
        file_asset = MagicMock()
        file_asset.id = uuid4()
        upload_svc.upload.return_value = file_asset
        repo.save.side_effect = lambda r: r
        svc = _make_svc(repo, upload_svc)

        svc.upload_template("bos", b"data", "f.docx", _DOCX_MIME, uuid4())
        repo.soft_delete.assert_called_once_with(old, ANY)

    def test_success_bos_docx(self):
        repo = MagicMock()
        repo.get_active_by_type.return_value = None
        upload_svc = MagicMock()
        file_asset = MagicMock()
        file_asset.id = uuid4()
        upload_svc.upload.return_value = file_asset
        repo.save.side_effect = lambda r: r
        svc = _make_svc(repo, upload_svc)

        result = svc.upload_template("BOS", b"data", "f.docx", _DOCX_MIME, uuid4())
        assert result.template_type == "bos"
        assert result.file_id == file_asset.id
        repo.save.assert_called_once()

    def test_success_vac_pptx(self):
        repo = MagicMock()
        repo.get_active_by_type.return_value = None
        upload_svc = MagicMock()
        file_asset = MagicMock()
        file_asset.id = uuid4()
        upload_svc.upload.return_value = file_asset
        repo.save.side_effect = lambda r: r
        svc = _make_svc(repo, upload_svc)

        result = svc.upload_template("vac", b"data", "f.pptx", _PPTX_MIME, uuid4())
        assert result.template_type == "vac"
        repo.save.assert_called_once()


class TestSoftDelete:
    def test_not_found_raises(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        svc = _make_svc(repo)
        with pytest.raises(TemplateError, match="not found"):
            svc.soft_delete(uuid4(), uuid4())

    def test_delegates_to_repo(self):
        repo = MagicMock()
        row = MagicMock()
        repo.get_by_id.return_value = row
        repo.soft_delete.return_value = row
        svc = _make_svc(repo)
        svc.soft_delete(uuid4(), uuid4())
        repo.soft_delete.assert_called_once()
