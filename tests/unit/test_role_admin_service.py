"""Unit tests for RoleAdminService (services ≥85% line threshold)."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.role_admin import RoleAdminError, RoleAdminService


def _make_svc(role_repo=None, permission_repo=None) -> RoleAdminService:
    return RoleAdminService(
        role_repo=role_repo or MagicMock(),
        permission_repo=permission_repo or MagicMock(),
    )


class TestCreateRole:
    def test_empty_code_raises(self):
        svc = _make_svc()
        with pytest.raises(RoleAdminError, match="code is required"):
            svc.create_role("", "Some Name", 10, None, uuid4())

    def test_empty_name_raises(self):
        svc = _make_svc()
        with pytest.raises(RoleAdminError, match="name is required"):
            svc.create_role("HOD", "", 10, None, uuid4())

    def test_duplicate_code_raises(self):
        role_repo = MagicMock()
        role_repo.get_by_code.return_value = MagicMock()  # already exists
        svc = _make_svc(role_repo=role_repo)
        with pytest.raises(RoleAdminError, match="already in use"):
            svc.create_role("HOD", "Head of Dept", 30, None, uuid4())

    def test_creates_role_on_repo(self):
        role_repo = MagicMock()
        role_repo.get_by_code.return_value = None
        fake_role = MagicMock()
        fake_role.id = uuid4()
        role_repo.create.return_value = fake_role
        svc = _make_svc(role_repo=role_repo)
        role = svc.create_role("HOD", "Head of Dept", 30, "Dept head role", uuid4())
        assert role is fake_role
        role_repo.create.assert_called_once()

    def test_code_is_uppercased(self):
        role_repo = MagicMock()
        role_repo.get_by_code.return_value = None
        role_repo.create.return_value = MagicMock()
        svc = _make_svc(role_repo=role_repo)
        svc.create_role("hod", "Head of Dept", 30, None, uuid4())
        args = role_repo.create.call_args
        assert args[0][0] == "HOD"


class TestUpdatePermissions:
    def test_role_not_found_raises(self):
        role_repo = MagicMock()
        role_repo.get_by_id.return_value = None
        svc = _make_svc(role_repo=role_repo)
        with pytest.raises(RoleAdminError, match="not found"):
            svc.update_permissions(uuid4(), [], uuid4())

    def test_unknown_permission_raises(self):
        role_repo = MagicMock()
        role_repo.get_by_id.return_value = MagicMock()
        perm_repo = MagicMock()
        perm_repo.get_by_id.return_value = None  # unknown permission
        svc = _make_svc(role_repo=role_repo, permission_repo=perm_repo)
        with pytest.raises(RoleAdminError, match="not found"):
            svc.update_permissions(uuid4(), [uuid4()], uuid4())

    def test_valid_permissions_calls_replace(self):
        role_repo = MagicMock()
        role_repo.get_by_id.return_value = MagicMock()
        perm_repo = MagicMock()
        perm_repo.get_by_id.return_value = MagicMock()  # permission exists
        svc = _make_svc(role_repo=role_repo, permission_repo=perm_repo)
        pids = [uuid4(), uuid4()]
        svc.update_permissions(uuid4(), pids, uuid4())
        role_repo.replace_permissions.assert_called_once()


class TestSoftDeleteRole:
    def test_not_found_raises(self):
        role_repo = MagicMock()
        role_repo.get_by_id.return_value = None
        svc = _make_svc(role_repo=role_repo)
        with pytest.raises(RoleAdminError, match="not found"):
            svc.soft_delete_role(uuid4(), uuid4())

    def test_calls_soft_delete(self):
        fake_role = MagicMock()
        role_repo = MagicMock()
        role_repo.get_by_id.return_value = fake_role
        role_repo.soft_delete.return_value = fake_role
        svc = _make_svc(role_repo=role_repo)
        svc.soft_delete_role(uuid4(), uuid4())
        role_repo.soft_delete.assert_called_once()
