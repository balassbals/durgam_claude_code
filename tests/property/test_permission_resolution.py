"""Hypothesis property tests for can() permission resolution (rules-engine ≥95%).

These tests verify that can() never grants access beyond what was explicitly
assigned, regardless of the combination of roles and permissions.

Each hypothesis example creates its own DB session to avoid state accumulation
across examples (hypothesis runs multiple examples within one test function;
the function-scoped db_session does not reset between examples).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

import durgam.models  # noqa: F401 — populate metadata
from durgam.auth.permissions import can
from durgam.config import settings as app_settings
from durgam.models.identity import Permission, Role, RolePermission, User, UserRole


def _with_fresh_session(fn):
    """Run fn with a fresh DB connection that rolls back on exit."""
    engine = create_engine(app_settings.test_database_url, echo=False)
    SQLModel.metadata.create_all(engine)
    conn = engine.connect()
    tx = conn.begin()
    try:
        with Session(bind=conn) as session:
            return fn(session)
    finally:
        try:
            tx.rollback()
        except Exception:
            pass
        conn.close()
        engine.dispose()


def _seed_scenario(
    session: Session,
    *,
    scope_type: str | None,
    role_scope_id: UUID | None,
) -> tuple[User, str, str]:
    suffix = uuid4().hex[:8]
    user = User(username=f"h_{suffix}", email=f"h_{suffix}@h.invalid", password_hash="x",
                is_active=True)
    session.add(user)
    role = Role(code=f"HR_{suffix}", name="Hyp Role", level=5)
    session.add(role)
    resource = f"hyp_{suffix}"
    perm_scope = scope_type if scope_type is not None else "*"
    perm = Permission(resource=resource, action="read", scope=perm_scope)
    session.add(perm)
    session.flush()
    session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    session.add(UserRole(user_id=user.id, role_id=role.id, scope_type=scope_type,
                         scope_id=role_scope_id))
    session.flush()
    return user, resource, "read"


class TestCanNeverGrantsBeyondAssignment:
    @settings(max_examples=15)
    @given(scope_type=st.one_of(st.none(), st.sampled_from(["department", "campus"])))
    def test_unassigned_resource_always_denied(self, scope_type) -> None:
        """A user with no permissions on 'other_resource' must always get False."""
        def run(session: Session) -> None:
            user, resource, action = _seed_scenario(
                session, scope_type=scope_type, role_scope_id=None
            )
            other = "other_" + uuid4().hex[:6]
            result = can(user_id=user.id, action=action, resource=other,
                         scope_type=scope_type, scope_id=None, session=session)
            assert result is False, (
                f"can() must not grant access to '{other}' which was never assigned"
            )

        _with_fresh_session(run)

    @settings(max_examples=15)
    @given(scope_type=st.sampled_from(["department", "campus"]))
    def test_specific_scope_id_never_leaks_to_other_scope(self, scope_type) -> None:
        """A role scoped to scope_id=X must not grant access at scope_id=Y."""
        def run(session: Session) -> None:
            x = uuid4()
            y = uuid4()
            user, resource, action = _seed_scenario(
                session, scope_type=scope_type, role_scope_id=x
            )
            result = can(user_id=user.id, action=action, resource=resource,
                         scope_type=scope_type, scope_id=y, session=session)
            assert result is False, (
                f"can() must not grant scope {scope_type}:{y} when role is scoped to {x}"
            )

        _with_fresh_session(run)
