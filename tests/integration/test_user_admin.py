"""Integration tests for UserAdminService + real PostgreSQL."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlmodel import Session

from durgam.repositories.user import UserRepository
from durgam.repositories.user_role import UserRoleRepository
from durgam.services.user_admin import UserAdminError, UserAdminService


def _svc(session: Session) -> UserAdminService:
    return UserAdminService(
        user_repo=UserRepository(session),
        user_role_repo=UserRoleRepository(session),
    )


class TestCreateUser:
    def test_create_returns_user_and_password(self, db_session: Session) -> None:
        actor = uuid4()
        svc = _svc(db_session)
        user, pw = svc.create_user("int_test_user", "int@test.invalid", actor)
        assert user.username == "int_test_user"
        assert len(pw) > 0
        assert user.must_change_password is True

    def test_duplicate_username_raises(self, db_session: Session) -> None:
        actor = uuid4()
        svc = _svc(db_session)
        svc.create_user("dup_user", "dup@test.invalid", actor)
        with pytest.raises(UserAdminError, match="already taken"):
            svc.create_user("dup_user", "dup2@test.invalid", actor)

    def test_list_includes_created_user(self, db_session: Session) -> None:
        actor = uuid4()
        svc = _svc(db_session)
        svc.create_user("list_tst_user", "lst@test.invalid", actor)
        users, total = svc.list_users()
        usernames = [u.username for u in users]
        assert "list_tst_user" in usernames

    def test_search_filters_by_username(self, db_session: Session) -> None:
        actor = uuid4()
        svc = _svc(db_session)
        svc.create_user("findme_xyz", "fxyz@test.invalid", actor)
        svc.create_user("notthisone", "not@test.invalid", actor)
        users, total = svc.list_users(search="findme")
        assert any(u.username == "findme_xyz" for u in users)
        assert not any(u.username == "notthisone" for u in users)


class TestSoftDelete:
    def test_soft_deleted_user_excluded_from_list(self, db_session: Session) -> None:
        actor = uuid4()
        svc = _svc(db_session)
        user, _ = svc.create_user("del_user", "del@test.invalid", actor)
        svc.soft_delete_user(user.id, actor)
        users, _ = svc.list_users()
        assert not any(u.username == "del_user" for u in users)


class TestHardDelete:
    def test_hard_delete_blocked_when_not_soft_deleted(self, db_session: Session) -> None:
        actor = uuid4()
        svc = _svc(db_session)
        user, _ = svc.create_user("hd_user", "hd@test.invalid", actor)
        with pytest.raises(UserAdminError, match="soft-deleted"):
            svc.hard_delete_user(user.id, actor)

    def test_hard_delete_succeeds_when_no_audit_rows(self, db_session: Session) -> None:
        actor = uuid4()
        svc = _svc(db_session)
        user, _ = svc.create_user("hd_clean", "hdc@test.invalid", actor)
        svc.soft_delete_user(user.id, actor)
        # No audit rows exist for this fresh user → hard delete should succeed.
        svc.hard_delete_user(user.id, actor)
        assert svc.get_user(user.id) is None


class TestResetPassword:
    def test_reset_returns_new_password(self, db_session: Session) -> None:
        actor = uuid4()
        svc = _svc(db_session)
        user, original_pw = svc.create_user("pw_reset_usr", "pwr@test.invalid", actor)
        _, new_pw = svc.reset_user_password(user.id, actor)
        assert new_pw != original_pw
        assert len(new_pw) == 16
