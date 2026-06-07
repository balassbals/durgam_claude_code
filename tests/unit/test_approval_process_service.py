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


class TestChannelReorder:
    """Unit tests for move_channel_up/down logic (pure Python, not via Reflex)."""

    @staticmethod
    def _move_up(lst, code):
        idx = lst.index(code) if code in lst else -1
        if idx > 0:
            lst[idx - 1], lst[idx] = lst[idx], lst[idx - 1]
        return lst

    @staticmethod
    def _move_down(lst, code):
        idx = lst.index(code) if code in lst else -1
        if 0 <= idx < len(lst) - 1:
            lst[idx], lst[idx + 1] = lst[idx + 1], lst[idx]
        return lst

    def test_move_up_swaps_with_predecessor(self):
        assert self._move_up(["A", "B", "C"], "B") == ["B", "A", "C"]

    def test_move_up_first_element_is_noop(self):
        assert self._move_up(["A", "B", "C"], "A") == ["A", "B", "C"]

    def test_move_down_swaps_with_successor(self):
        assert self._move_down(["A", "B", "C"], "B") == ["A", "C", "B"]

    def test_move_down_last_element_is_noop(self):
        assert self._move_down(["A", "B", "C"], "C") == ["A", "B", "C"]


class TestChannelOrderPreservation:
    """Regression: channel_role_codes order must be preserved end-to-end."""

    def _make_svc(self):
        repo = MagicMock()
        return ApprovalProcessService(repo=repo), repo

    def test_create_preserves_channel_order(self):
        svc, repo = self._make_svc()
        repo.save.side_effect = lambda r: r
        channel = ["DEAN_STUDENT_WELFARE", "REGISTRAR"]
        result = svc.create(
            code="DSW_TEST",
            title="DSW Order Test",
            channel_role_codes=channel,
            actor_id=uuid4(),
        )
        assert result.channel_role_codes == ["DEAN_STUDENT_WELFARE", "REGISTRAR"]

    def test_update_preserves_channel_order(self):
        svc, repo = self._make_svc()
        existing = MagicMock()
        existing.channel_role_codes = ["A", "B"]
        repo.get_by_id.return_value = existing
        repo.save.side_effect = lambda r: r
        new_channel = ["HOD", "DEAN_STUDENT_WELFARE", "REGISTRAR"]
        svc.update(uuid4(), {"channel_role_codes": new_channel}, uuid4())
        assert existing.channel_role_codes == ["HOD", "DEAN_STUDENT_WELFARE", "REGISTRAR"]


class TestCreateWithAttachmentFields:
    """Regression: attachment + CC fields are persisted on create."""

    def _make_svc(self):
        repo = MagicMock()
        return ApprovalProcessService(repo=repo), repo

    def test_create_with_all_attachment_and_cc_fields(self):
        svc, repo = self._make_svc()
        repo.save.side_effect = lambda r: r
        result = svc.create(
            code="ATTACH_TEST",
            title="Attachment Fields Test",
            channel_role_codes=["HOD"],
            requires_upward_attachments=True,
            max_upward_attachments=5,
            requires_downward_attachments=True,
            max_downward_attachments=3,
            informational_cc_role_codes=["VC", "REGISTRAR"],
            actor_id=uuid4(),
        )
        assert result.requires_upward_attachments is True
        assert result.max_upward_attachments == 5
        assert result.requires_downward_attachments is True
        assert result.max_downward_attachments == 3
        assert result.informational_cc_role_codes == ["VC", "REGISTRAR"]
