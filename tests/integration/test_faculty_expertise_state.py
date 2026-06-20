"""Integration tests for FacultyService expertise methods (M10 Phase P3c).

Tests verify: add / update / remove / list_expertise with real PostgreSQL.
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
    ExpertiseNotFoundError,
    FacultyService,
    NotOwnerError,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_faculty(session: Session) -> Faculty:
    uid = uuid4().hex[:8]
    now = datetime.now(UTC)

    campus = Campus(code=f"PC{uid[:4]}", name=f"Xp Campus {uid}")
    session.add(campus)
    session.flush()

    school = School(code=f"PS{uid[:4]}", name=f"Xp School {uid}")
    session.add(school)
    session.flush()

    desig = Designation(code=f"PD{uid[:4]}", name=f"Xp Desig {uid}", rank=55)
    session.add(desig)
    session.flush()

    dept = Department(
        code=f"PDP{uid[:3]}",
        name=f"Xp Dept {uid}",
        school_id=school.id,
        main_campus_id=campus.id,
    )
    session.add(dept)
    session.flush()

    user = User(
        username=f"xpt_{uid}",
        email=f"xpt_{uid}@dev.local",
        password_hash="x",
        is_active=True,
    )
    session.add(user)
    session.flush()

    faculty = Faculty(
        user_id=user.id,
        employee_id=f"PEMP-{uid}",
        title="Dr",
        first_name="Xp",
        last_name="Test",
        designation_id=desig.id,
        department_id=dept.id,
        campus_id=campus.id,
        joining_date=date(2020, 7, 1),
        phone="9000444000",
        emergency_contact_name="EC",
        emergency_contact_relation="Parent",
        emergency_contact_phone="9000444001",
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


class TestAddExpertiseIntegration:
    def test_add_with_proficiency_persists(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        xp = svc.add_expertise(
            faculty.id,
            area="Machine Learning",
            proficiency="Expert",
            actor_id=faculty.user_id,
        )
        assert xp.area == "Machine Learning"
        assert xp.proficiency == "Expert"
        assert xp.faculty_id == faculty.id

    def test_add_without_proficiency_persists(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        xp = svc.add_expertise(
            faculty.id,
            area="NLP",
            proficiency=None,
            actor_id=faculty.user_id,
        )
        assert xp.area == "NLP"
        assert xp.proficiency is None

    def test_not_owner_raises(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        with pytest.raises(NotOwnerError):
            svc.add_expertise(faculty.id, area="X", actor_id=uuid4())


class TestUpdateRemoveExpertiseIntegration:
    def test_update_persists(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        xp = svc.add_expertise(
            faculty.id, area="Vision", proficiency="Intermediate", actor_id=faculty.user_id
        )
        updated = svc.update_expertise(
            xp.id, {"area": "Computer Vision", "proficiency": "Expert"}, faculty.user_id
        )
        assert updated.area == "Computer Vision"
        assert updated.proficiency == "Expert"

    def test_remove_soft_deletes(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        xp = svc.add_expertise(faculty.id, area="Gone", actor_id=faculty.user_id)
        svc.remove_expertise(xp.id, faculty.user_id)
        remaining = svc.list_expertise(faculty.id)
        assert xp.id not in [e.id for e in remaining]

    def test_remove_not_found_raises(self, db_session: Session) -> None:
        svc = _make_svc(db_session)
        with pytest.raises(ExpertiseNotFoundError):
            svc.remove_expertise(uuid4(), uuid4())

    def test_list_sorted_area_alpha(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        for area in ["Networks", "AI", "Databases"]:
            svc.add_expertise(faculty.id, area=area, actor_id=faculty.user_id)
        result = svc.list_expertise(faculty.id)
        areas = [e.area for e in result]
        assert areas == sorted(areas, key=str.lower)
