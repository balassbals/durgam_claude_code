"""Integration tests for VisitingFaculty — CRUD, lockless, approval.

Key tests:
- VisitingFaculty CRUD with real database
- VisitingFaculty is deliberately NOT AY-locked: LOCK an AY, confirm VF
  create/update still succeeds (proves AY-lock machinery doesn't reach VF)
- Approval toggle changes is_admin_approved
- list_by_department returns active only
"""

from datetime import date
from uuid import uuid4

import pytest

from durgam.models.campus import Campus
from durgam.models.config_anchors import AcademicYear, VisitingFaculty
from durgam.models.department import Department
from durgam.models.identity import User
from durgam.models.school import School
from durgam.repositories.visiting_faculty import VisitingFacultyRepository
from durgam.services.visiting_faculty import VisitingFacultyError, VisitingFacultyService


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


def _svc(session) -> VisitingFacultyService:
    return VisitingFacultyService(repo=VisitingFacultyRepository(session))


class TestVisitingFacultyCRUD:
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

        results = svc.list_by_department(dept.id)
        assert len(results) == 1
        assert results[0].id == created.id

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


class TestVisitingFacultyLockless:
    """Prove VisitingFaculty is deliberately not AY-locked.

    The meaningful test: LOCK an academic year, then confirm a VF create/update
    still SUCCEEDS. This proves the AY-lock machinery deliberately doesn't reach
    this entity and guards against someone later adding AY-locking by
    pattern-matching it to its neighbours.
    """

    def test_create_succeeds_with_locked_ay_present(self, db_session):
        """Lock an AY, then create a VF — proves VF is not AY-scoped."""
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
        """Lock an AY, then update a VF — proves VF ignores AY-lock."""
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
        """Lock an AY, then soft-delete a VF — proves VF ignores AY-lock."""
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


class TestVisitingFacultyApproval:
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

        approved = svc.set_approval(created.id, True, user.id)
        assert approved.is_admin_approved is True

        unapproved = svc.set_approval(created.id, False, user.id)
        assert unapproved.is_admin_approved is False

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
