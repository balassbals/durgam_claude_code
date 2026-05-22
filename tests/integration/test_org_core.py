"""Integration tests for M3 org-core repositories against real PostgreSQL.

Covers: FK constraints, soft-delete filtering, unique-constraint enforcement,
campus-dept counting, department campus-link management, sub-department
campus-link management, vision/mission singleton pattern, config singletons.
"""

from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlmodel import select

from durgam.models.campus import Campus
from durgam.models.centre import CentreOfExcellence
from durgam.models.config_anchors import ClassTimingsConfig, WorkingDaysConfig
from durgam.models.course import Course
from durgam.models.department import Department, DepartmentCampus, SubDepartment
from durgam.models.program import (
    Program,
    ProgramExitLevel,
    ProgramOutcome,
    ProgramRegulation,
    ProgramScheme,
    ProgramSchemeCourse,
    ProgramSpecialisation,
)
from durgam.models.school import School
from durgam.models.vision_mission import (
    DepartmentMission,
    DepartmentVisionMission,
    UniversityMission,
    UniversityVisionMission,
)
from durgam.repositories.campus import CampusRepository
from durgam.repositories.centre import CentreRepository
from durgam.repositories.config_singleton import ConfigSingletonRepository
from durgam.repositories.course import CourseRepository
from durgam.repositories.department import DepartmentRepository, SubDepartmentRepository
from durgam.repositories.program import ProgramRepository
from durgam.repositories.school import SchoolRepository
from durgam.repositories.vision_mission import VisionMissionRepository


# ── Helpers ───────────────────────────────────────────────────────────────────

def _campus(session, *, idx: str | None = None) -> Campus:
    uid = idx or uuid4().hex[:6]
    c = Campus(code=f"T{uid}"[:10], name=f"Test Campus {uid}")
    session.add(c)
    session.flush()
    session.refresh(c)
    return c


def _school(session, *, idx: str | None = None) -> School:
    uid = idx or uuid4().hex[:6]
    s = School(
        code=f"S{uid}"[:10],
        name=f"Test School {uid}",
        dean_role_code=f"DEAN_S{uid}"[:64],
    )
    session.add(s)
    session.flush()
    session.refresh(s)
    return s


def _department(session, school: School, campus: Campus, *, idx: str | None = None) -> Department:
    uid = idx or uuid4().hex[:6]
    d = Department(
        code=f"D{uid}"[:10],
        name=f"Test Department {uid}",
        school_id=school.id,
        main_campus_id=campus.id,
    )
    session.add(d)
    session.flush()
    session.refresh(d)
    return d


def _program(session, department: Department, *, idx: str | None = None) -> Program:
    uid = idx or uuid4().hex[:6]
    p = Program(
        code=f"P{uid}"[:20],
        name=f"Test Program {uid}",
        department_id=department.id,
        degree_type="BSc",
        duration_years=3,
        is_active=True,
    )
    session.add(p)
    session.flush()
    session.refresh(p)
    return p


def _course(session, program: Program, department: Department, *, idx: str | None = None) -> Course:
    uid = idx or uuid4().hex[:6]
    c = Course(
        code=f"C{uid}"[:20],
        name=f"Test Course {uid}",
        program_id=program.id,
        department_id=department.id,
        credits=4,
        lecture=3,
        tutorial=1,
        practical=0,
        evaluation="E",
        is_active=True,
    )
    session.add(c)
    session.flush()
    session.refresh(c)
    return c


def _clean_university_vm(session) -> None:
    """Remove university VM rows committed by seeded_db_engine (TD-008)."""
    session.execute(sa.text("DELETE FROM university_missions"))
    session.execute(sa.text("DELETE FROM university_vision_missions"))
    session.flush()


# ── Campus ────────────────────────────────────────────────────────────────────

