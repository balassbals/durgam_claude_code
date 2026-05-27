"""Unit tests for ApprovalProcessService — CRUD + validation."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.approval_process import ApprovalProcessError, ApprovalProcessService


class TestApprovalProcessCreate:
    def _make_svc(self):
        repo = MagicMock()
        return ApprovalProcessService(repo=repo), repo

    def test_create_success(self):
        svc, repo = self._make_svc()
        repo.save.side_effect = lambda r: r
        result = svc.create(
            code="CPC_FUND_RELEASE",
            title="Central Purchase Committee Fund Release",
            requestor_role_codes=["HOD", "AHOD"],
            channel_role_codes=["REGISTRAR", "FINANCE_OFFICER"],
            is_finance=True,
            actor_id=uuid4(),
        )
        repo.save.assert_called_once()
        assert result.code == "CPC_FUND_RELEASE"
        assert result.is_finance is True

    def test_blank_code_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(ApprovalProcessError, match="code is required"):
            svc.create(
                code="  ",
                title="Test",
                actor_id=uuid4(),
            )

    def test_blank_title_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(ApprovalProcessError, match="title is required"):
            svc.create(
                code="TEST",
                title="  ",
                actor_id=uuid4(),
            )


class TestApprovalProcessUpdate:
    def _make_svc(self):
        repo = MagicMock()
        return ApprovalProcessService(repo=repo), repo

    def test_update_success(self):
        svc, repo = self._make_svc()
        existing = MagicMock()
        repo.get_by_id.return_value = existing
        repo.save.side_effect = lambda r: r
        result = svc.update(uuid4(), {"title": "Updated"}, uuid4())
        assert result.title == "Updated"
        repo.save.assert_called_once()

    def test_update_not_found_raises(self):
        svc, repo = self._make_svc()
        repo.get_by_id.return_value = None
        with pytest.raises(ApprovalProcessError, match="not found"):
            svc.update(uuid4(), {}, uuid4())


class TestApprovalProcessSoftDelete:
    def _make_svc(self):
        repo = MagicMock()
        return ApprovalProcessService(repo=repo), repo

    def test_soft_delete_success(self):
        svc, repo = self._make_svc()
        existing = MagicMock()
        repo.get_by_id.return_value = existing
        repo.soft_delete.side_effect = lambda r, a: r
        svc.soft_delete(uuid4(), uuid4())
        repo.soft_delete.assert_called_once()

    def test_soft_delete_not_found_raises(self):
        svc, repo = self._make_svc()
        repo.get_by_id.return_value = None
        with pytest.raises(ApprovalProcessError, match="not found"):
            svc.soft_delete(uuid4(), uuid4())
