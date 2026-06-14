"""Integration tests for can() and write_audit_row() against real PostgreSQL."""

from uuid import UUID, uuid4

from sqlmodel import Session

from durgam.audit.log import write_audit_row
from durgam.auth.permissions import can
from durgam.models.identity import Permission, Role, RolePermission, User, UserRole


def _make_user(session: Session, *, active: bool = True, deleted: bool = False) -> User:
    user = User(
        username=f"u_{uuid4().hex[:8]}",
        email=f"u_{uuid4().hex[:8]}@test.com",
        password_hash="x",
        is_active=active,
        is_deleted=deleted,
    )
    session.add(user)
    session.flush()
    return user


def _grant(session: Session, user: User, action: str, resource: str, scope: str) -> None:
    role = Role(code=f"R_{uuid4().hex[:8]}", name="R", level=1)
    perm = Permission(resource=resource, action=action, scope=scope)
    session.add_all([role, perm])
    session.flush()
    session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    session.add(UserRole(user_id=user.id, role_id=role.id))
    session.flush()


def _grant_scoped(
    session: Session,
    user: User,
    action: str,
    resource: str,
    perm_scope: str,
    *,
    role_scope_type: str,
    role_scope_id: UUID | None = None,
) -> None:
    """Like _grant but binds the UserRole to a specific scope_type/scope_id."""
    role = Role(code=f"R_{uuid4().hex[:8]}", name="R", level=1)
    perm = Permission(resource=resource, action=action, scope=perm_scope)
    session.add_all([role, perm])
    session.flush()
    session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    session.add(UserRole(
        user_id=user.id,
        role_id=role.id,
        scope_type=role_scope_type,
        scope_id=role_scope_id,
    ))
    session.flush()


class TestCan:
    def test_permitted_principal_returns_true(self, db_session):
        user = _make_user(db_session)
        _grant(db_session, user, "read", "report", "*")
        assert can(user.id, "read", "report", "*", None, db_session) is True

    def test_denied_principal_returns_false(self, db_session):
        user = _make_user(db_session)
        assert can(user.id, "delete", "report", "*", None, db_session) is False

    def test_inactive_user_denied(self, db_session):
        user = _make_user(db_session, active=False)
        _grant(db_session, user, "read", "report", "*")
        assert can(user.id, "read", "report", "*", None, db_session) is False

    def test_soft_deleted_user_denied(self, db_session):
        user = _make_user(db_session, deleted=True)
        _grant(db_session, user, "read", "report", "*")
        assert can(user.id, "read", "report", "*", None, db_session) is False

    def test_wildcard_scope_grants_any_scope_type(self, db_session):
        user = _make_user(db_session)
        _grant(db_session, user, "approve", "leave_request", "*")
        assert can(user.id, "approve", "leave_request", "department", None, db_session) is True

    def test_scoped_permission_denied_for_different_scope(self, db_session):
        user = _make_user(db_session)
        _grant(db_session, user, "approve", "leave_request", "department")
        assert can(user.id, "approve", "leave_request", "campus", None, db_session) is False

    def test_can_scope_wildcard_request_accepts_scoped_user_role(self, db_session) -> None:
        """Regression: a campus-scoped UserRole with announcement:create:* grant
        must satisfy a scope_type='*' request. Pre-fix, scoped roles were
        filtered out before their permissions were examined.
        """
        campus_id = uuid4()  # no FK enforcement on UserRole.scope_id
        user = _make_user(db_session)
        _grant_scoped(
            db_session, user, "create", "announcement", "*",
            role_scope_type="campus",
            role_scope_id=campus_id,
        )

        result = can(
            user_id=user.id,
            action="create",
            resource="announcement",
            scope_type="*",
            scope_id=None,
            session=db_session,
        )
        assert result is True, (
            "Scoped UserRole must satisfy scope_type='*' request when the "
            "permission's scope is '*' — pre-fix this returned False."
        )

    def test_can_scope_own_request_accepts_scoped_user_role(self, db_session) -> None:
        """Regression: a campus-scoped UserRole with announcement:soft_delete:own
        grant must satisfy a scope_type='own' request. Phase 7.1 handled scope='*';
        Phase 8b.2 extends the same fix to scope='own' since neither is a structural
        role-scope (both are operation-level semantics: '*'=global, 'own'=per-instance
        ownership checked by handler body).
        """
        campus_id = uuid4()  # no FK enforcement on UserRole.scope_id
        user = _make_user(db_session)
        _grant_scoped(
            db_session, user, "soft_delete", "announcement", "own",
            role_scope_type="campus",
            role_scope_id=campus_id,
        )

        result = can(
            user_id=user.id,
            action="soft_delete",
            resource="announcement",
            scope_type="own",
            scope_id=None,
            session=db_session,
        )
        assert result is True, (
            "Campus-scoped UserRole must satisfy scope_type='own' request — "
            "'own' is not a structural role-scope; pre-fix this returned False."
        )


class TestWriteAuditRow:
    def test_creates_row_with_diff(self, db_session):
        actor = uuid4()
        row = write_audit_row(
            actor_user_id=actor,
            actor_role_code="ADMIN",
            action="update",
            resource="user",
            resource_id="user-123",
            request_id="req-1",
            ip="127.0.0.1",
            user_agent="pytest",
            before={"name": "Alice"},
            after={"name": "Bob"},
            session=db_session,
        )
        assert row.id is not None
        assert row.diff_json == {"name": ["Alice", "Bob"]}
        assert row.actor_user_id == actor

    def test_creation_diff_is_all_none_to_value(self, db_session):
        row = write_audit_row(
            actor_user_id=None,
            actor_role_code=None,
            action="create",
            resource="role",
            resource_id="role-1",
            request_id=None,
            ip=None,
            user_agent=None,
            before=None,
            after={"code": "DEAN"},
            session=db_session,
        )
        assert row.diff_json == {"code": [None, "DEAN"]}

    def test_no_diff_if_nothing_changed(self, db_session):
        row = write_audit_row(
            actor_user_id=None,
            actor_role_code=None,
            action="noop",
            resource="x",
            resource_id=None,
            request_id=None,
            ip=None,
            user_agent=None,
            before={"a": 1},
            after={"a": 1},
            session=db_session,
        )
        assert row.diff_json == {}

    def test_actor_roles_json_stored(self, db_session):
        actor = uuid4()
        roles = [
            {"role_code": "HOD", "scope_type": "department", "scope_id": str(uuid4())},
            {"role_code": "BASIC_USER", "scope_type": None, "scope_id": None},
        ]
        row = write_audit_row(
            actor_user_id=actor,
            actor_role_code="HOD",
            action="write",
            resource="department_vision_mission",
            resource_id="dept-1",
            request_id="req-2",
            ip="10.0.0.1",
            user_agent="pytest",
            before=None,
            after={"vision": "new"},
            actor_roles_json=roles,
            session=db_session,
        )
        assert row.actor_roles_json == roles
        assert len(row.actor_roles_json) == 2
        assert row.actor_roles_json[0]["role_code"] == "HOD"

    def test_actor_roles_json_null_for_unauthenticated(self, db_session):
        row = write_audit_row(
            actor_user_id=None,
            actor_role_code=None,
            action="login_failed",
            resource="session",
            resource_id="baduser",
            request_id=None,
            ip="1.2.3.4",
            user_agent="browser",
            before=None,
            after={"reason": "invalid_credentials"},
            actor_roles_json=None,
            session=db_session,
        )
        assert row.actor_roles_json is None