class TestCampusRepository:
    def test_get_by_code_returns_active_campus(self, db_session):
        camp = _campus(db_session)
        repo = CampusRepository(db_session)
        result = repo.get_by_code(camp.code)
        assert result is not None
        assert result.id == camp.id

    def test_get_by_code_returns_none_for_deleted(self, db_session):
        camp = _campus(db_session)
        repo = CampusRepository(db_session)
        repo.soft_delete(camp, actor_id=uuid4())
        assert repo.get_by_code(camp.code) is None

    def test_unique_code_enforced(self, db_session):
        _campus(db_session, idx="DUPCD")
        with pytest.raises(Exception):  # UniqueViolation wrapped by SA
            db_session.add(Campus(code="TDUPCD", name="Duplicate"))
            db_session.flush()

    def test_count_departments_includes_main_campus(self, db_session):
        camp = _campus(db_session)
        schl = _school(db_session)
        _department(db_session, schl, camp)
        repo = CampusRepository(db_session)
        assert repo.count_departments(camp.id) >= 1

    def test_count_departments_includes_join_row(self, db_session):
        camp = _campus(db_session)
        schl = _school(db_session)
        camp2 = _campus(db_session)
        dept = _department(db_session, schl, camp2)  # main campus is camp2
        # Add camp as a secondary campus via join row
        dc = DepartmentCampus(department_id=dept.id, campus_id=camp.id)
        db_session.add(dc)
        db_session.flush()
        repo = CampusRepository(db_session)
        assert repo.count_departments(camp.id) >= 1

    def test_count_departments_zero_for_unused_campus(self, db_session):
        camp = _campus(db_session)
        repo = CampusRepository(db_session)
        assert repo.count_departments(camp.id) == 0


# ── School ────────────────────────────────────────────────────────────────────

class TestSchoolRepository:
    def test_get_by_code(self, db_session):
        schl = _school(db_session)
        repo = SchoolRepository(db_session)
        assert repo.get_by_code(schl.code) is not None

    def test_soft_delete_excludes_from_list(self, db_session):
        schl = _school(db_session)
        repo = SchoolRepository(db_session)
        repo.soft_delete(schl, actor_id=uuid4())
        active = repo.list_active()
        assert all(s.id != schl.id for s in active)

    def test_count_departments(self, db_session):
        camp = _campus(db_session)
        schl = _school(db_session)
        _department(db_session, schl, camp)
        repo = SchoolRepository(db_session)
        assert repo.count_departments(schl.id) == 1


# ── Department ────────────────────────────────────────────────────────────────

