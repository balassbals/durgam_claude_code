"""Integration tests for FacultyRepository and sub-model repos (M10 Phase 2).

Uses the seeded_db_engine fixture (real PostgreSQL). Each test runs inside a
rolled-back transaction so no data persists between tests.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlmodel import Session

from durgam.models.faculty import (
    Faculty,
    FacultyDocument,
    FacultyEducation,
    FacultyExperience,
    FacultyExpertise,
    FacultyWorkload,
)
from durgam.repositories.faculty import (
    FacultyDocumentRepository,
    FacultyEducationRepository,
    FacultyExperienceRepository,
    FacultyExpertiseRepository,
    FacultyRepository,
    FacultyWorkloadRepository,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_seeded_user_id(session: Session, username: str):
    from sqlmodel import select
    from durgam.models.identity import User
    return session.exec(
        select(User.id).where(User.username == username)
    ).one()

def _get_seeded_dept_id(session: Session, code: str):
    from sqlmodel import select
    from durgam.models.department import Department
    return session.exec(
        select(Department.id).where(Department.code == code)
    ).one()

def _get_seeded_campus_id(session: Session, code: str):
    from sqlmodel import select
    from durgam.models.campus import Campus
    return session.exec(
        select(Campus.id).where(Campus.code == code)
    ).one()

def _get_seeded_designation_id(session: Session, code: str):
    from sqlmodel import select
    from durgam.models.config_anchors import Designation
    return session.exec(
        select(Designation.id).where(Designation.code == code)
    ).one()

def _get_seeded_ay_id(session: Session):
    from sqlmodel import select
    from durgam.models.config_anchors import AcademicYear
    return session.exec(select(AcademicYear.id)).first()

def _get_seeded_file_asset_id(session: Session):
    from sqlmodel import select
    from durgam.models.crosscutting import FileAsset
    return session.exec(select(FileAsset.id)).first()


def _new_faculty(session: Session, *, employee_id: str = None, actor_id=None) -> Faculty:
    """Create a Faculty for a seeded regular-teaching user not yet in faculties table.

    Uses faculty_user (asst_prof_l10) as the base user since they're seeded but
    not guaranteed to be in the faculties table via the seeded_db_engine.
    """
    from sqlmodel import select

    # Pick a user that is regular_teaching; use employee_id override to avoid conflict
    user_id = _get_seeded_user_id(session, "faculty_user")
    dept_id = _get_seeded_dept_id(session, "DMACS")
    campus_id = _get_seeded_campus_id(session, "PSN")
    desig_id = _get_seeded_designation_id(session, "asst_prof_l10")
    actor = actor_id or uuid4()
    emp_id = employee_id or f"TEST-{uuid4().hex[:8]}"
    now = datetime.now(UTC)

    # Remove any existing Faculty row for faculty_user to avoid unique constraint
    existing = session.exec(
        select(Faculty).where(Faculty.user_id == user_id)
    ).first()
    if existing is not None:
        session.delete(existing)
        session.flush()

    f = Faculty(
        user_id=user_id,
        employee_id=emp_id,
        title="Dr",
        first_name="Test",
        last_name="Faculty",
        designation_id=desig_id,
        department_id=dept_id,
        campus_id=campus_id,
        joining_date=date(2020, 6, 1),
        is_vacation_employee=False,
        phone="9000000099",
        emergency_contact_name="EC Name",
        emergency_contact_relation="Spouse",
        emergency_contact_phone="9000000098",
        is_phd=False,
        created_by=actor,
        updated_by=actor,
        created_at=now,
        updated_at=now,
    )
    return f


# ── FacultyRepository tests ───────────────────────────────────────────────────

class TestFacultyRepository:
    def test_create_and_get(self, seeded_session: Session) -> None:
        repo = FacultyRepository(seeded_session)
        f = _new_faculty(seeded_session)
        created = repo.create(f)
        assert created.id is not None
        fetched = repo.get(created.id)
        assert fetched is not None
        assert fetched.employee_id == created.employee_id

    def test_get_returns_none_for_soft_deleted(self, seeded_session: Session) -> None:
        repo = FacultyRepository(seeded_session)
        actor = uuid4()
        f = _new_faculty(seeded_session, actor_id=actor)
        created = repo.create(f)
        repo.soft_delete(created.id, actor)
        assert repo.get(created.id) is None

    def test_get_by_user_id(self, seeded_session: Session) -> None:
        repo = FacultyRepository(seeded_session)
        f = _new_faculty(seeded_session)
        created = repo.create(f)
        found = repo.get_by_user_id(created.user_id)
        assert found is not None
        assert found.id == created.id

    def test_get_by_employee_id(self, seeded_session: Session) -> None:
        repo = FacultyRepository(seeded_session)
        emp_id = f"EMP-{uuid4().hex[:8]}"
        f = _new_faculty(seeded_session, employee_id=emp_id)
        repo.create(f)
        found = repo.get_by_employee_id(emp_id)
        assert found is not None
        assert found.employee_id == emp_id

    def test_list_by_department(self, seeded_session: Session) -> None:
        """Seeded faculty rows exist for DMACS — list returns at least 1."""
        repo = FacultyRepository(seeded_session)
        dept_id = _get_seeded_dept_id(seeded_session, "DMACS")
        rows = repo.list_by_department(dept_id)
        # Phase 1B seeded 7 Faculty rows all in DMACS
        assert len(rows) >= 1

    def test_list_by_campus(self, seeded_session: Session) -> None:
        repo = FacultyRepository(seeded_session)
        campus_id = _get_seeded_campus_id(seeded_session, "PSN")
        rows = repo.list_by_campus(campus_id)
        assert len(rows) >= 1

    def test_list_paginated_total(self, seeded_session: Session) -> None:
        repo = FacultyRepository(seeded_session)
        rows, total = repo.list_paginated(offset=0, limit=100)
        assert total >= 7  # Phase 1B seeded 7 faculty rows
        assert len(rows) == min(total, 100)

    def test_update(self, seeded_session: Session) -> None:
        repo = FacultyRepository(seeded_session)
        actor = uuid4()
        f = _new_faculty(seeded_session, actor_id=actor)
        created = repo.create(f)
        updated = repo.update(created.id, {"phone": "9876543210"}, actor)
        assert updated.phone == "9876543210"

    def test_soft_delete_excludes_from_list(self, seeded_session: Session) -> None:
        repo = FacultyRepository(seeded_session)
        actor = uuid4()
        f = _new_faculty(seeded_session, actor_id=actor)
        created = repo.create(f)
        _, before = repo.list_paginated()
        repo.soft_delete(created.id, actor)
        _, after = repo.list_paginated()
        assert after == before - 1


# ── FacultyEducationRepository tests ─────────────────────────────────────────

class TestFacultyEducationRepository:
    def _setup(self, seeded_session: Session):
        faculty_repo = FacultyRepository(seeded_session)
        f = _new_faculty(seeded_session)
        faculty = faculty_repo.create(f)
        repo = FacultyEducationRepository(seeded_session)
        return faculty.id, repo

    def test_create_and_list(self, seeded_session: Session) -> None:
        faculty_id, repo = self._setup(seeded_session)
        actor = uuid4()
        now = datetime.now(UTC)
        edu = FacultyEducation(
            faculty_id=faculty_id,
            degree_name="B.Tech",
            awarding_institution="Test University",
            year_of_award=2005,
            created_by=actor,
            updated_by=actor,
            created_at=now,
            updated_at=now,
        )
        created = repo.create(edu)
        assert created.id is not None
        rows = repo.list_by_faculty(faculty_id)
        assert any(r.id == created.id for r in rows)

    def test_soft_delete_excludes(self, seeded_session: Session) -> None:
        faculty_id, repo = self._setup(seeded_session)
        actor = uuid4()
        now = datetime.now(UTC)
        edu = FacultyEducation(
            faculty_id=faculty_id,
            degree_name="M.Tech",
            awarding_institution="IIT",
            year_of_award=2008,
            created_by=actor,
            updated_by=actor,
            created_at=now,
            updated_at=now,
        )
        created = repo.create(edu)
        repo.soft_delete(created.id, actor)
        rows = repo.list_by_faculty(faculty_id)
        assert all(r.id != created.id for r in rows)


# ── FacultyWorkloadRepository upsert ──────────────────────────────────────────

class TestFacultyWorkloadRepository:
    def test_upsert_creates_on_first_call(self, seeded_session: Session) -> None:
        faculty_repo = FacultyRepository(seeded_session)
        f = _new_faculty(seeded_session)
        faculty = faculty_repo.create(f)

        ay_id = _get_seeded_ay_id(seeded_session)
        if ay_id is None:
            pytest.skip("No academic year seeded")

        repo = FacultyWorkloadRepository(seeded_session)
        actor = uuid4()
        wl = repo.upsert(
            faculty_id=faculty.id,
            academic_year_id=ay_id,
            semester="ODD",
            entries=[{"course": "CS101", "hours": 4}],
            notes="Test workload",
            actor_id=actor,
        )
        assert wl.id is not None
        assert wl.semester == "ODD"
        assert len(wl.entries_json) == 1

    def test_upsert_updates_on_second_call(self, seeded_session: Session) -> None:
        faculty_repo = FacultyRepository(seeded_session)
        f = _new_faculty(seeded_session)
        faculty = faculty_repo.create(f)

        ay_id = _get_seeded_ay_id(seeded_session)
        if ay_id is None:
            pytest.skip("No academic year seeded")

        repo = FacultyWorkloadRepository(seeded_session)
        actor = uuid4()
        repo.upsert(
            faculty_id=faculty.id,
            academic_year_id=ay_id,
            semester="EVEN",
            entries=[{"course": "CS101", "hours": 4}],
            notes=None,
            actor_id=actor,
        )
        updated = repo.upsert(
            faculty_id=faculty.id,
            academic_year_id=ay_id,
            semester="EVEN",
            entries=[{"course": "CS101", "hours": 4}, {"course": "CS102", "hours": 3}],
            notes="Updated",
            actor_id=actor,
        )
        rows = repo.list_by_faculty_ay(faculty.id, ay_id)
        # Only one row should exist (upsert, not duplicate insert)
        even_rows = [r for r in rows if r.semester == "EVEN"]
        assert len(even_rows) == 1
        assert len(even_rows[0].entries_json) == 2


# ── FacultyDocumentRepository tests ──────────────────────────────────────────

class TestFacultyDocumentRepository:
    def test_list_by_faculty_and_type(self, seeded_session: Session) -> None:
        faculty_repo = FacultyRepository(seeded_session)
        f = _new_faculty(seeded_session)
        faculty = faculty_repo.create(f)

        asset_id = _get_seeded_file_asset_id(seeded_session)
        if asset_id is None:
            pytest.skip("No file asset seeded")

        repo = FacultyDocumentRepository(seeded_session)
        actor = uuid4()
        now = datetime.now(UTC)
        doc = FacultyDocument(
            faculty_id=faculty.id,
            file_asset_id=asset_id,
            doc_type="degree_certificate",
            created_by=actor,
            updated_by=actor,
            created_at=now,
            updated_at=now,
        )
        repo.create(doc)

        typed_rows = repo.list_by_faculty_and_type(faculty.id, "degree_certificate")
        assert len(typed_rows) >= 1
        other_rows = repo.list_by_faculty_and_type(faculty.id, "phd_certificate")
        assert len(other_rows) == 0
