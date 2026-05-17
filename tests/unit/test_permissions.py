"""Unit tests for can() scope_id discrimination (§7.2, M2 gate prerequisite).

Uses the db_session fixture (real PostgreSQL via rollback-per-test) because
can() executes SQL. Tests are in tests/unit/ per M2 implementation discipline.

These cases must hold before the permission-check widget can be wired into
the M2 gate demo — if can() grants for the wrong reason, the gate proves nothing.

Implementation note: every helper call generates a unique resource name to avoid
colliding with seeded permissions visible under PostgreSQL READ COMMITTED isolation
(the seeded_db_engine fixture commits data that db_session tests can see).
"""

from uuid import uuid4

from sqlmodel import Session

from durgam.auth.permissions import can
from durgam.models.identity import Permission, Role, RolePermission, User, UserRole


def _make_scoped_user(
    session: Session,
    *,
    scope_type: str | None,
    scope_id: object,
    perm_action: str = "read",
) -> tuple[User, str]:
    """Insert an active user with one role and one permission; return (user, resource_name).

    The resource name is unique per call so inserts never collide with seeded
    permissions regardless of READ COMMITTED visibility.
    The permission scope is inferred from scope_type (or '*' for unscoped users).
    """
    suffix = uuid4().hex[:8]
    user = User(
        username=f"u_{suffix}",
        email=f"u_{suffix}@test.invalid",
        password_hash="x",
        is_active=True,
    )
    session.add(user)

    role = Role(code=f"R_{suffix}", name="Test Role", level=10)
    session.add(role)

    resource = f"res_{suffix}"
    perm_scope = scope_type if scope_type is not None else "*"
    perm = Permission(resource=resource, action=perm_action, scope=perm_scope)
    session.add(perm)
    session.flush()

    session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    session.add(
        UserRole(user_id=user.id, role_id=role.id, scope_type=scope_type, scope_id=scope_id)
    )
    session.flush()

    return user, resource


class TestCanScopeIdDiscrimination:
    """Verify can() discriminates by scope_id when UserRole carries a specific scope_id."""

    def test_matching_scope_id_grants(self, db_session: Session) -> None:
        scope_id = uuid4()
        user, resource = _make_scoped_user(
            db_session, scope_type="department", scope_id=scope_id
        )

        assert can(
            user.id, "read", resource,
            scope_type="department", scope_id=scope_id,
            session=db_session,
        ) is True, "exact scope_id match must grant"

    def test_different_scope_id_denies(self, db_session: Session) -> None:
        scope_id_x = uuid4()
        scope_id_y = uuid4()
        user, resource = _make_scoped_user(
            db_session, scope_type="department", scope_id=scope_id_x
        )

        assert can(
            user.id, "read", resource,
            scope_type="department", scope_id=scope_id_y,
            session=db_session,
        ) is False, "non-matching scope_id must deny"

    def test_none_scope_id_in_check_denies_when_role_has_specific_scope(
        self, db_session: Session
    ) -> None:
        """scope_id=None in the can() call must NOT match a UserRole with scope_id=X.

        A user with a permission scoped to department X must not be considered
        to hold that permission over an unspecified department.
        This was a latent bug in the M0 implementation surfaced at M2 planning.
        """
        scope_id = uuid4()
        user, resource = _make_scoped_user(
            db_session, scope_type="department", scope_id=scope_id
        )

        assert can(
            user.id, "read", resource,
            scope_type="department", scope_id=None,
            session=db_session,
        ) is False, "scope_id=None in check must not match a role with a specific scope_id"

    def test_global_role_within_scope_type_grants_any_scope_id(
        self, db_session: Session
    ) -> None:
        """UserRole with scope_id=None applies to all objects within that scope_type.

        Checking with any specific scope_id must return True.
        """
        user, resource = _make_scoped_user(
            db_session,
            scope_type="department",
            scope_id=None,  # role covers all departments
        )

        assert can(
            user.id, "read", resource,
            scope_type="department", scope_id=uuid4(),
            session=db_session,
        ) is True, "UserRole with scope_id=None must grant for any scope_id within scope_type"

    def test_global_role_wildcard_permission_grants_regardless_of_scope(
        self, db_session: Session
    ) -> None:
        """UserRole with scope_type=None and '*'-scoped permission grants for any check."""
        user, resource = _make_scoped_user(
            db_session,
            scope_type=None,  # no scope restriction on the role
            scope_id=None,
        )

        assert can(
            user.id, "read", resource,
            scope_type=None, scope_id=None,
            session=db_session,
        ) is True, "global role with '*' permission must grant for unscoped checks"

        assert can(
            user.id, "read", resource,
            scope_type="department", scope_id=uuid4(),
            session=db_session,
        ) is True, "global role must also grant for scoped checks"
