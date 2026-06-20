"""Integration tests for FacultyService.list_faculty_for_admin (M10 Phase P6).

Exercises the real list_with_filters SQL (joins + search ILIKE + IN filters +
pagination) and distinct_filter_options against PostgreSQL via db_session.

Consistent with the existing test_faculty_*_state.py files, which test the
service+repository layer (the state handlers use open_session()/dev-DB and the
guard, so they are verified by manual walkthrough — see CLAUDE.md route-guard
rule). The substantive new logic here is the repository query, fully covered.
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


# ── Shared fixture chain ──────────────────────────────────────────────────────


def _make_svc(session: Session) -> FacultyService:
    return FacultyService(
        faculty_repo=FacultyRepository(session),
        education_repo=FacultyEducationRepository(session),
        experience_repo=FacultyExperienceRepository(session),
        expertise_repo=FacultyExpertiseRepository(session),
        document_repo=FacultyDocumentRepository(session),
        workload_repo=FacultyWorkloadRepository(session),
    )


def _make_org(session: Session, *, dept_code: str, campus_code: str, desig_name: str):
    uid = uuid4().hex[:6]
    campus = Campus(code=campus_code, name=f"Campus {campus_code} {uid}")
    session.add(campus)
    session.flush()
    school = School(code=f"AS{uid}", name=f"Adm School {uid}")
    session.add(school)
    session.flush()
    desig = Designation(code=f"AD{uid}", name=desig_name, rank=33)
    session.add(desig)
    session.flush()
    dept = Department(
        code=dept_code,
        name=f"Dept {dept_code} {uid}",
        school_id=school.id,
        main_campus_id=campus.id,
    )
    session.add(dept)
    session.flush()
    return campus, desig, dept


def _make_faculty(
    session: Session, *, first: str, last: str, emp: str, campus, desig, dept
) -> Faculty:
    uid = uuid4().hex[:8]
    now = datetime.now(UTC)
    user = User(
        username=f"adm_{uid}",
        email=f"adm_{uid}@dev.local",
        password_hash="x",
        is_active=True,
    )
    session.add(user)
    session.flush()
    faculty = Faculty(
        user_id=user.id,
        employee_id=emp,
        title="Dr",
        first_name=first,
        last_name=last,
        designation_id=desig.id,
        department_id=dept.id,
        campus_id=campus.id,
        joining_date=date(2020, 7, 1),
        phone="9000666000",
        emergency_contact_name="EC",
        emergency_contact_relation="Parent",
        emergency_contact_phone="9000666001",
        is_phd=False,
        created_at=now,
        updated_at=now,
    )
    session.add(faculty)
    session.flush()
    return faculty


def _seed_three(session: Session):
    """Create 3 faculty across 2 depts / 2 campuses / 2 designations."""
    c1, d1, dept1 = _make_org(
        session, dept_code="ADMACS", campus_code="APSN", desig_name="Professor"
    )
    c2, d2, dept2 = _make_org(
        session, dept_code="ADPHY", campus_code="ABLR", desig_name="Lecturer"
    )
    _make_faculty(
        session, first="Asha", last="Rao", emp="EMP-A1",
        campus=c1, desig=d1, dept=dept1,
    )
    _make_faculty(
        session, first="Bharat", last="Kumar", emp="EMP-B2",
        campus=c1, desig=d1, dept=dept1,
    )
    _make_faculty(
        session, first="Chitra", last="Nair", emp="EMP-C3",
        campus=c2, desig=d2, dept=dept2,
    )
    return dept1, dept2, c1, c2


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestListFacultyForAdminIntegration:
    def test_no_filters_returns_all_seeded(self, db_session: Session) -> None:
        _seed_three(db_session)
        svc = _make_svc(db_session)
        rows, total = svc.list_faculty_for_admin(page_size=50)
        emps = {r["employee_id"] for r in rows}
        assert {"EMP-A1", "EMP-B2", "EMP-C3"} <= emps
        assert total >= 3

    def test_filter_by_department(self, db_session: Session) -> None:
        _seed_three(db_session)
        svc = _make_svc(db_session)
        rows, total = svc.list_faculty_for_admin(
            department_codes=["ADPHY"], page_size=50
        )
        assert total == 1
        assert rows[0]["employee_id"] == "EMP-C3"
        assert rows[0]["department_code"] == "ADPHY"

    def test_filter_by_campus(self, db_session: Session) -> None:
        _seed_three(db_session)
        svc = _make_svc(db_session)
        rows, total = svc.list_faculty_for_admin(campus_codes=["APSN"], page_size=50)
        assert total == 2
        assert {r["employee_id"] for r in rows} == {"EMP-A1", "EMP-B2"}

    def test_filter_by_designation(self, db_session: Session) -> None:
        _seed_three(db_session)
        svc = _make_svc(db_session)
        rows, total = svc.list_faculty_for_admin(
            designations=["Lecturer"], page_size=50
        )
        assert total == 1
        assert rows[0]["designation"] == "Lecturer"

    def test_search_by_name_case_insensitive_partial(self, db_session: Session) -> None:
        _seed_three(db_session)
        svc = _make_svc(db_session)
        rows, total = svc.list_faculty_for_admin(search="ash", page_size=50)
        assert total == 1
        assert rows[0]["employee_id"] == "EMP-A1"

    def test_search_by_employee_id(self, db_session: Session) -> None:
        _seed_three(db_session)
        svc = _make_svc(db_session)
        rows, total = svc.list_faculty_for_admin(search="EMP-B2", page_size=50)
        assert total == 1
        assert rows[0]["employee_id"] == "EMP-B2"

    def test_pagination_respects_page_size(self, db_session: Session) -> None:
        _seed_three(db_session)
        svc = _make_svc(db_session)
        page1, total = svc.list_faculty_for_admin(
            campus_codes=["APSN"], page=1, page_size=1
        )
        page2, _ = svc.list_faculty_for_admin(
            campus_codes=["APSN"], page=2, page_size=1
        )
        assert total == 2
        assert len(page1) == 1
        assert len(page2) == 1
        assert page1[0]["employee_id"] != page2[0]["employee_id"]

    def test_no_pii_columns(self, db_session: Session) -> None:
        _seed_three(db_session)
        svc = _make_svc(db_session)
        rows, _ = svc.list_faculty_for_admin(page_size=50)
        assert rows
        keys = set(rows[0].keys())
        assert keys == {
            "faculty_id",
            "employee_id",
            "name",
            "designation",
            "department_code",
            "campus",
        }

    def test_filter_options_distinct_sorted(self, db_session: Session) -> None:
        _seed_three(db_session)
        svc = _make_svc(db_session)
        depts, campuses, desigs = svc.faculty_filter_options()
        assert "ADMACS" in depts and "ADPHY" in depts
        assert "APSN" in campuses and "ABLR" in campuses
        assert "Professor" in desigs and "Lecturer" in desigs
        assert depts == sorted(depts)
        assert campuses == sorted(campuses)
        assert desigs == sorted(desigs)


class TestFacultyAdminStateVarTypes:
    """P6.1 regression: the three filter-option vars must be list[str].

    desig_options must NOT collide with the inherited BaseState.designation_options
    (typed list[dict[str, str]]); a same-name redeclaration keeps the parent's dict
    type and Reflex rejects the list[str] assignment at runtime, blanking the group.
    """

    def test_option_vars_are_list_str(self) -> None:
        from durgam.states.faculty_admin import FacultyAdminListState

        assert FacultyAdminListState.dept_options._var_type == list[str]
        assert FacultyAdminListState.campus_options._var_type == list[str]
        assert FacultyAdminListState.desig_options._var_type == list[str]

    def test_no_designation_options_collision(self) -> None:
        """The renamed var exists; the colliding name is not redeclared here."""
        from durgam.states.faculty_admin import FacultyAdminListState

        assert hasattr(FacultyAdminListState, "desig_options")
        # The inherited designation_options keeps its BaseState dict type; this
        # subclass must not have re-typed it to list[str].
        assert FacultyAdminListState.designation_options._var_type == list[dict[str, str]]
