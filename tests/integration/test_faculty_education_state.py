"""Integration tests for FacultyService education methods (M10 Phase P3a).

Tests verify: add / update / remove / list_education with real PostgreSQL.
Uses db_session (function-scoped rollback) with a synthetic Faculty chain.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlmodel import Session

from durgam.models.campus import Campus
from durgam.models.config_anchors import Designation
from durgam.models.department import Department
from durgam.models.faculty import Faculty, FacultyEducation
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
from durgam.services.faculty import (
    EducationNotFoundError,
    FacultyService,
    InvalidYearError,
    NotOwnerError,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_faculty(session: Session) -> Faculty:
    uid = uuid4().hex[:8]
    now = datetime.now(UTC)

    campus = Campus(code=f"EC{uid[:4]}", name=f"Edu Campus {uid}")
    session.add(campus)
    session.flush()

    school = School(code=f"ES{uid[:4]}", name=f"Edu School {uid}")
    session.add(school)
    session.flush()

    desig = Designation(code=f"ED{uid[:4]}", name=f"Edu Desig {uid}", rank=77)
    session.add(desig)
    session.flush()

    dept = Department(
        code=f"EDP{uid[:3]}",
        name=f"Edu Dept {uid}",
        school_id=school.id,
        main_campus_id=campus.id,
    )
    session.add(dept)
    session.flush()

    user = User(
        username=f"edu_{uid}",
        email=f"edu_{uid}@dev.local",
        password_hash="x",
        is_active=True,
    )
    session.add(user)
    session.flush()

    faculty = Faculty(
        user_id=user.id,
        employee_id=f"EDUEMP-{uid}",
        title="Dr",
        first_name="Edu",
        last_name="Test",
        designation_id=desig.id,
        department_id=dept.id,
        campus_id=campus.id,
        joining_date=date(2020, 7, 1),
        phone="9000222000",
        emergency_contact_name="EC",
        emergency_contact_relation="Parent",
        emergency_contact_phone="9000222001",
        is_phd=False,
        created_at=now,
        updated_at=now,
    )
    session.add(faculty)
    session.flush()
    return faculty


def _make_svc(session: Session) -> FacultyService:
    return FacultyService(
        faculty_repo=FacultyRepository(session),
        education_repo=FacultyEducationRepository(session),
        experience_repo=FacultyExperienceRepository(session),
        expertise_repo=FacultyExpertiseRepository(session),
        document_repo=FacultyDocumentRepository(session),
        workload_repo=FacultyWorkloadRepository(session),
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestAddEducationIntegration:
    def test_add_and_list_persists(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)

        edu = svc.add_education(
            faculty.id,
            degree_name="M.Tech",
            awarding_institution="IIT Madras",
            year_of_award=2015,
            actor_id=faculty.user_id,
            specialization="CS",
            distinction="First Class",
        )

        assert edu.degree_name == "M.Tech"
        assert edu.awarding_institution == "IIT Madras"
        assert edu.year_of_award == 2015
        assert edu.specialization == "CS"
        assert edu.faculty_id == faculty.id

    def test_year_boundary_accepted(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        current_year = datetime.now(UTC).year

        edu = svc.add_education(
            faculty.id,
            degree_name="B.Tech",
            awarding_institution="SSSIHL",
            year_of_award=current_year,
            actor_id=faculty.user_id,
        )
        assert edu.year_of_award == current_year

    def test_year_out_of_range_raises(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        with pytest.raises(InvalidYearError):
            svc.add_education(
                faculty.id,
                degree_name="B.Tech",
                awarding_institution="SSSIHL",
                year_of_award=1940,
                actor_id=faculty.user_id,
            )

    def test_not_owner_raises(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        with pytest.raises(NotOwnerError):
            svc.add_education(
                faculty.id,
                degree_name="B.Tech",
                awarding_institution="SSSIHL",
                year_of_award=2010,
                actor_id=uuid4(),
            )


class TestUpdateRemoveEducationIntegration:
    def test_update_persists_fields(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)

        edu = svc.add_education(
            faculty.id,
            degree_name="B.Tech",
            awarding_institution="Old Uni",
            year_of_award=2005,
            actor_id=faculty.user_id,
        )

        updated = svc.update_education(
            edu.id,
            {"awarding_institution": "New Uni", "year_of_award": 2006},
            faculty.user_id,
        )
        assert updated.awarding_institution == "New Uni"
        assert updated.year_of_award == 2006

    def test_remove_soft_deletes(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)

        edu = svc.add_education(
            faculty.id,
            degree_name="PhD",
            awarding_institution="MIT",
            year_of_award=2018,
            actor_id=faculty.user_id,
        )
        svc.remove_education(edu.id, faculty.user_id)

        # Should no longer appear in list
        remaining = svc.list_education(faculty.id)
        ids = [e.id for e in remaining]
        assert edu.id not in ids

    def test_remove_not_found_raises(self, db_session: Session) -> None:
        svc = _make_svc(db_session)
        with pytest.raises(EducationNotFoundError):
            svc.remove_education(uuid4(), uuid4())

    def test_list_sorted_year_desc(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)

        for year in [2005, 2018, 2010]:
            svc.add_education(
                faculty.id,
                degree_name=f"Degree-{year}",
                awarding_institution="Uni",
                year_of_award=year,
                actor_id=faculty.user_id,
            )

        result = svc.list_education(faculty.id)
        years = [e.year_of_award for e in result]
        assert years == sorted(years, reverse=True)
