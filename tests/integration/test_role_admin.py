"""Integration tests for RoleAdminService + real PostgreSQL (gate clause)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlmodel import Session

from durgam.auth.permissions import can
from durgam.repositories.permission import PermissionRepository
from durgam.repositories.role import RoleRepository
from durgam.repositories.user import UserRepository
from durgam.repositories.user_role import UserRoleRepository
from durgam.services.role_admin import RoleAdminError, RoleAdminService
from durgam.services.user_admin import UserAdminService


def _role_svc(session: Session) -> RoleAdminService:
    return RoleAdminService(
        role_repo=RoleRepository(session),
        permission_repo=PermissionRepository(session),
    )


def _user_svc(session: Session) -> UserAdminService:
    return UserAdminService(
        user_repo=UserRepository(session),
        user_role_repo=UserRoleRepository(session),
    )


class TestCreateRole:
    def test_create_role_appears_in_list(self, db_session: Session) -> None:
        actor = uuid4()
        svc = _role_svc(db_session)
        svc.create_role("INT_TESTROLE", "Integration Test Role", 25, None, actor)
        roles = svc.list_roles()
        codes = [r.code for r in roles]
        assert "INT_TESTROLE" in codes

    def test_duplicate_code_raises(self, db_session: Session) -> None:
        actor = uuid4()
        svc = _role_svc(db_session)
        svc.create_role("DUPROLE2", "Dup Role 2", 10, None, actor)
        with pytest.raises(RoleAdminError, match="already in use"):
            svc.create_role("DUPROLE2", "Dup Again", 10, None, actor)


class TestPermissionAssignmentAndCanCheck:
    """Direct integration test of the M2 gate clause:
    'System Admin can construct any role and verify scoped permissions.'
    """

    def test_role_with_permission_grants_can(self, db_session: Session) -> None:
        actor_id = uuid4()

        # Create a user
        user_svc = _user_svc(db_session)
        user, _ = user_svc.create_user("gate_test_user", "gate@test.invalid", actor_id)

        # Create a role
        role_svc = _role_svc(db_session)
        role = role_svc.create_role("GATE_ROLE", "Gate Role", 20, None, actor_id)

        # Create a unique permission for this test run to avoid collision with seeded data.
        from durgam.models.identity import Permission
        unique_resource = f"dept_gate_{uuid4().hex[:8]}"
        perm = Permission(resource=unique_resource, action="read", scope="department")
        db_session.add(perm)
        db_session.flush()

        # Assign permission to role
        role_svc.update_permissions(role.id, [perm.id], actor_id)

        # Assign role to user scoped to a specific department.
        # UserRole PK is (user_id, role_id) — each role is held once, with scope metadata.
        scope_id = uuid4()
        from durgam.models.identity import UserRole
        db_session.add(UserRole(
            user_id=user.id,
            role_id=role.id,
            scope_type="department",
            scope_id=scope_id,
        ))
        db_session.flush()

        # Gate check: can() must return True for matching scope_id
        result = can(
            user_id=user.id,
            action="read",
            resource=unique_resource,
            scope_type="department",
            scope_id=scope_id,
            session=db_session,
        )
        assert result is True, "Gate clause: scoped permission must grant for matching scope_id"

        # Gate check: can() must return False for different scope_id
        other_dept = uuid4()
        result_other = can(
            user_id=user.id,
            action="read",
            resource=unique_resource,
            scope_type="department",
            scope_id=other_dept,
            session=db_session,
        )
        assert result_other is False, "Gate clause: must deny for a different scope_id"

        # Gate check: can() must return False for scope_id=None
        result_none = can(
            user_id=user.id,
            action="read",
            resource=unique_resource,
            scope_type="department",
            scope_id=None,
            session=db_session,
        )
        assert result_none is False, "Gate clause: must deny for scope_id=None"