class TestDepartmentRepository:
    def test_get_by_code(self, db_session):
        camp = _campus(db_session)
        schl = _school(db_session)
        dept = _department(db_session, schl, camp)
        repo = DepartmentRepository(db_session)
        assert repo.get_by_code(dept.code) is not None

    def test_list_by_school(self, db_session):
        camp = _campus(db_session)
        schl = _school(db_session)
        dept = _department(db_session, schl, camp)
        repo = DepartmentRepository(db_session)
        result = repo.list_by_school(schl.id)
        assert any(d.id == dept.id for d in result)

    def test_unique_code_enforced(self, db_session):
        camp = _campus(db_session)
        schl = _school(db_session)
        uid = uuid4().hex[:6]
        dept1 = Department(
            code=f"DU{uid}"[:10], name="Dept 1",
            school_id=schl.id, main_campus_id=camp.id
        )
        db_session.add(dept1)
        db_session.flush()
        with pytest.raises(Exception):
            dept2 = Department(
                code=dept1.code, name="Dept 2",
                school_id=schl.id, main_campus_id=camp.id,
            )
            db_session.add(dept2)
            db_session.flush()

    def test_upsert_and_remove_campus_link(self, db_session):
        camp = _campus(db_session)
        camp2 = _campus(db_session)
        schl = _school(db_session)
        dept = _department(db_session, schl, camp)
        repo = DepartmentRepository(db_session)

        repo.upsert_campus_link(dept.id, camp2.id)
        links = repo.list_campus_links(dept.id)
        assert any(lk.campus_id == camp2.id for lk in links)

        repo.upsert_campus_link(dept.id, camp2.id, has_ahod=True)
        links = repo.list_campus_links(dept.id)
        updated = next(lk for lk in links if lk.campus_id == camp2.id)
        assert updated.has_ahod is True

        repo.remove_campus_link(dept.id, camp2.id)
        links = repo.list_campus_links(dept.id)
        assert not any(lk.campus_id == camp2.id for lk in links)

    def test_count_programs(self, db_session):
        camp = _campus(db_session)
        schl = _school(db_session)
        dept = _department(db_session, schl, camp)
        _program(db_session, dept)
        repo = DepartmentRepository(db_session)
        assert repo.count_programs(dept.id) == 1

    def test_count_courses(self, db_session):
        camp = _campus(db_session)
        schl = _school(db_session)
        dept = _department(db_session, schl, camp)
        prog = _program(db_session, dept)
        _course(db_session, prog, dept)
        repo = DepartmentRepository(db_session)
        assert repo.count_courses(dept.id) == 1

    def test_fk_requires_valid_school(self, db_session):
        camp = _campus(db_session)
        with pytest.raises(Exception):
            dept = Department(
                code="DFKTEST", name="Bad FK",
                school_id=uuid4(),  # nonexistent
                main_campus_id=camp.id,
            )
            db_session.add(dept)
            db_session.flush()


# ── SubDepartment ─────────────────────────────────────────────────────────────

class TestSubDepartmentRepository:
    def test_list_by_department(self, db_session):
        camp = _campus(db_session)
        schl = _school(db_session)
        dept = _department(db_session, schl, camp)
        uid = uuid4().hex[:6]
        subdept = SubDepartment(
            code=f"SD{uid}"[:10],
            name=f"SubDept {uid}",
            parent_department_id=dept.id,
        )
        db_session.add(subdept)
        db_session.flush()
        repo = SubDepartmentRepository(db_session)
        result = repo.list_by_department(dept.id)
        assert any(s.id == subdept.id for s in result)

    def test_campus_link_upsert_and_remove(self, db_session):
        camp = _campus(db_session)
        schl = _school(db_session)
        dept = _department(db_session, schl, camp)
        uid = uuid4().hex[:6]
        subdept = SubDepartment(
            code=f"SE{uid}"[:10],
            name=f"SubDeptCampus {uid}",
            parent_department_id=dept.id,
        )
        db_session.add(subdept)
        db_session.flush()
        db_session.refresh(subdept)

        repo = SubDepartmentRepository(db_session)
        repo.upsert_campus_link(subdept.id, camp.id)
        links = repo.list_campus_links(subdept.id)
        assert any(lk.campus_id == camp.id for lk in links)

        # Idempotent upsert
        repo.upsert_campus_link(subdept.id, camp.id)
        assert len(repo.list_campus_links(subdept.id)) == 1

        repo.remove_campus_link(subdept.id, camp.id)
        assert repo.list_campus_links(subdept.id) == []


# ── Centre ────────────────────────────────────────────────────────────────────

class TestCentreRepository:
    def test_get_by_code_and_list_by_campus(self, db_session):
        camp = _campus(db_session)
        uid = uuid4().hex[:6]
        centre = CentreOfExcellence(
            code=f"CT{uid}"[:10], name=f"Centre {uid}", campus_id=camp.id
        )
        db_session.add(centre)
        db_session.flush()
        db_session.refresh(centre)

        repo = CentreRepository(db_session)
        assert repo.get_by_code(centre.code) is not None
        assert any(c.id == centre.id for c in repo.list_by_campus(camp.id))

    def test_soft_delete_excludes(self, db_session):
        camp = _campus(db_session)
        uid = uuid4().hex[:6]
        centre = CentreOfExcellence(
            code=f"CU{uid}"[:10], name=f"Centre {uid}", campus_id=camp.id
        )
        db_session.add(centre)
        db_session.flush()
        db_session.refresh(centre)

        repo = CentreRepository(db_session)
        repo.soft_delete(centre, actor_id=uuid4())
        assert repo.get_by_code(centre.code) is None
        assert not any(c.id == centre.id for c in repo.list_by_campus(camp.id))


