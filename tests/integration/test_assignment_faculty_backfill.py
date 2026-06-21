"""Integration tests for M10 Phase 11A faculty_id backfill on assignment tables.

Verifies the faculty_id FK + the shared employee_id→faculty_id resolution helpers
against real PostgreSQL. Extended per table across 11A's per-table commits;
table 1 = faculty_mentor_assignments.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlmodel import Session

from durgam.models.campus import Campus
from durgam.models.config_anchors import Designation, FacultyMentorAssignment
from durgam.models.department import Department
from durgam.models.identity import User
from durgam.models.school import School
from durgam.repositories.assignment import AssignmentRepository
from durgam.services.assignment import (
    AssignmentError,
    FacultyMentorService,
    faculty_display,
    resolve_faculty_id_by_employee_id,
)


def _ay(session: Session):
    from durgam.models.config_anchors import AcademicYear
    ay = AcademicYear(
        code=f"BA{uuid4().hex[:5]}", starts_on=date(2025, 7, 1),
        ends_on=date(2026, 4, 30), is_locked=False,
    )
    session.add(ay)
    session.flush()
    return ay


def _faculty(session: Session, emp: str):
    uid = uuid4().hex[:6]
    now = datetime.now(UTC)
    campus = Campus(code=f"FC{uid}", name="FC")
    session.add(campus)
    session.flush()
    school = School(code=f"FS{uid}", name="FS")
    session.add(school)
    session.flush()
    desig = Designation(code=f"FD{uid}", name="Prof", rank=50)
    session.add(desig)
    session.flush()
    dept = Department(code=f"FDP{uid}", name="FD", school_id=school.id, main_campus_id=campus.id)
    session.add(dept)
    session.flush()
    user = User(username=f"bf_{uid}", email=f"bf_{uid}@dev.local", password_hash="x", is_active=True)
    session.add(user)
    session.flush()
    f = FacultyMentorAssignment  # noqa: F841 (silence unused-import-style lints)
    from durgam.models.faculty import Faculty
    fac = Faculty(
        user_id=user.id, employee_id=emp, title="Dr", first_name="Asha", last_name="Rao",
        designation_id=desig.id, department_id=dept.id, campus_id=campus.id,
        joining_date=date(2020, 1, 1), phone="9", emergency_contact_name="E",
        emergency_contact_relation="P", emergency_contact_phone="9",
        created_at=now, updated_at=now,
    )
    session.add(fac)
    session.flush()
    return fac, campus


class TestFacultyMentorBackfill:
    def test_create_with_faculty_id_persists_fk(self, db_session: Session) -> None:
        ay = _ay(db_session)
        fac, campus = _faculty(db_session, f"EMP-{uuid4().hex[:6]}")
        svc = FacultyMentorService(
            repo=AssignmentRepository(FacultyMentorAssignment, db_session)
        )
        rec = svc.create(
            academic_year_id=ay.id, campus_id=campus.id, faculty_id=fac.id,
            student_id_placeholder="STU-1", actor_id=uuid4(),
        )
        fetched = AssignmentRepository(
            FacultyMentorAssignment, db_session
        ).get_by_id(rec.id)
        assert fetched is not None
        assert fetched.faculty_id == fac.id

    def test_resolve_employee_id_returns_faculty_id(self, db_session: Session) -> None:
        emp = f"EMP-{uuid4().hex[:6]}"
        fac, _ = _faculty(db_session, emp)
        assert resolve_faculty_id_by_employee_id(db_session, emp) == fac.id

    def test_resolve_unknown_employee_id_raises(self, db_session: Session) -> None:
        with pytest.raises(AssignmentError, match="No faculty found"):
            resolve_faculty_id_by_employee_id(db_session, "NOPE-404")

    def test_resolve_blank_employee_id_raises(self, db_session: Session) -> None:
        with pytest.raises(AssignmentError, match="required"):
            resolve_faculty_id_by_employee_id(db_session, "  ")

    def test_faculty_display_formats_emp_and_name(self, db_session: Session) -> None:
        emp = f"EMP-{uuid4().hex[:6]}"
        fac, _ = _faculty(db_session, emp)
        label = faculty_display(db_session, fac.id)
        assert emp in label
        assert "Asha" in label and "Rao" in label
