"""Integration tests for M5b assignment repos — AY-lock enforcement.

Each AY-locked entity gets its own explicit test proving that:
1. save() on a locked AY raises AcademicYearLockedError
2. soft_delete() on a locked AY raises AcademicYearLockedError
3. save() on an unlocked AY succeeds
"""

from datetime import date
from uuid import uuid4

import pytest

from durgam.models.campus import Campus
from durgam.models.config_anchors import (
    AcademicYear,
    ClassCoordinatorAssignment,
    ClassTeacherAssignment,
    FacultyMentorAssignment,
    MentalHealthCounsellor,
)
from durgam.models.department import Department
from durgam.models.identity import User
from durgam.models.school import School
from durgam.repositories.assignment import AssignmentRepository
from durgam.repositories.mental_health_counsellor import (
    MentalHealthCounsellorRepository,
)
from durgam.services.assignment import (
    AssignmentError,
    ClassCoordinatorService,
)
from durgam.services.org_exceptions import AcademicYearLockedError


# ── Helpers ──────────────────────────────────────────────────────────────────


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
    s = School(code=f"S{uuid4().hex[:4]}", name="Test School", dean_role_code="DEAN")
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


# ── MentalHealthCounsellor AY-lock ──────────────────────────────────────────


class TestCounsellorAYLock:
    def test_save_on_locked_ay_raises(self, db_session):
        ay = _ay(db_session, locked=True)
        campus = _campus(db_session)
        record = MentalHealthCounsellor(
            academic_year_id=ay.id,
            campus_id=campus.id,
            name="Dr. Test",
            qualification="PhD",
            specialisation="Clinical",
            mode_of_appointment="inhouse",
            appointment_start=date(2025, 7, 1),
            appointment_end=date(2026, 4, 30),
        )
        repo = MentalHealthCounsellorRepository(db_session)
        with pytest.raises(AcademicYearLockedError):
            repo.save(record)

    def test_soft_delete_on_locked_ay_raises(self, db_session):
        ay = _ay(db_session)
        campus = _campus(db_session)
        user = _user(db_session)
        record = MentalHealthCounsellor(
            academic_year_id=ay.id,
            campus_id=campus.id,
            name="Dr. Test",
            qualification="PhD",
            specialisation="Clinical",
            mode_of_appointment="inhouse",
            appointment_start=date(2025, 7, 1),
            appointment_end=date(2026, 4, 30),
        )
        repo = MentalHealthCounsellorRepository(db_session)
        saved = repo.save(record)

        ay.is_locked = True
        db_session.flush()

        with pytest.raises(AcademicYearLockedError):
            repo.soft_delete(saved, actor_id=user.id)

    def test_save_on_unlocked_ay_succeeds(self, db_session):
        ay = _ay(db_session)
        campus = _campus(db_session)
        record = MentalHealthCounsellor(
            academic_year_id=ay.id,
            campus_id=campus.id,
            name="Dr. Success",
            qualification="PhD",
            specialisation="Clinical",
            mode_of_appointment="external",
            appointment_start=date(2025, 7, 1),
            appointment_end=date(2026, 4, 30),
        )
        repo = MentalHealthCounsellorRepository(db_session)
        saved = repo.save(record)
        assert saved.id is not None
        assert saved.name == "Dr. Success"


# ── FacultyMentorAssignment AY-lock ─────────────────────────────────────────


class TestFacultyMentorAYLock:
    def test_save_on_locked_ay_raises(self, db_session):
        ay = _ay(db_session, locked=True)
        campus = _campus(db_session)
        record = FacultyMentorAssignment(
            academic_year_id=ay.id,
            campus_id=campus.id,
            faculty_id_placeholder="FAC001",
            student_id_placeholder="STU001",
        )
        repo = AssignmentRepository(FacultyMentorAssignment, db_session)
        with pytest.raises(AcademicYearLockedError):
            repo.save(record)

    def test_soft_delete_on_locked_ay_raises(self, db_session):
        ay = _ay(db_session)
        campus = _campus(db_session)
        user = _user(db_session)
        record = FacultyMentorAssignment(
            academic_year_id=ay.id,
            campus_id=campus.id,
            faculty_id_placeholder="FAC001",
            student_id_placeholder="STU001",
        )
        repo = AssignmentRepository(FacultyMentorAssignment, db_session)
        saved = repo.save(record)

        ay.is_locked = True
        db_session.flush()

        with pytest.raises(AcademicYearLockedError):
            repo.soft_delete(saved, actor_id=user.id)

    def test_save_on_unlocked_ay_succeeds(self, db_session):
        ay = _ay(db_session)
        campus = _campus(db_session)
        record = FacultyMentorAssignment(
            academic_year_id=ay.id,
            campus_id=campus.id,
            faculty_id_placeholder="FAC001",
            student_id_placeholder="STU001",
        )
        repo = AssignmentRepository(FacultyMentorAssignment, db_session)
        saved = repo.save(record)
        assert saved.id is not None


# ── ClassTeacherAssignment AY-lock ───────────────────────────────────────────