# ── Program ───────────────────────────────────────────────────────────────────

class TestProgramRepository:
    def test_get_by_code_and_list_by_department(self, db_session):
        camp = _campus(db_session)
        schl = _school(db_session)
        dept = _department(db_session, schl, camp)
        prog = _program(db_session, dept)
        repo = ProgramRepository(db_session)
        assert repo.get_by_code(prog.code) is not None
        assert any(p.id == prog.id for p in repo.list_by_department(dept.id))

    def test_list_outcomes_by_type(self, db_session):
        camp = _campus(db_session)
        schl = _school(db_session)
        dept = _department(db_session, schl, camp)
        prog = _program(db_session, dept)
        repo = ProgramRepository(db_session)
        repo.create_outcome(prog.id, "PEO", "PEO1", "Test PEO 1", 1)
        repo.create_outcome(prog.id, "PO", "PO1", "Test PO 1", 1)
        peos = repo.list_outcomes_by_type(prog.id, "PEO")
        pos = repo.list_outcomes_by_type(prog.id, "PO")
        assert len(peos) == 1 and peos[0].code == "PEO1"
        assert len(pos) == 1 and pos[0].code == "PO1"

    def test_scheme_course_add_and_remove(self, db_session):
        camp = _campus(db_session)
        schl = _school(db_session)
        dept = _department(db_session, schl, camp)
        prog = _program(db_session, dept)
        course = _course(db_session, prog, dept)

        uid = uuid4().hex[:6]
        reg = ProgramRegulation(
            program_id=prog.id, code=f"R{uid}", effective_from_year=2021
        )
        db_session.add(reg)
        db_session.flush()
        db_session.refresh(reg)

        scheme = ProgramScheme(
            program_id=prog.id, regulation_id=reg.id, semester=1, total_credits=4
        )
        db_session.add(scheme)
        db_session.flush()
        db_session.refresh(scheme)

        repo = ProgramRepository(db_session)
        repo.add_scheme_course(scheme.id, course.id)
        ids = repo.list_scheme_course_ids(scheme.id)
        assert course.id in ids

        repo.add_scheme_course(scheme.id, course.id)  # idempotent
        assert len(repo.list_scheme_course_ids(scheme.id)) == 1

        repo.remove_scheme_course(scheme.id, course.id)
        assert repo.list_scheme_course_ids(scheme.id) == []

    def test_unique_program_outcome_constraint(self, db_session):
        camp = _campus(db_session)
        schl = _school(db_session)
        dept = _department(db_session, schl, camp)
        prog = _program(db_session, dept)
        repo = ProgramRepository(db_session)
        repo.create_outcome(prog.id, "PEO", "PEO1", "First", 1)
        with pytest.raises(Exception):  # unique (program_id, outcome_type, code)
            repo.create_outcome(prog.id, "PEO", "PEO1", "Duplicate", 2)


# ── Course ────────────────────────────────────────────────────────────────────

