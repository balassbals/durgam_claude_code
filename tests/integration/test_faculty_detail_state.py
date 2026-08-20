"""Integration tests for FacultyService.get_faculty_detail (M10 Phase 8A).

Exercises the full detail dict (identity + contact + external IDs + PhD +
Education/Experience/Expertise) against real PostgreSQL via db_session, and
asserts NO PAN/Aadhaar/document fields leak.
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
from durgam.services.faculty import FacultyNotFoundError, FacultyService


def _make_svc(session: Session) -> FacultyService:
    return FacultyService(
        faculty_repo=FacultyRepository(session),
        education_repo=FacultyEducationRepository(session),
        experience_repo=FacultyExperienceRepository(session),
        expertise_repo=FacultyExpertiseRepository(session),
        document_repo=FacultyDocumentRepository(session),
        workload_repo=FacultyWorkloadRepository(session),
    )


def _make_faculty(session: Session, *, is_phd: bool = False) -> Faculty:
    uid = uuid4().hex[:8]
    now = datetime.now(UTC)
    campus = Campus(code=f"TC{uid[:4]}", name=f"Det Campus {uid}")
    session.add(campus)
    session.flush()
    school = School(code=f"TS{uid[:4]}", name=f"Det School {uid}")
    session.add(school)
    session.flush()
    desig = Designation(code=f"TD{uid[:4]}", name="Professor", rank=22)
    session.add(desig)
    session.flush()
    dept = Department(
        code=f"TDP{uid[:3]}", name=f"Det Dept {uid}",
        school_id=school.id, main_campus_id=campus.id,
    )
    session.add(dept)
    session.flush()
    user = User(
        username=f"det_{uid}", email=f"det_{uid}@dev.local",
        password_hash="x", is_active=True, employee_type="regular_teaching",
    )
    session.add(user)
    session.flush()
    faculty = Faculty(
        user_id=user.id, employee_id=f"DETEMP-{uid}", title="Dr",
        first_name="Detail", last_name="User",
        designation_id=desig.id, department_id=dept.id, campus_id=campus.id,
        joining_date=date(2019, 6, 1), phone="9000888000",
        emergency_contact_name="EC", emergency_contact_relation="Parent",
        emergency_contact_phone="9000888001",
        orcid="https://orcid.org/0000-0001-2345-6789",
        is_phd=is_phd,
        phd_thesis_title="A Thesis" if is_phd else None,
        phd_year=2015 if is_phd else None,
        created_at=now, updated_at=now,
    )
    session.add(faculty)
    session.flush()
    return faculty


class TestGetFacultyDetailIntegration:
    def test_full_dict_shape(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        d = svc.get_faculty_detail(faculty.id, viewer_user_id=faculty.user_id)
        assert d["employee_id"] == faculty.employee_id
        assert d["name"] == "Dr Detail User"
        assert d["designation"] == "Professor"
        assert d["employee_type"] == "regular_teaching"
        assert d["orcid"] == "https://orcid.org/0000-0001-2345-6789"
        assert d["phd"] is None
        assert d["education"] == []
        assert d["experience"] == []
        assert d["expertise"] == []
        assert d["photo_file_id"] == ""

    def test_no_pii_or_document_fields(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        d = svc.get_faculty_detail(faculty.id, viewer_user_id=faculty.user_id)
        for forbidden in (
            "pan", "aadhaar", "pan_enc", "aadhaar_enc", "documents",
            "emergency_contact_phone", "emergency_contact_name",
        ):
            assert forbidden not in d

    def test_phd_populated_when_is_phd(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session, is_phd=True)
        svc = _make_svc(db_session)
        d = svc.get_faculty_detail(faculty.id, viewer_user_id=faculty.user_id)
        assert d["phd"] is not None
        assert d["phd"]["thesis_title"] == "A Thesis"
        assert d["phd"]["year"] == "2015"

    def test_sub_entities_populated(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        svc.add_education(
            faculty.id, degree_name="PhD", awarding_institution="MIT",
            year_of_award=2014, actor_id=faculty.user_id,
        )
        svc.add_experience(
            faculty.id, organization="TCS", designation_held="Lead",
            from_date=date(2010, 1, 1), to_date=date(2014, 1, 1),
            actor_id=faculty.user_id,
        )
        svc.add_expertise(faculty.id, area="ML", proficiency="Expert", actor_id=faculty.user_id)
        d = svc.get_faculty_detail(faculty.id, viewer_user_id=faculty.user_id)
        assert len(d["education"]) == 1
        assert d["education"][0]["degree_name"] == "PhD"
        assert len(d["experience"]) == 1
        assert "Present" not in d["experience"][0]["date_range"]
        assert len(d["expertise"]) == 1
        assert d["expertise"][0]["area"] == "ML"

    def test_not_found_raises(self, db_session: Session) -> None:
        svc = _make_svc(db_session)
        with pytest.raises(FacultyNotFoundError):
            svc.get_faculty_detail(uuid4(), viewer_user_id=uuid4())
