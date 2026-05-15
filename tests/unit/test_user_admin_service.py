"""Unit tests for UserAdminService (services ≥85% line threshold)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from durgam.services.user_admin import HardDeleteBlockedError, UserAdminError, UserAdminService


def _make_svc(user_repo=None, user_role_repo=None) -> UserAdminService:
    return UserAdminService(
        user_repo=user_repo or MagicMock(),
        user_role_repo=user_role_repo or MagicMock(),
    )


class TestCreateUser:
    def test_empty_username_raises(self):
        svc = _make_svc()
        with pytest.raises(UserAdminError, match="Username is required"):
            svc.create_user("", "a@b.com", uuid4())

    def test_invalid_email_raises(self):
        svc = _make_svc()
        with pytest.raises(UserAdminError, match="valid email"):
            svc.create_user("jdoe", "notanemail", uuid4())

    def test_duplicate_username_raises(self):
        user_repo = MagicMock()
        user_repo.get_by_username.return_value = MagicMock()  # already exists
        svc = _make_svc(user_repo=user_repo)
        with pytest.raises(UserAdminError, match="already taken"):
            svc.create_user("jdoe", "jdoe@test.com", uuid4())

    def test_duplicate_email_raises(self):
        user_repo = MagicMock()
        user_repo.get_by_username.return_value = None
        user_repo.get_by_email.return_value = MagicMock()  # already exists
        svc = _make_svc(user_repo=user_repo)
        with pytest.raises(UserAdminError, match="already registered"):
            svc.create_user("jdoe", "jdoe@test.com", uuid4())

    def test_returns_user_and_temp_password(self):
        user_repo = MagicMock()
        user_repo.get_by_username.return_value = None
        user_repo.get_by_email.return_value = None
        fake_user = MagicMock()
        fake_user.id = uuid4()
        user_repo.create.return_value = fake_user
        svc = _make_svc(user_repo=user_repo)

        with patch(
            "durgam.services.user_admin.generate_temp_password",
            return_value="Fake1!Pass12",
        ):
            user, pw = svc.create_user("jdoe", "jdoe@test.com", uuid4())

        assert user is fake_user
        assert pw == "Fake1!Pass12"
        user_repo.create.assert_called_once()


class TestSoftDeleteUser:
    def test_not_found_raises(self):
        user_repo = MagicMock()
        user_repo.get_by_id.return_value = None
        svc = _make_svc(user_repo=user_repo)
        with pytest.raises(UserAdminError, match="not found"):
            svc.soft_delete_user(uuid4(), uuid4())

    def test_calls_soft_delete_on_repo(self):
        fake_user = MagicMock()
        user_repo = MagicMock()
        user_repo.get_by_id.return_value = fake_user
        user_repo.soft_delete.return_value = fake_user
        svc = _make_svc(user_repo=user_repo)
        svc.soft_delete_user(uuid4(), uuid4())
        user_repo.soft_delete.assert_called_once()


class TestHardDeleteUser:
    def test_not_soft_deleted_raises(self):
        fake_user = MagicMock()
        fake_user.is_deleted = False
        user_repo = MagicMock()
        user_repo._session = MagicMock()
        user_repo._session.get.return_value = fake_user
        svc = _make_svc(user_repo=user_repo)
        with pytest.raises(UserAdminError, match="soft-deleted"):
            svc.hard_delete_user(uuid4(), uuid4())

    def test_user_with_audit_rows_raises_hard_delete_blocked(self):
        fake_user = MagicMock()
        fake_user.is_deleted = True
        fake_user.username = "jdoe"
        user_repo = MagicMock()
        user_repo._session = MagicMock()
        user_repo._session.get.return_value = fake_user
        # Simulate audit_count > 0
        user_repo._session.exec.return_value.one.return_value = 5
        svc = _make_svc(user_repo=user_repo)
        with pytest.raises(HardDeleteBlockedError):
            svc.hard_delete_user(uuid4(), uuid4())

    def test_no_audit_rows_succeeds(self):
        fake_user = MagicMock()
        fake_user.is_deleted = True
        fake_user.username = "jdoe"
        user_repo = MagicMock()
        user_repo._session = MagicMock()
        user_repo._session.get.return_value = fake_user
        # Simulate audit_count == 0
        user_repo._session.exec.return_value.one.return_value = 0
        svc = _make_svc(user_repo=user_repo)
        svc.hard_delete_user(uuid4(), uuid4())
        user_repo.hard_delete.assert_called_once_with(fake_user)


class TestResetUserPassword:
    def test_not_found_raises(self):
        user_repo = MagicMock()
        user_repo.get_by_id.return_value = None
        svc = _make_svc(user_repo=user_repo)
        with pytest.raises(UserAdminError, match="not found"):
            svc.reset_user_password(uuid4(), uuid4())

    def test_returns_user_and_temp_password(self):
        fake_user = MagicMock()
        fake_user.id = uuid4()
        user_repo = MagicMock()
        user_repo.get_by_id.return_value = fake_user
        user_repo.update_fields.return_value = fake_user
        svc = _make_svc(user_repo=user_repo)

        with patch(
            "durgam.services.user_admin.generate_temp_password",
            return_value="Reset1!Pw9876",
        ):
            user, pw = svc.reset_user_password(uuid4(), uuid4())

        assert pw == "Reset1!Pw9876"
        user_repo.update_fields.assert_called_once()