class TestCourseRepository:
    def test_get_by_code_and_list_by_department(self, db_session):
        camp = _campus(db_session)
        schl = _school(db_session)
        dept = _department(db_session, schl, camp)
        prog = _program(db_session, dept)
        course = _course(db_session, prog, dept)
        repo = CourseRepository(db_session)
        assert repo.get_by_code(course.code) is not None
        assert any(c.id == course.id for c in repo.list_by_department(dept.id))

    def test_count_scheme_usages(self, db_session):
        camp = _campus(db_session)
        schl = _school(db_session)
        dept = _department(db_session, schl, camp)
        prog = _program(db_session, dept)
        course = _course(db_session, prog, dept)

        uid = uuid4().hex[:6]
        reg = ProgramRegulation(
            program_id=prog.id, code=f"R{uid}", effective_from_year=2021
        )
        db_session.add(reg)
        db_session.flush()
        db_session.refresh(reg)

        scheme = ProgramScheme(
            program_id=prog.id, regulation_id=reg.id, semester=1, total_credits=4
        )
        db_session.add(scheme)
        db_session.flush()
        db_session.refresh(scheme)

        link = ProgramSchemeCourse(scheme_id=scheme.id, course_id=course.id)
        db_session.add(link)
        db_session.flush()

        repo = CourseRepository(db_session)
        assert repo.count_scheme_usages(course.id) == 1

    def test_soft_delete_excludes_from_list(self, db_session):
        camp = _campus(db_session)
        schl = _school(db_session)
        dept = _department(db_session, schl, camp)
        prog = _program(db_session, dept)
        course = _course(db_session, prog, dept)
        repo = CourseRepository(db_session)
        repo.soft_delete(course, actor_id=uuid4())
        assert not any(c.id == course.id for c in repo.list_by_department(dept.id))


# ── Department invariant ──────────────────────────────────────────────────────

class TestDepartmentMainCampusInvariant:
    """Invariant: departments.main_campus_id always appears in department_campuses."""

    def test_seeded_departments_all_have_main_in_links(self, seeded_session):
        """After seeding, every active department's main_campus_id is in its campus links."""
        depts = seeded_session.exec(
            select(Department).where(Department.is_deleted == False)  # noqa: E712
        ).all()
        assert depts, "No seeded departments found — seed may not have run"
        for dept in depts:
            links = seeded_session.exec(
                select(DepartmentCampus).where(
                    DepartmentCampus.department_id == dept.id
                )
            ).all()
            link_campus_ids = {link.campus_id for link in links}
            assert dept.main_campus_id in link_campus_ids, (
                f"Department '{dept.code}': main_campus_id={dept.main_campus_id} "
                f"not in campus links {link_campus_ids}"
            )


# ── Vision/Mission ────────────────────────────────────────────────────────────

class TestVisionMissionRepository:
    def test_university_singleton_create_and_retrieve(self, db_session):
        _clean_university_vm(db_session)
        repo = VisionMissionRepository(db_session)
        assert repo.get_university_vm() is None
        uvm = repo.create_university_vm("Test vision text")
        assert uvm.id is not None
        assert repo.get_university_vm() is not None

    def test_university_mission_ordered_by_display_order(self, db_session):
        repo = VisionMissionRepository(db_session)
        uvm = repo.create_university_vm("Vision")
        repo.create_university_mission(uvm.id, "Mission B", display_order=2)
        repo.create_university_mission(uvm.id, "Mission A", display_order=1)
        missions = repo.list_university_missions(uvm.id)
        assert len(missions) == 2
        assert missions[0].display_order == 1
        assert missions[1].display_order == 2

    def test_university_vm_save_updates_vision(self, db_session):
        _clean_university_vm(db_session)
        repo = VisionMissionRepository(db_session)
        uvm = repo.create_university_vm("Original")
        uvm.vision = "Updated"
        repo.save_university_vm(uvm)
        retrieved = repo.get_university_vm()
        assert retrieved is not None
        assert retrieved.vision == "Updated"

    def test_department_vm_unique_per_department(self, db_session):
        camp = _campus(db_session)
        schl = _school(db_session)
        dept = _department(db_session, schl, camp)
        repo = VisionMissionRepository(db_session)
        repo.create_department_vm(dept.id, "Dept vision")
        with pytest.raises(Exception):  # unique constraint on department_id
            repo.create_department_vm(dept.id, "Duplicate vision")

    def test_department_mission_ordered(self, db_session):
        camp = _campus(db_session)
        schl = _school(db_session)
        dept = _department(db_session, schl, camp)
        repo = VisionMissionRepository(db_session)
        dvm = repo.create_department_vm(dept.id, "Dept vision")
        repo.create_department_mission(dvm.id, "Mission 2", display_order=2)
        repo.create_department_mission(dvm.id, "Mission 1", display_order=1)
        missions = repo.list_department_missions(dvm.id)
        assert missions[0].display_order == 1

    def test_repo_exposes_no_delete_methods(self, db_session):
        """VisionMissionRepository must not provide any delete pathway (E-001)."""
        repo = VisionMissionRepository(db_session)
        for name in dir(repo):
            assert "delete" not in name.lower(), (
                f"VisionMissionRepository unexpectedly has a delete method: {name!r}"
            )


