"""Unit tests for SchoolService (non-trivial handlers only)."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.org_exceptions import HardDeleteBlockedError
from durgam.services.school import SchoolError, SchoolService


def _make_svc(school_repo=None) -> SchoolService:
    return SchoolService(school_repo=school_repo or MagicMock())


class TestCreate:
    def test_empty_code_raises(self):
        svc = _make_svc()
        with pytest.raises(SchoolError, match="code is required"):
            svc.create("", "Name", uuid4())

    def test_empty_name_raises(self):
        svc = _make_svc()
        with pytest.raises(SchoolError, match="name is required"):
            svc.create("SCI", "", uuid4())

    def test_duplicate_code_raises(self):
        repo = MagicMock()
        repo.get_by_code.return_value = MagicMock()
        svc = _make_svc(repo)
        with pytest.raises(SchoolError, match="already in use"):
            svc.create("SCI", "Sciences", uuid4())

    def test_creates_successfully(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        fake = MagicMock()
        repo.save.return_value = fake
        svc = _make_svc(repo)
        result = svc.create("SCI", "Sciences", uuid4())
        assert result is fake


class TestHardDelete:
    def test_blocked_by_departments(self):
        repo = MagicMock()
        fake = MagicMock()
        fake.is_deleted = True
        repo._session.get.return_value = fake
        repo.count_departments.return_value = 5
        svc = _make_svc(repo)
        with pytest.raises(HardDeleteBlockedError, match="5 department"):
            svc.hard_delete(uuid4(), uuid4())

    def test_blocked_by_audit(self):
        repo = MagicMock()
        fake = MagicMock()
        fake.is_deleted = True
        repo._session.get.return_value = fake
        repo.count_departments.return_value = 0
        repo._session.exec.return_value.one.return_value = 1
        svc = _make_svc(repo)
        with pytest.raises(HardDeleteBlockedError, match="1 audit"):
            svc.hard_delete(uuid4(), uuid4())

    def test_requires_soft_delete_first(self):
        repo = MagicMock()
        fake = MagicMock()
        fake.is_deleted = False
        repo._session.get.return_value = fake
        svc = _make_svc(repo)
        with pytest.raises(SchoolError, match="deactivated"):
            svc.hard_delete(uuid4(), uuid4())
