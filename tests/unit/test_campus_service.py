"""Unit tests for CampusService (non-trivial handlers only)."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.campus import CampusError, CampusService
from durgam.services.org_exceptions import HardDeleteBlockedError


def _make_svc(campus_repo=None) -> CampusService:
    return CampusService(campus_repo=campus_repo or MagicMock())


class TestCreate:
    def test_empty_code_raises(self):
        svc = _make_svc()
        with pytest.raises(CampusError, match="code is required"):
            svc.create("", "Name", uuid4())

    def test_empty_name_raises(self):
        svc = _make_svc()
        with pytest.raises(CampusError, match="name is required"):
            svc.create("PSN", "", uuid4())

    def test_duplicate_code_raises(self):
        repo = MagicMock()
        repo.get_by_code.return_value = MagicMock()  # already exists
        svc = _make_svc(repo)
        with pytest.raises(CampusError, match="already in use"):
            svc.create("PSN", "Name", uuid4())

    def test_creates_and_returns_campus(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        fake = MagicMock()
        repo.save.return_value = fake
        svc = _make_svc(repo)
        result = svc.create("PSN", "Prasanthi Nilayam", uuid4())
        assert result is fake
        repo.save.assert_called_once()


class TestSoftDelete:
    def test_not_found_raises(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        svc = _make_svc(repo)
        with pytest.raises(CampusError, match="not found"):
            svc.soft_delete(uuid4(), uuid4())

    def test_delegates_to_repo(self):
        repo = MagicMock()
        fake = MagicMock()
        repo.get_by_id.return_value = fake
        repo.soft_delete.return_value = fake
        svc = _make_svc(repo)
        svc.soft_delete(uuid4(), uuid4())
        repo.soft_delete.assert_called_once()


class TestHardDelete:
    def test_not_soft_deleted_first_raises(self):
        repo = MagicMock()
        fake = MagicMock()
        fake.is_deleted = False
        repo._session.get.return_value = fake
        svc = _make_svc(repo)
        with pytest.raises(CampusError, match="deactivated"):
            svc.hard_delete(uuid4(), uuid4())

    def test_blocked_by_dependent_departments(self):
        repo = MagicMock()
        fake = MagicMock()
        fake.is_deleted = True
        repo._session.get.return_value = fake
        repo.count_departments.return_value = 2
        svc = _make_svc(repo)
        with pytest.raises(HardDeleteBlockedError, match="2 department"):
            svc.hard_delete(uuid4(), uuid4())

    def test_blocked_by_audit_history(self):
        repo = MagicMock()
        fake = MagicMock()
        fake.is_deleted = True
        repo._session.get.return_value = fake
        repo.count_departments.return_value = 0
        repo._session.exec.return_value.one.return_value = 3
        svc = _make_svc(repo)
        with pytest.raises(HardDeleteBlockedError, match="3 audit"):
            svc.hard_delete(uuid4(), uuid4())

    def test_not_found_raises(self):
        repo = MagicMock()
        repo._session.get.return_value = None
        svc = _make_svc(repo)
        with pytest.raises(CampusError, match="not found"):
            svc.hard_delete(uuid4(), uuid4())

    def test_succeeds_when_no_dependents_or_audit(self):
        repo = MagicMock()
        fake = MagicMock()
        fake.is_deleted = True
        repo._session.get.return_value = fake
        repo.count_departments.return_value = 0
        repo._session.exec.return_value.one.return_value = 0
        svc = _make_svc(repo)
        svc.hard_delete(uuid4(), uuid4())
        repo.hard_delete.assert_called_once_with(fake)