# ── Config singletons ─────────────────────────────────────────────────────────

class TestConfigSingletonRepository:
    def test_class_timings_get_or_create(self, db_session):
        repo = ConfigSingletonRepository(db_session)
        ctc = repo.get_or_create_class_timings()
        assert ctc.periods_per_day == 8
        assert ctc.period_duration_minutes == 50
        # Second call returns same row
        ctc2 = repo.get_or_create_class_timings()
        assert ctc2.id == ctc.id

    def test_class_timings_save(self, db_session):
        repo = ConfigSingletonRepository(db_session)
        ctc = repo.get_or_create_class_timings()
        ctc.periods_per_day = 9
        repo.save_class_timings(ctc)
        refreshed = repo.get_or_create_class_timings()
        assert refreshed.periods_per_day == 9

    def test_working_days_get_or_create(self, db_session):
        repo = ConfigSingletonRepository(db_session)
        wdc = repo.get_or_create_working_days()
        assert wdc.days_per_week == 5
        wdc2 = repo.get_or_create_working_days()
        assert wdc2.id == wdc.id

    def test_working_days_save(self, db_session):
        repo = ConfigSingletonRepository(db_session)
        wdc = repo.get_or_create_working_days()
        wdc.days_per_week = 6
        repo.save_working_days(wdc)
        refreshed = repo.get_or_create_working_days()
        assert refreshed.days_per_week == 6


# ── FK and cascade behaviour ──────────────────────────────────────────────────

class TestForeignKeyConstraints:
    def test_centre_requires_valid_campus(self, db_session):
        with pytest.raises(Exception):
            centre = CentreOfExcellence(
                code="CXBAD", name="Bad FK", campus_id=uuid4()
            )
            db_session.add(centre)
            db_session.flush()

    def test_program_requires_valid_department(self, db_session):
        with pytest.raises(Exception):
            prog = Program(
                code="PBAD", name="Bad FK", department_id=uuid4(),
                degree_type="BSc", duration_years=3, is_active=True,
            )
            db_session.add(prog)
            db_session.flush()

    def test_course_requires_valid_program_and_department(self, db_session):
        with pytest.raises(Exception):
            course = Course(
                code="CBAD", name="Bad FK",
                program_id=uuid4(), department_id=uuid4(),
                credits=4, lecture=3, tutorial=1, practical=0,
                evaluation="E", is_active=True,
            )
            db_session.add(course)
            db_session.flush()

    def test_soft_delete_does_not_cascade_to_children(self, db_session):
        """Soft-deleting a department does NOT cascade-delete its programs."""
        camp = _campus(db_session)
        schl = _school(db_session)
        dept = _department(db_session, schl, camp)
        prog = _program(db_session, dept)

        dept_repo = DepartmentRepository(db_session)
        dept_repo.soft_delete(dept, actor_id=uuid4())

        # Program still exists — soft-delete is parent-only
        prog_repo = ProgramRepository(db_session)
        retrieved = prog_repo.get_by_id(prog.id)
        assert retrieved is not None
        assert not retrieved.is_deleted