class TestClassTeacherAYLock:
    def test_save_on_locked_ay_raises(self, db_session):
        ay = _ay(db_session, locked=True)
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        record = ClassTeacherAssignment(
            academic_year_id=ay.id,
            department_id=dept.id,
            faculty_id_placeholder="FAC002",
            class_identifier="BSc-I-A",
        )
        repo = AssignmentRepository(ClassTeacherAssignment, db_session)
        with pytest.raises(AcademicYearLockedError):
            repo.save(record)

    def test_soft_delete_on_locked_ay_raises(self, db_session):
        ay = _ay(db_session)
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        user = _user(db_session)
        record = ClassTeacherAssignment(
            academic_year_id=ay.id,
            department_id=dept.id,
            faculty_id_placeholder="FAC002",
            class_identifier="BSc-I-A",
        )
        repo = AssignmentRepository(ClassTeacherAssignment, db_session)
        saved = repo.save(record)

        ay.is_locked = True
        db_session.flush()

        with pytest.raises(AcademicYearLockedError):
            repo.soft_delete(saved, actor_id=user.id)

    def test_save_on_unlocked_ay_succeeds(self, db_session):
        ay = _ay(db_session)
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        record = ClassTeacherAssignment(
            academic_year_id=ay.id,
            department_id=dept.id,
            faculty_id_placeholder="FAC002",
            class_identifier="BSc-I-A",
        )
        repo = AssignmentRepository(ClassTeacherAssignment, db_session)
        saved = repo.save(record)
        assert saved.id is not None


# ── ClassCoordinatorAssignment AY-lock ───────────────────────────────────────


class TestClassCoordinatorAYLock:
    def test_save_on_locked_ay_raises(self, db_session):
        ay = _ay(db_session, locked=True)
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        record = ClassCoordinatorAssignment(
            academic_year_id=ay.id,
            department_id=dept.id,
            faculty_id_placeholder="FAC003",
            class_identifier="BSc-II-A",
        )
        repo = AssignmentRepository(ClassCoordinatorAssignment, db_session)
        with pytest.raises(AcademicYearLockedError):
            repo.save(record)

    def test_soft_delete_on_locked_ay_raises(self, db_session):
        ay = _ay(db_session)
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        user = _user(db_session)
        record = ClassCoordinatorAssignment(
            academic_year_id=ay.id,
            department_id=dept.id,
            faculty_id_placeholder="FAC003",
            class_identifier="BSc-II-A",
        )
        repo = AssignmentRepository(ClassCoordinatorAssignment, db_session)
        saved = repo.save(record)

        ay.is_locked = True
        db_session.flush()

        with pytest.raises(AcademicYearLockedError):
            repo.soft_delete(saved, actor_id=user.id)

    def test_save_on_unlocked_ay_succeeds(self, db_session):
        ay = _ay(db_session)
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        record = ClassCoordinatorAssignment(
            academic_year_id=ay.id,
            department_id=dept.id,
            faculty_id_placeholder="FAC003",
            class_identifier="BSc-II-A",
        )
        repo = AssignmentRepository(ClassCoordinatorAssignment, db_session)
        saved = repo.save(record)
        assert saved.id is not None


# ── Max-2-coordinator integration test ───────────────────────────────────────


class TestMaxTwoCoordinators:
    def test_third_coordinator_same_class_raises(self, db_session):
        ay = _ay(db_session)
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        user = _user(db_session)

        repo = AssignmentRepository(ClassCoordinatorAssignment, db_session)
        svc = ClassCoordinatorService(repo=repo)

        svc.create(
            academic_year_id=ay.id,
            department_id=dept.id,
            faculty_id_placeholder="FAC_A",
            class_identifier="BSc-III-A",
            actor_id=user.id,
        )
        svc.create(
            academic_year_id=ay.id,
            department_id=dept.id,
            faculty_id_placeholder="FAC_B",
            class_identifier="BSc-III-A",
            actor_id=user.id,
        )

        with pytest.raises(AssignmentError, match="Maximum 2"):
            svc.create(
                academic_year_id=ay.id,
                department_id=dept.id,
                faculty_id_placeholder="FAC_C",
                class_identifier="BSc-III-A",
                actor_id=user.id,
            )

    def test_different_class_allows_more(self, db_session):
        ay = _ay(db_session)
        campus = _campus(db_session)
        school = _school(db_session)
        dept = _dept(db_session, school, campus)
        user = _user(db_session)

        repo = AssignmentRepository(ClassCoordinatorAssignment, db_session)
        svc = ClassCoordinatorService(repo=repo)

        svc.create(
            academic_year_id=ay.id,
            department_id=dept.id,
            faculty_id_placeholder="FAC_A",
            class_identifier="BSc-I-A",
            actor_id=user.id,
        )
        svc.create(
            academic_year_id=ay.id,
            department_id=dept.id,
            faculty_id_placeholder="FAC_B",
            class_identifier="BSc-I-A",
            actor_id=user.id,
        )

        result = svc.create(
            academic_year_id=ay.id,
            department_id=dept.id,
            faculty_id_placeholder="FAC_C",
            class_identifier="BSc-I-B",
            actor_id=user.id,
        )
        assert result.class_identifier == "BSc-I-B"
