"""Integration tests: Faculty + 5 sub-model smoke tests (M10 Phase 1A).

Per-model: create with all required fields, flush, refresh, assert FK-resolution.
One rollback test on missing required field.
"""

from datetime import date
from uuid import uuid4

import pytest
from sqlmodel import select

from durgam.models.config_anchors import AcademicYear, Designation
from durgam.models.crosscutting import FileAsset
from durgam.models.department import Department
from durgam.models.campus import Campus
from durgam.models.identity import User
from durgam.models.faculty import (
    Faculty,
    FacultyDocument,
    FacultyEducation,
    FacultyExperience,
    FacultyExpertise,
    FacultyWorkload,
)


def _first(session, model):
    return session.exec(select(model).limit(1)).first()


def _make_faculty(session, suffix: str) -> Faculty:
    """Create and flush a minimal Faculty row for use as FK in sub-model tests."""
    user = _first(session, User)
    designation = _first(session, Designation)
    department = _first(session, Department)
    campus = _first(session, Campus)
    assert user and designation and department and campus, (
        "Seed data required: User, Designation, Department, Campus must exist"
    )
    f = Faculty(
        user_id=user.id,
        employee_id=f"EMP-TEST-{suffix}",
        title="Dr.",
        first_name=f"Test{suffix}",
        last_name="Faculty",
        designation_id=designation.id,
        department_id=department.id,
        campus_id=campus.id,
        joining_date=date(2020, 6, 1),
        phone="9876543210",
        emergency_contact_name="Emergency Contact",
        emergency_contact_relation="Spouse",
        emergency_contact_phone="9876543211",
    )
    session.add(f)
    session.flush()
    return f


class TestFacultyModel:
    def test_create_faculty_with_required_fields(self, seeded_session):
        f = _make_faculty(seeded_session, uuid4().hex[:6])
        seeded_session.refresh(f)

        assert f.id is not None
        assert f.first_name.startswith("Test")
        assert f.last_name == "Faculty"
        assert f.is_phd is False
        assert f.is_vacation_employee is True
        assert f.orcid is None
        assert f.photo_file_id is None

    def test_faculty_missing_phone_raises_on_flush(self, db_session):
        from scripts.seed import seed

        seed(db_session)
        db_session.commit()

        user = _first(db_session, User)
        designation = _first(db_session, Designation)
        department = _first(db_session, Department)
        campus = _first(db_session, Campus)

        faculty = Faculty(
            user_id=user.id,
            employee_id=f"EMP-FAIL-{uuid4().hex[:6]}",
            title="Dr.",
            first_name="Missing",
            last_name="Phone",
            designation_id=designation.id,
            department_id=department.id,
            campus_id=campus.id,
            joining_date=date(2020, 1, 1),
            # phone intentionally omitted — NOT NULL in DB
            emergency_contact_name="EC",
            emergency_contact_relation="Parent",
            emergency_contact_phone="9000000000",
        )
        db_session.add(faculty)
        with pytest.raises(Exception):
            db_session.flush()


class TestFacultyEducationModel:
    def test_create_education_row(self, seeded_session):
        faculty = _make_faculty(seeded_session, uuid4().hex[:6])

        edu = FacultyEducation(
            faculty_id=faculty.id,
            degree_name="M.Tech",
            awarding_institution="IIT Madras",
            year_of_award=2015,
        )
        seeded_session.add(edu)
        seeded_session.flush()
        seeded_session.refresh(edu)

        assert edu.id is not None
        assert edu.degree_name == "M.Tech"
        assert edu.specialization is None
        assert edu.faculty_id == faculty.id


class TestFacultyExperienceModel:
    def test_create_experience_row_current_position(self, seeded_session):
        faculty = _make_faculty(seeded_session, uuid4().hex[:6])

        exp = FacultyExperience(
            faculty_id=faculty.id,
            organization="SSSIHL",
            designation_held="Assistant Professor",
            from_date=date(2022, 3, 15),
        )
        seeded_session.add(exp)
        seeded_session.flush()
        seeded_session.refresh(exp)

        assert exp.id is not None
        assert exp.organization == "SSSIHL"
        assert exp.to_date is None


class TestFacultyExpertiseModel:
    def test_create_expertise_row(self, seeded_session):
        faculty = _make_faculty(seeded_session, uuid4().hex[:6])

        expertise = FacultyExpertise(
            faculty_id=faculty.id,
            area="Machine Learning",
            proficiency="expert",
        )
        seeded_session.add(expertise)
        seeded_session.flush()
        seeded_session.refresh(expertise)

        assert expertise.id is not None
        assert expertise.area == "Machine Learning"
        assert expertise.proficiency == "expert"


class TestFacultyDocumentModel:
    def test_create_document_row(self, seeded_session):
        faculty = _make_faculty(seeded_session, uuid4().hex[:6])

        asset = FileAsset(
            storage_key=f"test/faculty/{uuid4().hex}.pdf",
            original_name="degree.pdf",
            mime_type="application/pdf",
            size_bytes=12345,
            sha256="a" * 64,
            purpose="faculty_document",
        )
        seeded_session.add(asset)
        seeded_session.flush()

        doc = FacultyDocument(
            faculty_id=faculty.id,
            file_asset_id=asset.id,
            doc_type="degree_certificate",
        )
        seeded_session.add(doc)
        seeded_session.flush()
        seeded_session.refresh(doc)

        assert doc.id is not None
        assert doc.doc_type == "degree_certificate"
        assert doc.file_asset_id == asset.id


class TestFacultyWorkloadModel:
    def test_create_workload_row_with_entries(self, seeded_session):
        faculty = _make_faculty(seeded_session, uuid4().hex[:6])
        ay = _first(seeded_session, AcademicYear)
        assert ay is not None, "AcademicYear must be seeded"

        workload = FacultyWorkload(
            faculty_id=faculty.id,
            academic_year_id=ay.id,
            semester="Sem 1",
            entries_json=[
                {"label": "Calculus", "type": "lecture", "hours_per_week": 4}
            ],
        )
        seeded_session.add(workload)
        seeded_session.flush()
        seeded_session.refresh(workload)

        assert workload.id is not None
        assert workload.semester == "Sem 1"
        assert len(workload.entries_json) == 1
        assert workload.entries_json[0]["label"] == "Calculus"
