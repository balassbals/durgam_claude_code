"""Unit tests for CentreService."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.centre import CentreError, CentreService
from durgam.services.org_exceptions import HardDeleteBlockedError


def _make_svc(centre_repo=None) -> CentreService:
    return CentreService(centre_repo=centre_repo or MagicMock())


class TestCreate:
    def test_empty_code_raises(self):
        with pytest.raises(CentreError, match="code is required"):
            _make_svc().create("", "Name", uuid4(), uuid4())

    def test_empty_name_raises(self):
        with pytest.raises(CentreError, match="name is required"):
            _make_svc().create("CMB", "", uuid4(), uuid4())

    def test_duplicate_code_raises(self):
        repo = MagicMock()
        repo.get_by_code.return_value = MagicMock()
        with pytest.raises(CentreError, match="already in use"):
            CentreService(repo).create("CMB", "Maths Bio", uuid4(), uuid4())


class TestHardDelete:
    def test_blocked_by_audit(self):
        repo = MagicMock()
        fake = MagicMock()
        fake.is_deleted = True
        repo._session.get.return_value = fake
        repo._session.exec.return_value.one.return_value = 2
        svc = _make_svc(repo)
        with pytest.raises(HardDeleteBlockedError, match="2 audit"):
            svc.hard_delete(uuid4(), uuid4())

    def test_requires_soft_delete_first(self):
        repo = MagicMock()
        fake = MagicMock()
        fake.is_deleted = False
        repo._session.get.return_value = fake
        with pytest.raises(CentreError, match="deactivated"):
            _make_svc(repo).hard_delete(uuid4(), uuid4())

    def test_succeeds_when_no_audit(self):
        repo = MagicMock()
        fake = MagicMock()
        fake.is_deleted = True
        repo._session.get.return_value = fake
        repo._session.exec.return_value.one.return_value = 0
        _make_svc(repo).hard_delete(uuid4(), uuid4())
        repo.hard_delete.assert_called_once()
