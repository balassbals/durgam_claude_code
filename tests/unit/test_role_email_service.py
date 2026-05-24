"""Unit tests for RoleEmailService — CRUD and validation."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.role_email import RoleEmailError, RoleEmailService


def _make_svc(repo=None) -> RoleEmailService:
    return RoleEmailService(repo=repo or MagicMock())


class TestCreate:
    def test_empty_role_code_raises(self):
        svc = _make_svc()
        with pytest.raises(RoleEmailError, match="Role code is required"):
            svc.create("", "a@b.com", uuid4())

    def test_invalid_email_raises(self):
        svc = _make_svc()
        with pytest.raises(RoleEmailError, match="Invalid email"):
            svc.create("REGISTRAR", "not-an-email", uuid4())

    def test_duplicate_raises(self):
        repo = MagicMock()
        repo.get_by_role_and_scope.return_value = MagicMock()
        svc = _make_svc(repo)
        with pytest.raises(RoleEmailError, match="already exists"):
            svc.create("REGISTRAR", "a@b.com", uuid4())

    def test_scope_type_without_scope_id_raises(self):
        repo = MagicMock()
        repo.get_by_role_and_scope.return_value = None
        svc = _make_svc(repo)
        with pytest.raises(RoleEmailError, match="scope_type and scope_id"):
            svc.create("HOD", "h@b.com", uuid4(), scope_type="department")

    def test_scope_id_without_scope_type_raises(self):
        repo = MagicMock()
        repo.get_by_role_and_scope.return_value = None
        svc = _make_svc(repo)
        with pytest.raises(RoleEmailError, match="scope_type and scope_id"):
            svc.create("HOD", "h@b.com", uuid4(), scope_id=uuid4())

    def test_success_saves_and_returns(self):
        repo = MagicMock()
        repo.get_by_role_and_scope.return_value = None
        repo.save.side_effect = lambda r: r
        svc = _make_svc(repo)
        result = svc.create("REGISTRAR", "reg@example.dev", uuid4())
        assert result.role_code == "REGISTRAR"
        assert result.email == "reg@example.dev"
        repo.save.assert_called_once()

    def test_role_code_uppercased_email_lowered(self):
        repo = MagicMock()
        repo.get_by_role_and_scope.return_value = None
        repo.save.side_effect = lambda r: r
        svc = _make_svc(repo)
        result = svc.create("registrar", "REG@Example.Dev", uuid4())
        assert result.role_code == "REGISTRAR"
        assert result.email == "reg@example.dev"


class TestUpdate:
    def test_not_found_raises(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        svc = _make_svc(repo)
        with pytest.raises(RoleEmailError, match="not found"):
            svc.update(uuid4(), {"email": "x@y.com"}, uuid4())

    def test_invalid_email_on_update_raises(self):
        repo = MagicMock()
        row = MagicMock()
        repo.get_by_id.return_value = row
        svc = _make_svc(repo)
        with pytest.raises(RoleEmailError, match="Invalid email"):
            svc.update(uuid4(), {"email": "bad"}, uuid4())


class TestSoftDelete:
    def test_not_found_raises(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        svc = _make_svc(repo)
        with pytest.raises(RoleEmailError, match="not found"):
            svc.soft_delete(uuid4(), uuid4())

    def test_delegates_to_repo(self):
        repo = MagicMock()
        row = MagicMock()
        repo.get_by_id.return_value = row
        repo.soft_delete.return_value = row
        svc = _make_svc(repo)
        svc.soft_delete(uuid4(), uuid4())
        repo.soft_delete.assert_called_once()
