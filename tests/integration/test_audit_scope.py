"""Integration tests for actor_roles_json scope capture and GIN index queries."""

from uuid import uuid4

from sqlalchemy import text
from sqlmodel import Session

from durgam.audit.log import write_audit_row
from durgam.models.identity import Permission, Role, RolePermission, User, UserRole


def _make_user(session: Session, *, username: str = "") -> User:
    uname = username or f"u_{uuid4().hex[:8]}"
    user = User(
        username=uname,
        email=f"{uname}@test.com",
        password_hash="x",
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def _make_role(session: Session, code: str, level: int = 0) -> Role:
    role = Role(code=code, name=code, level=level)
    session.add(role)
    session.flush()
    return role


class TestActorRolesJsonScope:
    def test_dept_scoped_hod_roles_stored(self, db_session):
        """A dept-scoped HoD's audit row contains the correct role snapshot."""
        dept_id = uuid4()
        user = _make_user(db_session)
        hod_role = _make_role(db_session, f"HOD_{uuid4().hex[:6]}")
        basic_role = _make_role(db_session, f"BU_{uuid4().hex[:6]}")

        db_session.add(UserRole(
            user_id=user.id, role_id=hod_role.id,
            scope_type="department", scope_id=dept_id,
        ))
        db_session.add(UserRole(
            user_id=user.id, role_id=basic_role.id,
            scope_type=None, scope_id=None,
        ))
        db_session.flush()

        roles_snapshot = [
            {"role_code": hod_role.code, "scope_type": "department", "scope_id": str(dept_id)},
            {"role_code": basic_role.code, "scope_type": None, "scope_id": None},
        ]

        row = write_audit_row(
            actor_user_id=user.id,
            actor_role_code=hod_role.code,
            action="write",
            resource="department_vision_mission",
            resource_id=str(dept_id),
            request_id="req-scope-1",
            ip="10.0.0.1",
            user_agent="pytest",
            before=None,
            after={"vision": "new"},
            actor_roles_json=roles_snapshot,
            session=db_session,
        )

        assert row.actor_roles_json is not None
        assert len(row.actor_roles_json) == 2
        codes = {r["role_code"] for r in row.actor_roles_json}
        assert hod_role.code in codes
        assert basic_role.code in codes

        scoped_entries = [r for r in row.actor_roles_json if r["scope_type"] == "department"]
        assert len(scoped_entries) == 1
        assert scoped_entries[0]["scope_id"] == str(dept_id)

    def test_global_only_role_has_null_scope(self, db_session):
        """A user with only global roles has scope_type=null entries."""
        user = _make_user(db_session)
        role = _make_role(db_session, f"ADMIN_{uuid4().hex[:6]}")
        db_session.add(UserRole(
            user_id=user.id, role_id=role.id,
            scope_type=None, scope_id=None,
        ))
        db_session.flush()

        roles_snapshot = [
            {"role_code": role.code, "scope_type": None, "scope_id": None},
        ]

        row = write_audit_row(
            actor_user_id=user.id,
            actor_role_code=role.code,
            action="create",
            resource="user",
            resource_id=str(uuid4()),
            request_id=None,
            ip=None,
            user_agent=None,
            before=None,
            after={"username": "new_user"},
            actor_roles_json=roles_snapshot,
            session=db_session,
        )

        assert row.actor_roles_json == roles_snapshot
        assert all(r["scope_type"] is None for r in row.actor_roles_json)

    def test_multi_role_user_all_roles_present(self, db_session):
        """A user with 3 roles has all 3 in actor_roles_json."""
        user = _make_user(db_session)
        roles = [
            _make_role(db_session, f"R1_{uuid4().hex[:6]}"),
            _make_role(db_session, f"R2_{uuid4().hex[:6]}"),
            _make_role(db_session, f"R3_{uuid4().hex[:6]}"),
        ]
        for r in roles:
            db_session.add(UserRole(user_id=user.id, role_id=r.id))
        db_session.flush()

        roles_snapshot = [{"role_code": r.code, "scope_type": None, "scope_id": None} for r in roles]

        row = write_audit_row(
            actor_user_id=user.id,
            actor_role_code=roles[0].code,
            action="write",
            resource="campus",
            resource_id=str(uuid4()),
            request_id=None,
            ip=None,
            user_agent=None,
            before=None,
            after={"name": "Test"},
            actor_roles_json=roles_snapshot,
            session=db_session,
        )

        assert len(row.actor_roles_json) == 3

    def test_unauthenticated_login_failed_null_roles(self, db_session):
        """Login_failed has actor_roles_json=NULL (unauthenticated)."""
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

    def test_gin_containment_query(self, db_session):
        """GIN index supports @> containment query for scope filtering."""
        dept_id = uuid4()
        user = _make_user(db_session)

        roles_with_dept = [
            {"role_code": "HOD", "scope_type": "department", "scope_id": str(dept_id)},
            {"role_code": "BASIC_USER", "scope_type": None, "scope_id": None},
        ]
        roles_global_only = [
            {"role_code": "REGISTRAR", "scope_type": None, "scope_id": None},
        ]

        row1 = write_audit_row(
            actor_user_id=user.id, actor_role_code="HOD",
            action="write", resource="department_vision_mission",
            resource_id=str(dept_id), request_id=None, ip=None, user_agent=None,
            before=None, after={"vision": "v1"},
            actor_roles_json=roles_with_dept, session=db_session,
        )
        row2 = write_audit_row(
            actor_user_id=user.id, actor_role_code="REGISTRAR",
            action="write", resource="university_vision_mission",
            resource_id=str(uuid4()), request_id=None, ip=None, user_agent=None,
            before=None, after={"vision": "v2"},
            actor_roles_json=roles_global_only, session=db_session,
        )
        db_session.flush()

        result = db_session.execute(
            text(
                "SELECT id FROM audit_logs "
                "WHERE actor_roles_json @> :pattern::jsonb "
                "AND id IN (:id1, :id2)"
            ),
            {
                "pattern": f'[{{"scope_type": "department", "scope_id": "{dept_id}"}}]',
                "id1": row1.id,
                "id2": row2.id,
            },
        ).fetchall()

        matched_ids = {r[0] for r in result}
        assert row1.id in matched_ids
        assert row2.id not in matched_ids
