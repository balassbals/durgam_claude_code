"""Integration tests for FacultyService.list_faculty_for_directory (M10 Phase 8A).

Exercises list_for_directory_with_filters (joins + search + filters + pagination +
photo_file_id) against real PostgreSQL via db_session. Consistent with the existing
test_faculty_*_state.py convention (service+repo layer; guarded state handlers are
covered by manual walkthrough).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlmodel import Session

from durgam.models.campus import Campus
from durgam.models.config_anchors import Designation
from durgam.models.department import Department
from durgam.models.faculty import Faculty
from durgam.models.identity import User
from durgam.models.school import School
from durgam.repositories.faculty import (
    FacultyDocumentRepository,
    FacultyEducationRepository,
    FacultyExperienceRepository,
    FacultyExpertiseRepository,
    FacultyRepository,
    FacultyWorkloadRepository,
)
from durgam.services.faculty import FacultyService


def _make_svc(session: Session) -> FacultyService:
    return FacultyService(
        faculty_repo=FacultyRepository(session),
        education_repo=FacultyEducationRepository(session),
        experience_repo=FacultyExperienceRepository(session),
        expertise_repo=FacultyExpertiseRepository(session),
        document_repo=FacultyDocumentRepository(session),
        workload_repo=FacultyWorkloadRepository(session),
    )


def _make_org(session, *, dept_code, campus_code, desig_name):
    uid = uuid4().hex[:6]
    campus = Campus(code=campus_code, name=f"Campus {campus_code} {uid}")
    session.add(campus)
    session.flush()
    school = School(code=f"DS{uid}", name=f"Dir School {uid}")
    session.add(school)
    session.flush()
    desig = Designation(code=f"DD{uid}", name=desig_name, rank=33)
    session.add(desig)
    session.flush()
    dept = Department(
        code=dept_code, name=f"Dept {dept_code} {uid}",
        school_id=school.id, main_campus_id=campus.id,
    )
    session.add(dept)
    session.flush()
    return campus, desig, dept


def _make_faculty(session, *, first, last, emp, campus, desig, dept):
    uid = uuid4().hex[:8]
    now = datetime.now(UTC)
    user = User(
        username=f"dir_{uid}", email=f"dir_{uid}@dev.local",
        password_hash="x", is_active=True,
    )
    session.add(user)
    session.flush()
    faculty = Faculty(
        user_id=user.id, employee_id=emp, title="Dr",
        first_name=first, last_name=last,
        designation_id=desig.id, department_id=dept.id, campus_id=campus.id,
        joining_date=date(2020, 7, 1), phone="9000777000",
        emergency_contact_name="EC", emergency_contact_relation="Parent",
        emergency_contact_phone="9000777001", is_phd=False,
        created_at=now, updated_at=now,
    )
    session.add(faculty)
    session.flush()
    return faculty


def _seed_three(session):
    c1, d1, dept1 = _make_org(session, dept_code="GDMACS", campus_code="GPSN", desig_name="Professor")
    c2, d2, dept2 = _make_org(session, dept_code="GDPHY", campus_code="GBLR", desig_name="Lecturer")
    _make_faculty(session, first="Asha", last="Rao", emp="GEMP-A1", campus=c1, desig=d1, dept=dept1)
    _make_faculty(session, first="Bharat", last="Kumar", emp="GEMP-B2", campus=c1, desig=d1, dept=dept1)
    _make_faculty(session, first="Chitra", last="Nair", emp="GEMP-C3", campus=c2, desig=d2, dept=dept2)


class TestListFacultyForDirectoryIntegration:
    def test_no_filters_returns_all(self, db_session: Session) -> None:
        _seed_three(db_session)
        svc = _make_svc(db_session)
        rows, total = svc.list_faculty_for_directory(page_size=50)
        emps = {r["employee_id"] for r in rows}
        assert {"GEMP-A1", "GEMP-B2", "GEMP-C3"} <= emps
        assert total >= 3

    def test_row_shape_has_photo_file_id_no_pii(self, db_session: Session) -> None:
        _seed_three(db_session)
        svc = _make_svc(db_session)
        rows, _ = svc.list_faculty_for_directory(department_codes=["GDPHY"], page_size=50)
        assert rows
        keys = set(rows[0].keys())
        assert keys == {
            "faculty_id", "employee_id", "name", "designation",
            "department_code", "campus_code", "photo_file_id",
        }
        # No photo set in fixtures → empty string
        assert rows[0]["photo_file_id"] == ""

    def test_filter_by_campus(self, db_session: Session) -> None:
        _seed_three(db_session)
        svc = _make_svc(db_session)
        rows, total = svc.list_faculty_for_directory(campus_codes=["GPSN"], page_size=50)
        assert total == 2
        assert {r["employee_id"] for r in rows} == {"GEMP-A1", "GEMP-B2"}

    def test_search_by_name(self, db_session: Session) -> None:
        _seed_three(db_session)
        svc = _make_svc(db_session)
        rows, total = svc.list_faculty_for_directory(search="chit", page_size=50)
        assert total == 1
        assert rows[0]["employee_id"] == "GEMP-C3"

    def test_search_by_employee_id(self, db_session: Session) -> None:
        _seed_three(db_session)
        svc = _make_svc(db_session)
        rows, total = svc.list_faculty_for_directory(search="GEMP-B2", page_size=50)
        assert total == 1
        assert rows[0]["name"] == "Dr Bharat Kumar"

    def test_pagination(self, db_session: Session) -> None:
        _seed_three(db_session)
        svc = _make_svc(db_session)
        p1, total = svc.list_faculty_for_directory(campus_codes=["GPSN"], page=1, page_size=1)
        p2, _ = svc.list_faculty_for_directory(campus_codes=["GPSN"], page=2, page_size=1)
        assert total == 2
        assert len(p1) == 1 and len(p2) == 1
        assert p1[0]["employee_id"] != p2[0]["employee_id"]
