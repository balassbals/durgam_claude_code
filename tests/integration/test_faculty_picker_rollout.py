"""M10 Phase 11C — picker→service rollout contract for the 5 admin forms.

Reflex State cannot be instantiated outside the runtime, so these tests exercise
the exact data path the picker drives in each of the five forms: run the picker
search to obtain a faculty_id (what select_faculty stores in form_faculty_id),
then call the same assignment/non-owned/ug service create the save handler calls
with that faculty_id, and assert the persisted row carries the correct FK.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from durgam.models.campus import Campus
from durgam.models.config_anchors import (
    AcademicYear,
    ClassCoordinatorAssignment,
    ClassTeacherAssignment,
    Designation,
    FacultyMentorAssignment,
)
from durgam.models.department import Department
from durgam.models.faculty import Faculty
from durgam.models.identity import User
from durgam.models.school import School
from durgam.repositories.assignment import AssignmentRepository
from durgam.repositories.faculty import FacultyRepository
from durgam.repositories.non_owned_course import NonOwnedCourseRepository
from durgam.repositories.ug_timetable import UGTimetableRepository
from durgam.services.assignment import (
    ClassCoordinatorService,
    ClassTeacherService,
    FacultyMentorService,
)
from durgam.services.faculty_picker import FacultyPickerService
from durgam.services.non_owned_course import NonOwnedCourseService
from durgam.services.ug_timetable import UGTimetableService


def _ay(session) -> AcademicYear:
    ay = AcademicYear(
        code=f"T{uuid4().hex[:6]}", starts_on=date(2025, 7, 1),
        ends_on=date(2026, 4, 30), is_locked=False,
    )
    session.add(ay)
    session.flush()
    return ay


def _campus(session) -> Campus:
    c = Campus(code=f"C{uuid4().hex[:4]}", name="Campus", address="A")
    session.add(c)
    session.flush()
    return c


def _dept(session, campus) -> Department:
    s = School(code=f"S{uuid4().hex[:4]}", name="School")
    session.add(s)
    session.flush()
    d = Department(
        code=f"D{uuid4().hex[:4]}", name="Dept",
        school_id=s.id, main_campus_id=campus.id,
    )
    session.add(d)
    session.flush()
    return d


def _faculty(session, *, employee_id) -> Faculty:
    campus = _campus(session)
    dept = _dept(session, campus)
    desig = Designation(code=f"DG{uuid4().hex[:4]}", name="Prof", rank=50)
    session.add(desig)
    session.flush()
    user = User(
        username=f"r_{uuid4().hex[:8]}", email=f"r_{uuid4().hex[:8]}@dev.local",
        password_hash="x", employee_type="regular_teaching",
    )
    session.add(user)
    session.flush()
    now = datetime.now(UTC)
    f = Faculty(
        user_id=user.id, employee_id=employee_id, title="Dr",
        first_name="Pick", last_name="Me", designation_id=desig.id,
        department_id=dept.id, campus_id=campus.id, joining_date=date(2020, 1, 1),
        phone="9", emergency_contact_name="E", emergency_contact_relation="P",
        emergency_contact_phone="9", created_at=now, updated_at=now,
    )
    session.add(f)
    session.flush()
    return f


def _pick(session, employee_id) -> str:
    """Mimic the picker: search returns rows; select_faculty stores row['id']."""
    rows = FacultyPickerService(FacultyRepository(session)).search(search=employee_id)
    match = next(r for r in rows if r["employee_id"] == employee_id)
    return match["id"]  # str UUID — exactly what form_faculty_id holds


class TestPickerRollout:
    def test_faculty_mentor_create_uses_picked_id(self, db_session):
        emp = f"RM-{uuid4().hex[:8]}"
        fac = _faculty(db_session, employee_id=emp)
        ay = _ay(db_session)
        campus = _campus(db_session)
        actor = uuid4()
        picked_id = _pick(db_session, emp)

        from uuid import UUID
        svc = FacultyMentorService(
            repo=AssignmentRepository(FacultyMentorAssignment, db_session)
        )
        row = svc.create(
            academic_year_id=ay.id, campus_id=campus.id,
            faculty_id=UUID(picked_id), student_id_placeholder="STU-1",
            actor_id=actor,
        )
        assert str(row.faculty_id) == picked_id == str(fac.id)

    def test_class_teacher_create_uses_picked_id(self, db_session):
        emp = f"RT-{uuid4().hex[:8]}"
        _faculty(db_session, employee_id=emp)
        ay = _ay(db_session)
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        picked_id = _pick(db_session, emp)

        from uuid import UUID
        svc = ClassTeacherService(
            repo=AssignmentRepository(ClassTeacherAssignment, db_session)
        )
        row = svc.create(
            academic_year_id=ay.id, department_id=dept.id,
            faculty_id=UUID(picked_id), class_identifier="BSc-I-A", actor_id=uuid4(),
        )
        assert str(row.faculty_id) == picked_id

    def test_class_coordinator_create_uses_picked_id(self, db_session):
        emp = f"RC-{uuid4().hex[:8]}"
        _faculty(db_session, employee_id=emp)
        ay = _ay(db_session)
        campus = _campus(db_session)
        dept = _dept(db_session, campus)
        picked_id = _pick(db_session, emp)

        from uuid import UUID
        svc = ClassCoordinatorService(
            repo=AssignmentRepository(ClassCoordinatorAssignment, db_session)
        )
        row = svc.create(
            academic_year_id=ay.id, department_id=dept.id,
            faculty_id=UUID(picked_id), class_identifier="BSc-II-A", actor_id=uuid4(),
        )
        assert str(row.faculty_id) == picked_id

    def test_non_owned_course_create_uses_picked_id(self, db_session):
        emp = f"RN-{uuid4().hex[:8]}"
        _faculty(db_session, employee_id=emp)
        ay = _ay(db_session)
        picked_id = _pick(db_session, emp)

        from uuid import UUID
        svc = NonOwnedCourseService(repo=NonOwnedCourseRepository(db_session))
        row = svc.create(
            academic_year_id=ay.id, course_code="MDC9", course_name="Ethics",
            credits=2, semester="odd", faculty_id=UUID(picked_id), actor_id=uuid4(),
        )
        assert str(row.faculty_id) == picked_id

    def test_ug_timetable_create_uses_picked_id(self, db_session):
        emp = f"RU-{uuid4().hex[:8]}"
        _faculty(db_session, employee_id=emp)
        ay = _ay(db_session)
        picked_id = _pick(db_session, emp)

        from uuid import UUID
        svc = UGTimetableService(repo=UGTimetableRepository(db_session))
        row = svc.create(
            academic_year_id=ay.id, semester="odd", year_of_study=1,
            day_of_week=1, period_number=1, course_code="PHY1",
            course_name="Physics", faculty_id=UUID(picked_id), actor_id=uuid4(),
        )
        assert str(row.faculty_id) == picked_id
