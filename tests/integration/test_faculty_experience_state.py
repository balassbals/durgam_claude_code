"""Integration tests for FacultyService experience methods (M10 Phase P3b).

Tests verify: add / update / remove / list_experience with real PostgreSQL.
Uses db_session (function-scoped rollback) with a synthetic Faculty chain.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
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
from durgam.services.faculty import (
    ExperienceNotFoundError,
    FacultyService,
    InvalidDateError,
    NotOwnerError,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_faculty(session: Session) -> Faculty:
    uid = uuid4().hex[:8]
    now = datetime.now(UTC)

    campus = Campus(code=f"XC{uid[:4]}", name=f"Exp Campus {uid}")
    session.add(campus)
    session.flush()

    school = School(code=f"XS{uid[:4]}", name=f"Exp School {uid}")
    session.add(school)
    session.flush()

    desig = Designation(code=f"XD{uid[:4]}", name=f"Exp Desig {uid}", rank=66)
    session.add(desig)
    session.flush()

    dept = Department(
        code=f"XDP{uid[:3]}",
        name=f"Exp Dept {uid}",
        school_id=school.id,
        main_campus_id=campus.id,
    )
    session.add(dept)
    session.flush()

    user = User(
        username=f"exp_{uid}",
        email=f"exp_{uid}@dev.local",
        password_hash="x",
        is_active=True,
    )
    session.add(user)
    session.flush()

    faculty = Faculty(
        user_id=user.id,
        employee_id=f"XEMP-{uid}",
        title="Dr",
        first_name="Exp",
        last_name="Test",
        designation_id=desig.id,
        department_id=dept.id,
        campus_id=campus.id,
        joining_date=date(2020, 7, 1),
        phone="9000333000",
        emergency_contact_name="EC",
        emergency_contact_relation="Parent",
        emergency_contact_phone="9000333001",
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


class TestAddExperienceIntegration:
    def test_add_open_ended_persists(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)

        exp = svc.add_experience(
            faculty.id,
            organization="Infosys",
            designation_held="Senior Engineer",
            from_date=date(2018, 6, 1),
            to_date=None,
            responsibilities="Backend services",
            actor_id=faculty.user_id,
        )
        assert exp.organization == "Infosys"
        assert exp.from_date == date(2018, 6, 1)
        assert exp.to_date is None
        assert exp.faculty_id == faculty.id

    def test_add_closed_range_persists(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        exp = svc.add_experience(
            faculty.id,
            organization="TCS",
            designation_held="Lead",
            from_date=date(2015, 1, 1),
            to_date=date(2018, 5, 31),
            actor_id=faculty.user_id,
        )
        assert exp.to_date == date(2018, 5, 31)

    def test_future_from_date_raises(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        future = datetime.now(UTC).date() + timedelta(days=10)
        with pytest.raises(InvalidDateError):
            svc.add_experience(
                faculty.id,
                organization="X",
                designation_held="Y",
                from_date=future,
                actor_id=faculty.user_id,
            )

    def test_from_after_to_raises(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        with pytest.raises(InvalidDateError):
            svc.add_experience(
                faculty.id,
                organization="X",
                designation_held="Y",
                from_date=date(2020, 1, 1),
                to_date=date(2019, 1, 1),
                actor_id=faculty.user_id,
            )

    def test_not_owner_raises(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        with pytest.raises(NotOwnerError):
            svc.add_experience(
                faculty.id,
                organization="X",
                designation_held="Y",
                from_date=date(2018, 1, 1),
                actor_id=uuid4(),
            )


class TestUpdateRemoveExperienceIntegration:
    def test_update_persists(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        exp = svc.add_experience(
            faculty.id,
            organization="Old Co",
            designation_held="Dev",
            from_date=date(2016, 1, 1),
            actor_id=faculty.user_id,
        )
        updated = svc.update_experience(
            exp.id,
            {"organization": "New Co", "to_date": date(2019, 12, 31)},
            faculty.user_id,
        )
        assert updated.organization == "New Co"
        assert updated.to_date == date(2019, 12, 31)

    def test_remove_soft_deletes(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        exp = svc.add_experience(
            faculty.id,
            organization="Gone Co",
            designation_held="Intern",
            from_date=date(2014, 1, 1),
            actor_id=faculty.user_id,
        )
        svc.remove_experience(exp.id, faculty.user_id)
        remaining = svc.list_experience(faculty.id)
        assert exp.id not in [e.id for e in remaining]

    def test_list_sorted_from_date_desc(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        for d in [date(2010, 1, 1), date(2018, 1, 1), date(2014, 1, 1)]:
            svc.add_experience(
                faculty.id,
                organization=f"Co-{d.year}",
                designation_held="Role",
                from_date=d,
                actor_id=faculty.user_id,
            )
        result = svc.list_experience(faculty.id)
        froms = [e.from_date for e in result]
        assert froms == sorted(froms, reverse=True)
