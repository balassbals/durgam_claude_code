"""Integration tests for NonOwnedCourse — CRUD + AY-lock.

Key tests:
- NonOwnedCourse CRUD with real database
- AY-lock: locked AY rejects save with AcademicYearLockedError
- AY-lock: locked AY rejects soft_delete with AcademicYearLockedError
- AY-lock: unlocked AY succeeds for save + soft_delete
- list_by_ay returns active only
"""

from datetime import date
from uuid import uuid4

import pytest

from durgam.models.config_anchors import AcademicYear, NonOwnedCourse
from durgam.models.identity import User
from durgam.repositories.non_owned_course import NonOwnedCourseRepository
from durgam.services.non_owned_course import NonOwnedCourseError, NonOwnedCourseService
from durgam.services.org_exceptions import AcademicYearLockedError


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


def _faculty(session):
    """Minimal Faculty to satisfy non_owned_courses.faculty_id FK (M10 Phase 11B)."""
    from datetime import UTC, datetime

    from durgam.models.campus import Campus
    from durgam.models.config_anchors import Designation
    from durgam.models.department import Department
    from durgam.models.faculty import Faculty
    from durgam.models.school import School

    campus = Campus(code=f"C{uuid4().hex[:4]}", name="Test Campus", address="Addr")
    school = School(code=f"S{uuid4().hex[:4]}", name="Test School")
    session.add_all([campus, school])
    session.flush()
    dept = Department(
        code=f"D{uuid4().hex[:4]}", name="Test Dept",
        school_id=school.id, main_campus_id=campus.id,
    )
    desig = Designation(code=f"DG{uuid4().hex[:4]}", name="Prof", rank=50)
    session.add_all([dept, desig])
    session.flush()
    user = _user(session)
    now = datetime.now(UTC)
    f = Faculty(
        user_id=user.id, employee_id=f"FAC-{uuid4().hex[:8]}", title="Dr",
        first_name="F", last_name="N", designation_id=desig.id,
        department_id=dept.id, campus_id=campus.id, joining_date=date(2020, 1, 1),
        phone="9", emergency_contact_name="E", emergency_contact_relation="P",
        emergency_contact_phone="9", created_at=now, updated_at=now,
    )
    session.add(f)
    session.flush()
    return f


def _svc(session) -> NonOwnedCourseService:
    return NonOwnedCourseService(repo=NonOwnedCourseRepository(session))


class TestNonOwnedCourseCRUD:
    def test_create_and_list(self, db_session):
        ay = _ay(db_session)
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            academic_year_id=ay.id,
            course_code="MDC101",
            course_name="Moral and Divine Culture",
            credits=2,
            semester="odd",
            faculty_id=_faculty(db_session).id,
            actor_id=user.id,
        )
        assert created.id is not None
        assert created.course_code == "MDC101"

        results = svc.list_by_ay(ay.id)
        assert len(results) == 1
        assert results[0].id == created.id

    def test_update(self, db_session):
        ay = _ay(db_session)
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            academic_year_id=ay.id,
            course_code="AWR101",
            course_name="Awareness",
            credits=1,
            semester="even",
            faculty_id=_faculty(db_session).id,
            actor_id=user.id,
        )
        updated = svc.update(created.id, {"course_name": "Updated Awareness"}, user.id)
        assert updated.course_name == "Updated Awareness"

    def test_soft_delete_excludes_from_list(self, db_session):
        ay = _ay(db_session)
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            academic_year_id=ay.id,
            course_code="DEL101",
            course_name="To Delete",
            credits=0,
            semester="odd",
            faculty_id=_faculty(db_session).id,
            actor_id=user.id,
        )
        svc.soft_delete(created.id, user.id)
        results = svc.list_by_ay(ay.id)
        assert len(results) == 0


class TestNonOwnedCourseAYLock:
    """AY-lock tests for NonOwnedCourse — locked AY rejects writes."""

    def test_locked_ay_rejects_save(self, db_session):
        locked_ay = _ay(db_session, locked=True)
        user = _user(db_session)
        svc = _svc(db_session)

        with pytest.raises(AcademicYearLockedError):
            svc.create(
                academic_year_id=locked_ay.id,
                course_code="LOCK01",
                course_name="Locked",
                credits=1,
                semester="odd",
                faculty_id=_faculty(db_session).id,
                actor_id=user.id,
            )

    def test_locked_ay_rejects_soft_delete(self, db_session):
        unlocked_ay = _ay(db_session, locked=False)
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            academic_year_id=unlocked_ay.id,
            course_code="LOCKD1",
            course_name="Will Lock",
            credits=1,
            semester="odd",
            faculty_id=_faculty(db_session).id,
            actor_id=user.id,
        )
        unlocked_ay.is_locked = True
        db_session.add(unlocked_ay)
        db_session.flush()

        with pytest.raises(AcademicYearLockedError):
            svc.soft_delete(created.id, user.id)

    def test_unlocked_ay_succeeds(self, db_session):
        unlocked_ay = _ay(db_session, locked=False)
        user = _user(db_session)
        svc = _svc(db_session)

        created = svc.create(
            academic_year_id=unlocked_ay.id,
            course_code="OPEN01",
            course_name="Open Course",
            credits=2,
            semester="even",
            faculty_id=_faculty(db_session).id,
            actor_id=user.id,
        )
        assert created.id is not None

        updated = svc.update(created.id, {"course_name": "Still Open"}, user.id)
        assert updated.course_name == "Still Open"

        deleted = svc.soft_delete(created.id, user.id)
        assert deleted.is_deleted is True
