"""Unit tests for DesignationService — CRUD + validation."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.designation import DesignationError, DesignationService


class TestDesignationCreate:
    def _make_svc(self):
        repo = MagicMock()
        return DesignationService(repo=repo), repo

    def test_create_success(self):
        svc, repo = self._make_svc()
        repo.save.side_effect = lambda r: r
        result = svc.create(
            code="senior_professor",
            name="Senior Professor",
            rank=1,
            actor_id=uuid4(),
        )
        repo.save.assert_called_once()
        assert result.code == "senior_professor"
        assert result.rank == 1

    def test_blank_code_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(DesignationError, match="code is required"):
            svc.create(code="  ", name="Test", rank=1, actor_id=uuid4())

    def test_blank_name_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(DesignationError, match="name is required"):
            svc.create(code="test", name="  ", rank=1, actor_id=uuid4())

    def test_zero_rank_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(DesignationError, match="Rank must be"):
            svc.create(code="test", name="Test", rank=0, actor_id=uuid4())

    def test_negative_rank_raises(self):
        svc, repo = self._make_svc()
        with pytest.raises(DesignationError, match="Rank must be"):
            svc.create(code="test", name="Test", rank=-1, actor_id=uuid4())


class TestDesignationUpdate:
    def _make_svc(self):
        repo = MagicMock()
        return DesignationService(repo=repo), repo

    def test_update_success(self):
        svc, repo = self._make_svc()
        existing = MagicMock()
        repo.get_by_id.return_value = existing
        repo.save.side_effect = lambda r: r
        result = svc.update(uuid4(), {"name": "Updated"}, uuid4())
        assert result.name == "Updated"
        repo.save.assert_called_once()

    def test_update_not_found_raises(self):
        svc, repo = self._make_svc()
        repo.get_by_id.return_value = None
        with pytest.raises(DesignationError, match="not found"):
            svc.update(uuid4(), {}, uuid4())


class TestDesignationSoftDelete:
    def _make_svc(self):
        repo = MagicMock()
        return DesignationService(repo=repo), repo

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
        with pytest.raises(DesignationError, match="not found"):
            svc.soft_delete(uuid4(), uuid4())
