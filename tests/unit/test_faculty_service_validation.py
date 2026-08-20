"""Unit tests for FacultyService field-edit validation rules (M10 Phase 2).

Tests are pure-Python — no DB, no I/O. All repository calls are replaced by
lightweight stubs using unittest.mock so this file runs in milliseconds.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from durgam.models.faculty import Faculty
from durgam.services.faculty import (
    EmployeeIdConflictError,
    FacultyService,
    FacultyServiceError,
    UnauthorizedFieldEditError,
    _FACULTY_ADMIN_EDITABLE,
    _FACULTY_SELF_EDITABLE,
)


def _make_faculty(**kwargs: object) -> Faculty:
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    defaults: dict = {
        "id": uuid4(),
        "user_id": uuid4(),
        "employee_id": "EMP-001",
        "title": "Dr",
        "first_name": "Test",
        "last_name": "User",
        "designation_id": uuid4(),
        "department_id": uuid4(),
        "campus_id": uuid4(),
        "joining_date": date(2020, 1, 1),
        "is_vacation_employee": True,
        "phone": "9000000000",
        "emergency_contact_name": "Contact",
        "emergency_contact_relation": "Spouse",
        "emergency_contact_phone": "9000000001",
        "is_phd": False,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
        "created_by": None,
        "updated_by": None,
        "deleted_at": None,
        "deleted_by": None,
    }
    defaults.update(kwargs)
    obj = Faculty.model_validate(defaults)
    return obj


def _make_service(
    faculty: Faculty | None = None,
    employee_id_taken: bool = False,
) -> FacultyService:
    """Build a FacultyService with stub repositories."""
    faculty_repo = MagicMock()
    faculty_repo.get.return_value = faculty
    faculty_repo.get_by_employee_id.return_value = (
        _make_faculty() if employee_id_taken else None
    )

    svc = FacultyService(
        faculty_repo=faculty_repo,
        education_repo=MagicMock(),
        experience_repo=MagicMock(),
        expertise_repo=MagicMock(),
        document_repo=MagicMock(),
        workload_repo=MagicMock(),
    )
    return svc


class TestFieldEditableConstants:
    def test_self_editable_excludes_admin_only_fields(self) -> None:
        admin_only = {"employee_id", "designation_id", "department_id", "campus_id",
                      "joining_date", "is_vacation_employee"}
        assert not (_FACULTY_SELF_EDITABLE & admin_only), (
            "Admin-only fields must not appear in _FACULTY_SELF_EDITABLE"
        )

    def test_admin_editable_is_superset_of_self_editable(self) -> None:
        assert _FACULTY_SELF_EDITABLE.issubset(_FACULTY_ADMIN_EDITABLE), (
            "_FACULTY_ADMIN_EDITABLE must include all self-editable fields"
        )

    def test_admin_editable_includes_admin_only_fields(self) -> None:
        assert "employee_id" in _FACULTY_ADMIN_EDITABLE
        assert "designation_id" in _FACULTY_ADMIN_EDITABLE
        assert "department_id" in _FACULTY_ADMIN_EDITABLE
        assert "campus_id" in _FACULTY_ADMIN_EDITABLE
        assert "joining_date" in _FACULTY_ADMIN_EDITABLE


class TestUpdateFacultyFieldGuard:
    def test_self_edit_of_allowed_field_succeeds(self) -> None:
        faculty = _make_faculty()
        svc = _make_service(faculty=faculty)
        faculty_repo = svc._faculty
        faculty_repo.update.return_value = faculty

        result = svc.update_faculty(
            faculty.id, {"phone": "9111111111"}, uuid4(), is_admin=False
        )
        assert result is faculty
        faculty_repo.update.assert_called_once()

    def test_self_edit_of_admin_locked_field_raises(self) -> None:
        faculty = _make_faculty()
        svc = _make_service(faculty=faculty)

        with pytest.raises(UnauthorizedFieldEditError):
            svc.update_faculty(
                faculty.id,
                {"employee_id": "NEW-001"},
                uuid4(),
                is_admin=False,
            )

    def test_admin_edit_of_admin_locked_field_succeeds(self) -> None:
        faculty = _make_faculty()
        svc = _make_service(faculty=faculty)
        faculty_repo = svc._faculty
        faculty_repo.update.return_value = faculty

        result = svc.update_faculty(
            faculty.id,
            {"employee_id": "NEW-001"},
            uuid4(),
            is_admin=True,
        )
        assert result is faculty

    def test_update_nonexistent_faculty_raises(self) -> None:
        svc = _make_service(faculty=None)

        with pytest.raises(FacultyServiceError):
            svc.update_faculty(uuid4(), {"phone": "9000000000"}, uuid4())


class TestEmployeeIdConflict:
    def test_create_with_duplicate_employee_id_raises(self) -> None:
        svc = _make_service(employee_id_taken=True)

        with pytest.raises(EmployeeIdConflictError):
            svc.create_faculty(
                user_id=uuid4(),
                employee_id="DUPE-001",
                title="Dr",
                first_name="Alice",
                last_name="Smith",
                designation_id=uuid4(),
                department_id=uuid4(),
                campus_id=uuid4(),
                joining_date=date(2020, 1, 1),
                phone="9000000000",
                emergency_contact_name="Bob",
                emergency_contact_relation="Spouse",
                emergency_contact_phone="9000000001",
                actor_id=uuid4(),
            )

    def test_update_with_duplicate_employee_id_raises(self) -> None:
        own_faculty = _make_faculty(employee_id="OWN-001")
        taken_faculty = _make_faculty(employee_id="TAKEN-001")

        faculty_repo = MagicMock()
        faculty_repo.get.return_value = own_faculty
        # get_by_employee_id returns a DIFFERENT faculty (conflict)
        faculty_repo.get_by_employee_id.return_value = taken_faculty

        svc = FacultyService(
            faculty_repo=faculty_repo,
            education_repo=MagicMock(),
            experience_repo=MagicMock(),
            expertise_repo=MagicMock(),
            document_repo=MagicMock(),
            workload_repo=MagicMock(),
        )

        with pytest.raises(EmployeeIdConflictError):
            svc.update_faculty(
                own_faculty.id,
                {"employee_id": "TAKEN-001"},
                uuid4(),
                is_admin=True,
            )


class TestDocTypeValidation:
    def test_invalid_doc_type_raises(self) -> None:
        faculty = _make_faculty()
        svc = _make_service(faculty=faculty)

        with pytest.raises(FacultyServiceError, match="doc_type"):
            svc.add_document(
                faculty.id,
                file_asset_id=uuid4(),
                doc_type="invalid_type",
                actor_id=uuid4(),
            )

    def test_valid_doc_types_accepted(self) -> None:
        faculty = _make_faculty()
        svc = _make_service(faculty=faculty)
        svc._document.create.return_value = MagicMock()

        for doc_type in ("degree_certificate", "phd_certificate", "other"):
            svc.add_document(
                faculty.id,
                file_asset_id=uuid4(),
                doc_type=doc_type,
                actor_id=uuid4(),
            )
