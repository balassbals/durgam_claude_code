"""Integration tests for FacultyService against real PostgreSQL (M10 Phase 2).

These verify business-rule enforcement (not just SQL), using the seeded_session
fixture. Each test runs inside a rolled-back transaction.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlmodel import Session, select

from durgam.models.faculty import Faculty
from durgam.repositories.faculty import (
    FacultyDocumentRepository,
    FacultyEducationRepository,
    FacultyExperienceRepository,
    FacultyExpertiseRepository,
    FacultyRepository,
    FacultyWorkloadRepository,
)
from durgam.services.faculty import (
    EmployeeIdConflictError,
    FacultyService,
    FacultyServiceError,
    UnauthorizedFieldEditError,
)


def _get_seeded_id(session: Session, model, attr: str, value: str):
    from sqlmodel import select
    return session.exec(
        select(model).where(getattr(model, attr) == value)
    ).one().id


def _make_svc(session: Session) -> FacultyService:
    return FacultyService(
        faculty_repo=FacultyRepository(session),
        education_repo=FacultyEducationRepository(session),
        experience_repo=FacultyExperienceRepository(session),
        expertise_repo=FacultyExpertiseRepository(session),
        document_repo=FacultyDocumentRepository(session),
        workload_repo=FacultyWorkloadRepository(session),
    )


def _seed_ids(session: Session) -> dict:
    from durgam.models.campus import Campus
    from durgam.models.config_anchors import Designation
    from durgam.models.department import Department
    from durgam.models.identity import User

    user_id = session.exec(
        select(User.id).where(User.username == "faculty_user")
    ).one()
    dept_id = session.exec(
        select(Department.id).where(Department.code == "DMACS")
    ).one()
    campus_id = session.exec(
        select(Campus.id).where(Campus.code == "PSN")
    ).one()
    desig_id = session.exec(
        select(Designation.id).where(Designation.code == "asst_prof_l10")
    ).one()
    return {
        "user_id": user_id,
        "dept_id": dept_id,
        "campus_id": campus_id,
        "desig_id": desig_id,
    }


def _remove_existing_faculty(session: Session, user_id) -> None:
    existing = session.exec(
        select(Faculty).where(Faculty.user_id == user_id)
    ).first()
    if existing is not None:
        session.delete(existing)
        session.flush()


class TestFacultyServiceCRUD:
    def test_create_faculty_succeeds(self, seeded_session: Session) -> None:
        svc = _make_svc(seeded_session)
        ids = _seed_ids(seeded_session)
        _remove_existing_faculty(seeded_session, ids["user_id"])
        actor = uuid4()

        faculty = svc.create_faculty(
            user_id=ids["user_id"],
            employee_id=f"INT-{uuid4().hex[:8]}",
            title="Dr",
            first_name="Integration",
            last_name="Test",
            designation_id=ids["desig_id"],
            department_id=ids["dept_id"],
            campus_id=ids["campus_id"],
            joining_date=date(2021, 7, 1),
            phone="9000099999",
            emergency_contact_name="EC",
            emergency_contact_relation="Parent",
            emergency_contact_phone="9000099998",
            actor_id=actor,
        )
        assert faculty.id is not None
        assert faculty.first_name == "Integration"

    def test_duplicate_employee_id_raises(self, seeded_session: Session) -> None:
        svc = _make_svc(seeded_session)
        ids = _seed_ids(seeded_session)
        _remove_existing_faculty(seeded_session, ids["user_id"])
        actor = uuid4()
        emp_id = f"DUPINT-{uuid4().hex[:8]}"

        svc.create_faculty(
            user_id=ids["user_id"],
            employee_id=emp_id,
            title="Dr",
            first_name="First",
            last_name="Faculty",
            designation_id=ids["desig_id"],
            department_id=ids["dept_id"],
            campus_id=ids["campus_id"],
            joining_date=date(2021, 7, 1),
            phone="9000099997",
            emergency_contact_name="EC",
            emergency_contact_relation="Parent",
            emergency_contact_phone="9000099996",
            actor_id=actor,
        )
        # Attempt to create another faculty with the same employee_id (different user)
        from durgam.models.identity import User
        another_user = session.exec(
            select(User.id).where(User.username == "hod_dmacs")
        ).one() if (session := seeded_session) else uuid4()

        with pytest.raises(EmployeeIdConflictError):
            svc.create_faculty(
                user_id=another_user,
                employee_id=emp_id,  # same employee_id → conflict
                title="Prof",
                first_name="Second",
                last_name="Faculty",
                designation_id=ids["desig_id"],
                department_id=ids["dept_id"],
                campus_id=ids["campus_id"],
                joining_date=date(2022, 1, 1),
                phone="9000099995",
                emergency_contact_name="EC2",
                emergency_contact_relation="Sibling",
                emergency_contact_phone="9000099994",
                actor_id=actor,
            )

    def test_admin_can_edit_locked_field(self, seeded_session: Session) -> None:
        """Registrar-tier admin can update employee_id (admin-locked field)."""
        svc = _make_svc(seeded_session)
        ids = _seed_ids(seeded_session)
        _remove_existing_faculty(seeded_session, ids["user_id"])
        actor = uuid4()

        faculty = svc.create_faculty(
            user_id=ids["user_id"],
            employee_id=f"LOCK-{uuid4().hex[:8]}",
            title="Dr",
            first_name="Lock",
            last_name="Test",
            designation_id=ids["desig_id"],
            department_id=ids["dept_id"],
            campus_id=ids["campus_id"],
            joining_date=date(2021, 7, 1),
            phone="9000099993",
            emergency_contact_name="EC",
            emergency_contact_relation="Parent",
            emergency_contact_phone="9000099992",
            actor_id=actor,
        )
        new_emp_id = f"LOCK-NEW-{uuid4().hex[:8]}"
        updated = svc.update_faculty(
            faculty.id,
            {"employee_id": new_emp_id},
            actor,
            is_admin=True,
        )
        assert updated.employee_id == new_emp_id

    def test_non_admin_cannot_edit_locked_field(self, seeded_session: Session) -> None:
        svc = _make_svc(seeded_session)
        ids = _seed_ids(seeded_session)
        _remove_existing_faculty(seeded_session, ids["user_id"])
        actor = uuid4()

        faculty = svc.create_faculty(
            user_id=ids["user_id"],
            employee_id=f"SELFLOCK-{uuid4().hex[:8]}",
            title="Dr",
            first_name="Self",
            last_name="Test",
            designation_id=ids["desig_id"],
            department_id=ids["dept_id"],
            campus_id=ids["campus_id"],
            joining_date=date(2021, 7, 1),
            phone="9000099991",
            emergency_contact_name="EC",
            emergency_contact_relation="Parent",
            emergency_contact_phone="9000099990",
            actor_id=actor,
        )
        with pytest.raises(UnauthorizedFieldEditError):
            svc.update_faculty(
                faculty.id,
                {"designation_id": uuid4()},
                actor,
                is_admin=False,
            )

    def test_soft_delete_faculty(self, seeded_session: Session) -> None:
        svc = _make_svc(seeded_session)
        ids = _seed_ids(seeded_session)
        _remove_existing_faculty(seeded_session, ids["user_id"])
        actor = uuid4()

        faculty = svc.create_faculty(
            user_id=ids["user_id"],
            employee_id=f"DEL-{uuid4().hex[:8]}",
            title="Dr",
            first_name="Delete",
            last_name="Test",
            designation_id=ids["desig_id"],
            department_id=ids["dept_id"],
            campus_id=ids["campus_id"],
            joining_date=date(2021, 7, 1),
            phone="9000099989",
            emergency_contact_name="EC",
            emergency_contact_relation="Parent",
            emergency_contact_phone="9000099988",
            actor_id=actor,
        )
        svc.soft_delete_faculty(faculty.id, actor)
        with pytest.raises(FacultyServiceError):
            svc.get_faculty(faculty.id)
