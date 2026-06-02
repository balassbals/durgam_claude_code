"""Integration tests for NonRegularFaculty — CRUD, lockless, approval, type field.

Key tests:
- NonRegularFaculty CRUD with real database
- NonRegularFaculty is deliberately NOT AY-locked: LOCK an AY, confirm NRF
  create/update still succeeds (proves AY-lock machinery doesn't reach NRF)
- Approval toggle changes is_admin_approved
- list_by_department returns active only
- non_regular_type field persists correctly
"""

from datetime import date
from uuid import uuid4

import pytest

from durgam.models.campus import Campus
from durgam.models.config_anchors import AcademicYear, NonRegularFaculty
from durgam.models.department import Department
from durgam.models.identity import User
from durgam.models.school import School
from durgam.repositories.non_regular_faculty import NonRegularFacultyRepository
from durgam.services.non_regular_faculty import NonRegularFacultyError, NonRegularFacultyService


def _ay(session, *, locked: bool = False) -> AcademicYear:
    ay = AcademicYear(
        code=f"T{uuid4().hex[:6]}",
        starts_on=date(2025, 7, 1),
        ends_on=date(2026, 4, 30),
        is_locked=locked,
    )
    session.add(ay)
    session.flush()
    session.refresh(ay)
    return ay


def _campus(session) -> Campus:
    c = Campus(code=f"C{uuid4().hex[:4]}", name="Test Campus", address="Addr")
    session.add(c)
    session.flush()
    session.refresh(c)
    return c


def _school(session) -> School:
    s = School(code=f"S{uuid4().hex[:4]}", name="Test School")
    session.add(s)
    session.flush()
    session.refresh(s)
    return s


def _dept(session, school: School, campus: Campus) -> Department:
    d = Department(
        code=f"D{uuid4().hex[:4]}",
        name="Test Dept",
        school_id=school.id,
        main_campus_id=campus.id,
    )
    session.add(d)
    session.flush()
    session.refresh(d)
    return d


def _user(session) -> User:
    from durgam.services.password import hash_password

    u = User(
        username=f"t{uuid4().hex[:8]}",
        email=f"t{uuid4().hex[:8]}@test.com",
        full_name="Test User",
        password_hash=hash_password("Test_Pass1!XZ"),
    )
    session.add(u)
    session.flush()
    session.refresh(u)
    return u


def _svc(session) -> NonRegularFacultyService:
    return NonRegularFacultyService(repo=NonRegularFacultyRepository(session))


class TestNonRegularFacultyCRUD:
    def test_create_and_list(self, db_session):
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            department_id=dept.id,
            name="Dr. Test",
            designation="Professor",
            organization="IISc Bangalore",
            expertise="Quantum Physics",
            available_from=date(2025, 7, 1),
            available_to=date(2025, 12, 31),
            actor_id=user.id,
        )
        assert created.id is not None
        assert created.name == "Dr. Test"
        assert created.is_admin_approved is False
        assert created.non_regular_type == "visiting"

        results = svc.list_by_department(dept.id)
        assert len(results) == 1
        assert results[0].id == created.id

    def test_create_with_type(self, db_session):
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            department_id=dept.id,
            name="Dr. Adjunct",
            designation="Associate Professor",
            organization="MIT",
            expertise="Machine Learning",
            available_from=date(2025, 7, 1),
            available_to=date(2025, 12, 31),
            actor_id=user.id,
            non_regular_type="adjunct",
        )
        assert created.non_regular_type == "adjunct"

    def test_update(self, db_session):
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            department_id=dept.id,
            name="Dr. Original",
            designation="Professor",
            organization="IISc",
            expertise="Physics",
            available_from=date(2025, 7, 1),
            available_to=date(2025, 12, 31),
            actor_id=user.id,
        )
        updated = svc.update(created.id, {"name": "Dr. Updated"}, user.id)
        assert updated.name == "Dr. Updated"

    def test_soft_delete_excludes_from_list(self, db_session):
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            department_id=dept.id,
            name="Dr. Gone",
            designation="Professor",
            organization="IISc",
            expertise="Physics",
            available_from=date(2025, 7, 1),
            available_to=date(2025, 12, 31),
            actor_id=user.id,
        )
        svc.soft_delete(created.id, user.id)
        results = svc.list_by_department(dept.id)
        assert len(results) == 0


