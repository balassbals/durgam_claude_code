"""Unit tests for FacultyService.update_contact / update_external_ids /
update_phd_section (M10 Phase P1).

Pure-Python, no DB, no I/O — repos are MagicMock stubs.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.models.faculty import Faculty
from durgam.services.faculty import (
    FacultyNotFoundError,
    FacultyService,
    InvalidPhdYearError,
    NotOwnerError,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_faculty(user_id=None, **kwargs) -> Faculty:
    now = datetime.now(UTC)
    uid = user_id or uuid4()
    defaults = {
        "id": uuid4(),
        "user_id": uid,
        "employee_id": "EMP-TEST",
        "title": "Dr",
        "first_name": "Test",
        "last_name": "Faculty",
        "designation_id": uuid4(),
        "department_id": uuid4(),
        "campus_id": uuid4(),
        "joining_date": date(2020, 1, 1),
        "is_vacation_employee": False,
        "phone": "9000000000",
        "emergency_contact_name": "EC",
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
    return Faculty.model_validate(defaults)


def _make_svc(faculty: Faculty | None = None) -> FacultyService:
    repo = MagicMock()
    repo.get.return_value = faculty
    repo.update.return_value = faculty  # simplification — good enough for unit tests
    svc = FacultyService.__new__(FacultyService)
    svc._faculty = repo
    svc._education = MagicMock()
    svc._experience = MagicMock()
    svc._expertise = MagicMock()
    svc._document = MagicMock()
    svc._workload = MagicMock()
    return svc


# ── update_contact ────────────────────────────────────────────────────────────


class TestUpdateContact:
    def test_writes_only_contact_fields(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc = _make_svc(faculty)

        svc.update_contact(
            faculty.id,
            phone="9100000001",
            whatsapp="9100000002",
            alt_phone=None,
            alt_email=None,
            emergency_contact_name="Parent",
            emergency_contact_relation="Mother",
            emergency_contact_phone="9100000003",
            actor_id=actor,
        )

        svc._faculty.update.assert_called_once()
        fields_arg = svc._faculty.update.call_args.args[1]
        expected_keys = {
            "phone", "whatsapp", "alt_phone", "alt_email",
            "emergency_contact_name", "emergency_contact_relation",
            "emergency_contact_phone",
        }
        assert set(fields_arg.keys()) == expected_keys
        # No identity fields leaked
        assert "employee_id" not in fields_arg
        assert "designation_id" not in fields_arg

    def test_not_found_raises_faculty_not_found_error(self):
        svc = _make_svc(faculty=None)
        with pytest.raises(FacultyNotFoundError, match="not found"):
            svc.update_contact(
                uuid4(),
                phone="9100000001",
                whatsapp=None,
                alt_phone=None,
                alt_email=None,
                emergency_contact_name="EC",
                emergency_contact_relation="Parent",
                emergency_contact_phone="9100000002",
                actor_id=uuid4(),
            )

    def test_not_owner_raises(self):
        faculty = _make_faculty(user_id=uuid4())
        svc = _make_svc(faculty)
        with pytest.raises(NotOwnerError, match="own"):
            svc.update_contact(
                faculty.id,
                phone="9100000001",
                whatsapp=None,
                alt_phone=None,
                alt_email=None,
                emergency_contact_name="EC",
                emergency_contact_relation="Parent",
                emergency_contact_phone="9100000002",
                actor_id=uuid4(),  # different user
            )


# ── update_external_ids ───────────────────────────────────────────────────────


class TestUpdateExternalIds:
    def test_writes_only_external_id_fields(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc = _make_svc(faculty)

        svc.update_external_ids(
            faculty.id,
            orcid="https://orcid.org/0000-0001-2345-6789",
            linkedin=None,
            google_scholar=None,
            researchgate=None,
            actor_id=actor,
        )

        fields_arg = svc._faculty.update.call_args.args[1]
        assert set(fields_arg.keys()) == {"orcid", "linkedin", "google_scholar", "researchgate"}
        assert "phone" not in fields_arg
        assert "is_phd" not in fields_arg


# ── update_phd_section ────────────────────────────────────────────────────────


class TestUpdatePhdSection:
    def test_is_phd_false_clears_all_phd_fields_regardless_of_input(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor, is_phd=True)
        svc = _make_svc(faculty)

        svc.update_phd_section(
            faculty.id,
            is_phd=False,
            phd_thesis_title="Some thesis",          # should be cleared
            phd_registration_number="REG-001",       # should be cleared
            phd_awarding_institution="MIT",           # should be cleared
            phd_year=2015,                            # should be cleared
            actor_id=actor,
        )

        fields_arg = svc._faculty.update.call_args.args[1]
        assert fields_arg["is_phd"] is False
        assert fields_arg["phd_thesis_title"] is None
        assert fields_arg["phd_registration_number"] is None
        assert fields_arg["phd_awarding_institution"] is None
        assert fields_arg["phd_year"] is None

    def test_is_phd_true_valid_year_succeeds(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc = _make_svc(faculty)
        current_year = datetime.now(UTC).year

        svc.update_phd_section(
            faculty.id,
            is_phd=True,
            phd_thesis_title="My Thesis",
            phd_registration_number=None,
            phd_awarding_institution=None,
            phd_year=current_year - 2,
            actor_id=actor,
        )

        fields_arg = svc._faculty.update.call_args.args[1]
        assert fields_arg["is_phd"] is True
        assert fields_arg["phd_year"] == current_year - 2

    def test_is_phd_true_future_year_out_of_range_raises(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc = _make_svc(faculty)
        current_year = datetime.now(UTC).year

        with pytest.raises(InvalidPhdYearError, match="1900"):
            svc.update_phd_section(
                faculty.id,
                is_phd=True,
                phd_thesis_title=None,
                phd_registration_number=None,
                phd_awarding_institution=None,
                phd_year=current_year + 5,
                actor_id=actor,
            )

    def test_is_phd_true_none_year_no_error(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc = _make_svc(faculty)

        svc.update_phd_section(
            faculty.id,
            is_phd=True,
            phd_thesis_title="Partial entry",
            phd_registration_number=None,
            phd_awarding_institution=None,
            phd_year=None,
            actor_id=actor,
        )

        fields_arg = svc._faculty.update.call_args.args[1]
        assert fields_arg["phd_year"] is None
        assert fields_arg["is_phd"] is True
