"""Integration tests for FacultyService section-update methods used by
FacultyProfileState (M10 Phase P1).

Uses db_session (function-scoped rollback) with fully synthetic Faculty chain.
Tests verify that update_contact / update_external_ids / update_phd_section
persist to the real DB and enforce service rules.
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
    FacultyNotFoundError,
    FacultyService,
    InvalidPhdYearError,
    NotOwnerError,
    OrcidRequiredError,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_faculty(session: Session) -> Faculty:
    uid = uuid4().hex[:8]
    now = datetime.now(UTC)

    campus = Campus(code=f"FP{uid[:4]}", name=f"FP Campus {uid}")
    session.add(campus)
    session.flush()

    school = School(code=f"FS{uid[:4]}", name=f"FP School {uid}")
    session.add(school)
    session.flush()

    desig = Designation(code=f"FD{uid[:4]}", name=f"FP Desig {uid}", rank=88)
    session.add(desig)
    session.flush()

    dept = Department(
        code=f"FDP{uid[:3]}",
        name=f"FP Dept {uid}",
        school_id=school.id,
        main_campus_id=campus.id,
    )
    session.add(dept)
    session.flush()

    user = User(
        username=f"fpu_{uid}",
        email=f"fpu_{uid}@dev.local",
        password_hash="x",
        is_active=True,
    )
    session.add(user)
    session.flush()

    faculty = Faculty(
        user_id=user.id,
        employee_id=f"FPEMP-{uid}",
        title="Dr",
        first_name="Profile",
        last_name="User",
        designation_id=desig.id,
        department_id=dept.id,
        campus_id=campus.id,
        joining_date=date(2021, 6, 1),
        phone="9000111000",
        emergency_contact_name="EC",
        emergency_contact_relation="Parent",
        emergency_contact_phone="9000111001",
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


# ── update_contact ────────────────────────────────────────────────────────────


class TestUpdateContactIntegration:
    def test_contact_fields_persisted(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)

        updated = svc.update_contact(
            faculty.id,
            phone="9111222333",
            whatsapp="9111222334",
            alt_phone="9111222335",
            alt_email="alt@dev.local",
            emergency_contact_name="Updated EC",
            emergency_contact_relation="Sibling",
            emergency_contact_phone="9111222336",
            actor_id=faculty.user_id,
        )

        assert updated.phone == "9111222333"
        assert updated.whatsapp == "9111222334"
        assert updated.alt_email == "alt@dev.local"
        assert updated.emergency_contact_name == "Updated EC"
        assert updated.emergency_contact_relation == "Sibling"

    def test_contact_identity_fields_unchanged(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        orig_employee_id = faculty.employee_id

        svc.update_contact(
            faculty.id,
            phone="9111222333",
            whatsapp=None,
            alt_phone=None,
            alt_email=None,
            emergency_contact_name="EC2",
            emergency_contact_relation="Parent",
            emergency_contact_phone="9111222337",
            actor_id=faculty.user_id,
        )

        refreshed = FacultyRepository(db_session).get(faculty.id)
        assert refreshed is not None
        assert refreshed.employee_id == orig_employee_id

    def test_not_found_raises(self, db_session: Session) -> None:
        svc = _make_svc(db_session)
        with pytest.raises(FacultyNotFoundError):
            svc.update_contact(
                uuid4(),
                phone="9111222333",
                whatsapp=None,
                alt_phone=None,
                alt_email=None,
                emergency_contact_name="EC",
                emergency_contact_relation="Parent",
                emergency_contact_phone="9111222338",
                actor_id=uuid4(),
            )

    def test_not_owner_raises(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        with pytest.raises(NotOwnerError):
            svc.update_contact(
                faculty.id,
                phone="9111222339",
                whatsapp=None,
                alt_phone=None,
                alt_email=None,
                emergency_contact_name="EC",
                emergency_contact_relation="Parent",
                emergency_contact_phone="9111222340",
                actor_id=uuid4(),  # not the faculty's user_id
            )


# ── update_external_ids ───────────────────────────────────────────────────────


class TestUpdateExternalIdsIntegration:
    def test_external_ids_persisted(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)

        updated = svc.update_external_ids(
            faculty.id,
            orcid="https://orcid.org/0000-0001-2345-6789",
            linkedin="https://linkedin.com/in/testfaculty",
            google_scholar=None,
            researchgate=None,
            actor_id=faculty.user_id,
        )

        assert updated.orcid == "https://orcid.org/0000-0001-2345-6789"
        assert updated.linkedin == "https://linkedin.com/in/testfaculty"
        assert updated.google_scholar is None

    def test_orcid_required_raises_when_none(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        with pytest.raises(OrcidRequiredError):
            svc.update_external_ids(
                faculty.id,
                orcid=None,
                linkedin=None,
                google_scholar=None,
                researchgate=None,
                actor_id=faculty.user_id,
            )

    def test_orcid_required_raises_when_empty(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        with pytest.raises(OrcidRequiredError):
            svc.update_external_ids(
                faculty.id,
                orcid="",
                linkedin=None,
                google_scholar=None,
                researchgate=None,
                actor_id=faculty.user_id,
            )

    def test_external_ids_phone_unchanged(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        orig_phone = faculty.phone

        svc.update_external_ids(
            faculty.id,
            orcid="https://orcid.org/0000-0001-0000-0001",
            linkedin=None,
            google_scholar=None,
            researchgate=None,
            actor_id=faculty.user_id,
        )

        refreshed = FacultyRepository(db_session).get(faculty.id)
        assert refreshed is not None
        assert refreshed.phone == orig_phone


# ── update_phd_section ────────────────────────────────────────────────────────


class TestUpdatePhdSectionIntegration:
    def test_phd_true_persists(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)

        updated = svc.update_phd_section(
            faculty.id,
            is_phd=True,
            phd_thesis_title="Computational Cognition Studies",
            phd_registration_number="PHD-2019-001",
            phd_awarding_institution="IIT Madras",
            phd_year=2019,
            actor_id=faculty.user_id,
        )

        assert updated.is_phd is True
        assert updated.phd_thesis_title == "Computational Cognition Studies"
        assert updated.phd_year == 2019

    def test_phd_false_clears_all_fields(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)

        # First set PhD = True
        svc.update_phd_section(
            faculty.id,
            is_phd=True,
            phd_thesis_title="Some thesis",
            phd_registration_number="REG-001",
            phd_awarding_institution="IIT Bombay",
            phd_year=2018,
            actor_id=faculty.user_id,
        )

        # Then clear it
        cleared = svc.update_phd_section(
            faculty.id,
            is_phd=False,
            phd_thesis_title="Some thesis",   # should be ignored when is_phd=False
            phd_registration_number="REG-001",
            phd_awarding_institution="IIT Bombay",
            phd_year=2018,
            actor_id=faculty.user_id,
        )

        assert cleared.is_phd is False
        assert cleared.phd_thesis_title is None
        assert cleared.phd_registration_number is None
        assert cleared.phd_awarding_institution is None
        assert cleared.phd_year is None

    def test_invalid_phd_year_raises(self, db_session: Session) -> None:
        faculty = _make_faculty(db_session)
        svc = _make_svc(db_session)
        current_year = datetime.now(UTC).year

        with pytest.raises(InvalidPhdYearError):
            svc.update_phd_section(
                faculty.id,
                is_phd=True,
                phd_thesis_title=None,
                phd_registration_number=None,
                phd_awarding_institution=None,
                phd_year=current_year + 10,
                actor_id=faculty.user_id,
            )