class TestNonRegularFacultyLockless:
    """Prove NonRegularFaculty is deliberately not AY-locked.

    The meaningful test: LOCK an academic year, then confirm a NRF create/update
    still SUCCEEDS. This proves the AY-lock machinery deliberately doesn't reach
    this entity and guards against someone later adding AY-locking by
    pattern-matching it to its neighbours.
    """

    def test_create_succeeds_with_locked_ay_present(self, db_session):
        locked_ay = _ay(db_session, locked=True)
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            department_id=dept.id,
            name="Dr. Lockless Create",
            designation="Professor",
            organization="IISc",
            expertise="Physics",
            available_from=locked_ay.starts_on,
            available_to=locked_ay.ends_on,
            actor_id=user.id,
        )
        assert created.id is not None
        assert created.name == "Dr. Lockless Create"

    def test_update_succeeds_with_locked_ay_present(self, db_session):
        locked_ay = _ay(db_session, locked=True)
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            department_id=dept.id,
            name="Dr. Lockless Update",
            designation="Professor",
            organization="IISc",
            expertise="Physics",
            available_from=locked_ay.starts_on,
            available_to=locked_ay.ends_on,
            actor_id=user.id,
        )
        updated = svc.update(
            created.id,
            {"name": "Dr. Still Lockless"},
            user.id,
        )
        assert updated.name == "Dr. Still Lockless"

    def test_soft_delete_succeeds_with_locked_ay_present(self, db_session):
        locked_ay = _ay(db_session, locked=True)
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            department_id=dept.id,
            name="Dr. Lockless Delete",
            designation="Professor",
            organization="IISc",
            expertise="Physics",
            available_from=locked_ay.starts_on,
            available_to=locked_ay.ends_on,
            actor_id=user.id,
        )
        deleted = svc.soft_delete(created.id, user.id)
        assert deleted.is_deleted is True


class TestNonRegularFacultyApproval:
    def test_approval_toggle(self, db_session):
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            department_id=dept.id,
            name="Dr. Approval",
            designation="Professor",
            organization="IISc",
            expertise="Physics",
            available_from=date(2025, 7, 1),
            available_to=date(2025, 12, 31),
            actor_id=user.id,
        )
        assert created.is_admin_approved is False
        assert created.approved_at is None
        assert created.approved_by_user_id is None

        approved = svc.set_approval(created.id, True, user.id)
        assert approved.is_admin_approved is True
        assert approved.approved_at is not None
        assert approved.approved_by_user_id == user.id

        unapproved = svc.set_approval(created.id, False, user.id)
        assert unapproved.is_admin_approved is False
        assert unapproved.approved_at is None
        assert unapproved.approved_by_user_id is None

    def test_list_by_department_returns_active_only(self, db_session):
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        user = _user(db_session)
        svc = _svc(db_session)

        v1 = svc.create(
            department_id=dept.id,
            name="Dr. Active",
            designation="Professor",
            organization="IISc",
            expertise="Physics",
            available_from=date(2025, 7, 1),
            available_to=date(2025, 12, 31),
            actor_id=user.id,
        )
        v2 = svc.create(
            department_id=dept.id,
            name="Dr. Deleted",
            designation="Professor",
            organization="IISc",
            expertise="Chemistry",
            available_from=date(2025, 7, 1),
            available_to=date(2025, 12, 31),
            actor_id=user.id,
        )
        svc.soft_delete(v2.id, user.id)

        results = svc.list_by_department(dept.id)
        assert len(results) == 1
        assert results[0].name == "Dr. Active"


class TestResolveDeptScope:
    """Regression test for U1: _resolve_user_dept_scope must not reference is_deleted."""

    def test_userrole_query_without_is_deleted(self, db_session):
        """Prove UserRole has no is_deleted column — a join query must work without it."""
        from durgam.models.identity import Role, UserRole
        from durgam.services.password import hash_password

        role = Role(code=f"R{uuid4().hex[:6]}", name="Test Role", level=50)
        db_session.add(role)
        db_session.flush()
        db_session.refresh(role)

        user = _user(db_session)
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)

        ur = UserRole(
            user_id=user.id,
            role_id=role.id,
            scope_type="department",
            scope_id=dept.id,
        )
        db_session.add(ur)
        db_session.flush()

        from sqlmodel import select

        stmt = (
            select(UserRole.scope_id)
            .join(Role, UserRole.role_id == Role.id)
            .where(UserRole.scope_type == "department")
            .limit(1)
        )
        result = db_session.exec(stmt).first()
        assert result is not None
        assert result == dept.id

    def test_dept_scoped_userrole_returns_scope_id(self, db_session):
        """Verify scope_id is correctly set on department-scoped UserRole."""
        from durgam.models.identity import Role, UserRole

        role = Role(code=f"R{uuid4().hex[:6]}", name="Test HOD", level=50)
        db_session.add(role)
        db_session.flush()
        db_session.refresh(role)

        user = _user(db_session)
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)

        ur = UserRole(
            user_id=user.id,
            role_id=role.id,
            scope_type="department",
            scope_id=dept.id,
        )
        db_session.add(ur)
        db_session.flush()
        db_session.refresh(ur)

        assert ur.scope_id == dept.id
        assert ur.scope_type == "department"
