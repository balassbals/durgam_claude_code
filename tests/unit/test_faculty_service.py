"""Unit tests for FacultyService.update_contact / update_external_ids /
update_phd_section (M10 Phase P1).

Pure-Python, no DB, no I/O — repos are MagicMock stubs.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from durgam.models.faculty import Faculty
from durgam.services.faculty import (
    DocumentInvalidMimeError,
    DocumentNotFoundError,
    DocumentTooLargeError,
    EducationNotFoundError,
    ExperienceNotFoundError,
    ExpertiseNotFoundError,
    FacultyNotFoundError,
    FacultyService,
    InvalidDateError,
    InvalidPhdYearError,
    InvalidYearError,
    NotOwnerError,
    OrcidRequiredError,
    PhotoInvalidMimeError,
    PhotoTooLargeError,
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


# ── update_external_ids — ORCID required (P1.1) ──────────────────────────────


class TestUpdateExternalIdsOrcidValidation:
    def test_orcid_required_raises_when_none(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc = _make_svc(faculty)
        with pytest.raises(OrcidRequiredError):
            svc.update_external_ids(
                faculty.id,
                orcid=None,
                linkedin=None,
                google_scholar=None,
                researchgate=None,
                actor_id=actor,
            )

    def test_orcid_required_raises_when_empty(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc = _make_svc(faculty)
        with pytest.raises(OrcidRequiredError):
            svc.update_external_ids(
                faculty.id,
                orcid="",
                linkedin=None,
                google_scholar=None,
                researchgate=None,
                actor_id=actor,
            )

    def test_orcid_required_raises_when_whitespace_only(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc = _make_svc(faculty)
        with pytest.raises(OrcidRequiredError):
            svc.update_external_ids(
                faculty.id,
                orcid="   ",
                linkedin=None,
                google_scholar=None,
                researchgate=None,
                actor_id=actor,
            )

    def test_orcid_valid_succeeds(self):
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
        assert fields_arg["orcid"] == "https://orcid.org/0000-0001-2345-6789"


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


# ── update_photo (P2) ─────────────────────────────────────────────────────────

_SMALL_JPEG = b"\xff\xd8\xff" + b"x" * 100
_SMALL_PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 100
_OVER_1MB = b"x" * (1024 * 1024 + 1)


class TestUpdatePhoto:
    def test_invalid_mime_raises_photo_invalid_mime_error(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc = _make_svc(faculty)
        with pytest.raises(PhotoInvalidMimeError, match="application/pdf"):
            svc.update_photo(
                faculty.id,
                file_bytes=b"%PDF-1.4",
                original_filename="doc.pdf",
                mime_type="application/pdf",
                actor_id=actor,
            )

    def test_oversized_raises_photo_too_large_error(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc = _make_svc(faculty)
        with pytest.raises(PhotoTooLargeError, match="1MB"):
            svc.update_photo(
                faculty.id,
                file_bytes=_OVER_1MB,
                original_filename="big.jpg",
                mime_type="image/jpeg",
                actor_id=actor,
            )

    def test_not_found_raises_faculty_not_found_error(self):
        svc = _make_svc(faculty=None)
        with pytest.raises(FacultyNotFoundError):
            svc.update_photo(
                uuid4(),
                file_bytes=_SMALL_JPEG,
                original_filename="photo.jpg",
                mime_type="image/jpeg",
                actor_id=uuid4(),
            )

    def test_not_owner_raises_not_owner_error(self):
        faculty = _make_faculty(user_id=uuid4())
        svc = _make_svc(faculty)
        with pytest.raises(NotOwnerError):
            svc.update_photo(
                faculty.id,
                file_bytes=_SMALL_JPEG,
                original_filename="photo.jpg",
                mime_type="image/jpeg",
                actor_id=uuid4(),  # different user
            )

    def test_jpeg_accepted_calls_update(self):
        actor = uuid4()
        new_photo_id = uuid4()
        faculty = _make_faculty(user_id=actor)

        mock_new_asset = MagicMock()
        mock_new_asset.id = new_photo_id
        updated = _make_faculty(user_id=actor, photo_file_id=new_photo_id)

        repo = MagicMock()
        repo.get.return_value = faculty
        repo.update.return_value = updated
        repo._session = MagicMock()
        repo._session.get.return_value = None  # no prior asset

        svc = FacultyService.__new__(FacultyService)
        svc._faculty = repo
        svc._education = MagicMock()
        svc._experience = MagicMock()
        svc._expertise = MagicMock()
        svc._document = MagicMock()
        svc._workload = MagicMock()

        mock_upload_instance = MagicMock()
        mock_upload_instance.upload.return_value = mock_new_asset

        with patch("durgam.repositories.file_asset.FileAssetRepository"), \
             patch("durgam.services.upload.UploadService", return_value=mock_upload_instance), \
             patch("durgam.storage.get_storage_backend"):
            result = svc.update_photo(
                faculty.id,
                file_bytes=_SMALL_JPEG,
                original_filename="photo.jpg",
                mime_type="image/jpeg",
                actor_id=actor,
            )

        repo.update.assert_called_once()
        assert result.photo_file_id == new_photo_id  # type: ignore[union-attr]

    def test_png_accepted_calls_update(self):
        actor = uuid4()
        new_photo_id = uuid4()
        faculty = _make_faculty(user_id=actor)

        mock_new_asset = MagicMock()
        mock_new_asset.id = new_photo_id
        updated = _make_faculty(user_id=actor, photo_file_id=new_photo_id)

        repo = MagicMock()
        repo.get.return_value = faculty
        repo.update.return_value = updated
        repo._session = MagicMock()
        repo._session.get.return_value = None

        svc = FacultyService.__new__(FacultyService)
        svc._faculty = repo
        svc._education = MagicMock()
        svc._experience = MagicMock()
        svc._expertise = MagicMock()
        svc._document = MagicMock()
        svc._workload = MagicMock()

        mock_upload_instance = MagicMock()
        mock_upload_instance.upload.return_value = mock_new_asset

        with patch("durgam.repositories.file_asset.FileAssetRepository"), \
             patch("durgam.services.upload.UploadService", return_value=mock_upload_instance), \
             patch("durgam.storage.get_storage_backend"):
            result = svc.update_photo(
                faculty.id,
                file_bytes=_SMALL_PNG,
                original_filename="photo.png",
                mime_type="image/png",
                actor_id=actor,
            )

        repo.update.assert_called_once()
        assert result.photo_file_id == new_photo_id  # type: ignore[union-attr]


# ── remove_photo (P2) ─────────────────────────────────────────────────────────


class TestRemovePhoto:
    def test_no_photo_is_noop_returns_faculty(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)  # photo_file_id=None by default
        svc = _make_svc(faculty)
        result = svc.remove_photo(faculty.id, actor_id=actor)
        assert result is faculty
        svc._faculty.update.assert_not_called()

    def test_not_owner_raises_not_owner_error(self):
        faculty = _make_faculty(user_id=uuid4())
        svc = _make_svc(faculty)
        with pytest.raises(NotOwnerError):
            svc.remove_photo(faculty.id, actor_id=uuid4())


# ── photo MIME whitelist (P2) ─────────────────────────────────────────────────


class TestPhotoMimeWhitelist:
    def test_allowed_mimes_is_exactly_jpeg_and_png(self):
        from durgam.services.faculty import _PHOTO_ALLOWED_MIMES

        assert _PHOTO_ALLOWED_MIMES == frozenset({"image/jpeg", "image/png"})

    def test_pdf_not_in_photo_allowed_mimes(self):
        from durgam.services.faculty import _PHOTO_ALLOWED_MIMES

        assert "application/pdf" not in _PHOTO_ALLOWED_MIMES


# ── Education CRUD (P3a) ──────────────────────────────────────────────────────


def _make_svc_with_edu(
    faculty=None, edu=None
) -> tuple[FacultyService, object, object]:
    """Return (svc, faculty_repo_mock, edu_repo_mock)."""
    faculty_repo = MagicMock()
    faculty_repo.get.return_value = faculty
    faculty_repo.update.return_value = faculty

    edu_repo = MagicMock()
    edu_repo.get.return_value = edu
    edu_repo.update.return_value = edu
    edu_repo.soft_delete.return_value = edu
    edu_repo.list_by_faculty.return_value = []

    svc = FacultyService.__new__(FacultyService)
    svc._faculty = faculty_repo
    svc._education = edu_repo
    svc._experience = MagicMock()
    svc._expertise = MagicMock()
    svc._document = MagicMock()
    svc._workload = MagicMock()
    return svc, faculty_repo, edu_repo


class TestAddEducation:
    def test_faculty_not_found_raises(self):
        svc, _, _ = _make_svc_with_edu(faculty=None)
        with pytest.raises(FacultyNotFoundError):
            svc.add_education(
                uuid4(), degree_name="B.Tech", awarding_institution="IIT",
                year_of_award=2010, actor_id=uuid4(),
            )

    def test_not_owner_raises(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=uuid4())
        svc, _, _ = _make_svc_with_edu(faculty=faculty)
        with pytest.raises(NotOwnerError):
            svc.add_education(
                faculty.id, degree_name="B.Tech", awarding_institution="IIT",
                year_of_award=2010, actor_id=actor,  # different user
            )

    def test_year_too_early_raises(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc, _, _ = _make_svc_with_edu(faculty=faculty)
        with pytest.raises(InvalidYearError, match="1950"):
            svc.add_education(
                faculty.id, degree_name="B.Tech", awarding_institution="IIT",
                year_of_award=1900, actor_id=actor,
            )

    def test_year_too_late_raises(self):
        from datetime import UTC, datetime
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc, _, _ = _make_svc_with_edu(faculty=faculty)
        future_year = datetime.now(UTC).year + 5
        with pytest.raises(InvalidYearError):
            svc.add_education(
                faculty.id, degree_name="B.Tech", awarding_institution="IIT",
                year_of_award=future_year, actor_id=actor,
            )

    def test_valid_succeeds_calls_create(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc, _, edu_repo = _make_svc_with_edu(faculty=faculty)
        from datetime import UTC, datetime
        current_year = datetime.now(UTC).year
        svc.add_education(
            faculty.id, degree_name="B.Tech", awarding_institution="IIT",
            year_of_award=current_year - 5, actor_id=actor,
        )
        edu_repo.create.assert_called_once()
        created = edu_repo.create.call_args.args[0]
        assert created.degree_name == "B.Tech"
        assert created.year_of_award == current_year - 5


class TestUpdateEducation:
    def _make_edu(self, faculty_id):
        e = MagicMock()
        e.id = uuid4()
        e.faculty_id = faculty_id
        return e

    def test_not_found_raises(self):
        svc, _, _ = _make_svc_with_edu(faculty=_make_faculty(), edu=None)
        with pytest.raises(EducationNotFoundError):
            svc.update_education(uuid4(), {}, uuid4())

    def test_not_owner_raises(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=uuid4())
        edu = self._make_edu(faculty.id)
        svc, faculty_repo, edu_repo = _make_svc_with_edu(faculty=faculty, edu=edu)
        edu_repo.get.return_value = edu
        faculty_repo.get.return_value = faculty
        with pytest.raises(NotOwnerError):
            svc.update_education(edu.id, {}, actor)

    def test_year_invalid_in_fields_raises(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        edu = self._make_edu(faculty.id)
        svc, faculty_repo, edu_repo = _make_svc_with_edu(faculty=faculty, edu=edu)
        edu_repo.get.return_value = edu
        faculty_repo.get.return_value = faculty
        with pytest.raises(InvalidYearError):
            svc.update_education(edu.id, {"year_of_award": 1800}, actor)

    def test_valid_calls_repo_update(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        edu = self._make_edu(faculty.id)
        svc, faculty_repo, edu_repo = _make_svc_with_edu(faculty=faculty, edu=edu)
        edu_repo.get.return_value = edu
        faculty_repo.get.return_value = faculty
        svc.update_education(edu.id, {"degree_name": "M.Tech"}, actor)
        edu_repo.update.assert_called_once()


class TestRemoveEducation:
    def _make_edu(self, faculty_id):
        e = MagicMock()
        e.id = uuid4()
        e.faculty_id = faculty_id
        return e

    def test_not_found_raises(self):
        svc, _, edu_repo = _make_svc_with_edu(faculty=_make_faculty(), edu=None)
        with pytest.raises(EducationNotFoundError):
            svc.remove_education(uuid4(), uuid4())

    def test_not_owner_raises(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=uuid4())
        edu = self._make_edu(faculty.id)
        svc, faculty_repo, edu_repo = _make_svc_with_edu(faculty=faculty, edu=edu)
        edu_repo.get.return_value = edu
        faculty_repo.get.return_value = faculty
        with pytest.raises(NotOwnerError):
            svc.remove_education(edu.id, actor)

    def test_valid_calls_soft_delete(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        edu = self._make_edu(faculty.id)
        svc, faculty_repo, edu_repo = _make_svc_with_edu(faculty=faculty, edu=edu)
        edu_repo.get.return_value = edu
        faculty_repo.get.return_value = faculty
        svc.remove_education(edu.id, actor)
        edu_repo.soft_delete.assert_called_once_with(edu.id, actor)


class TestListEducationSorted:
    def test_sorted_year_desc(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc, _, edu_repo = _make_svc_with_edu(faculty=faculty)

        def _edu(year):
            e = MagicMock()
            e.year_of_award = year
            return e

        edu_repo.list_by_faculty.return_value = [_edu(2010), _edu(2020), _edu(1995)]
        result = svc.list_education(faculty.id)
        assert [e.year_of_award for e in result] == [2020, 2010, 1995]


# ── Experience CRUD (P3b) ─────────────────────────────────────────────────────


def _make_svc_with_exp(faculty=None, exp=None) -> tuple[FacultyService, object, object]:
    """Return (svc, faculty_repo_mock, experience_repo_mock)."""
    faculty_repo = MagicMock()
    faculty_repo.get.return_value = faculty

    exp_repo = MagicMock()
    exp_repo.get.return_value = exp
    exp_repo.update.return_value = exp
    exp_repo.soft_delete.return_value = exp
    exp_repo.list_by_faculty.return_value = []

    svc = FacultyService.__new__(FacultyService)
    svc._faculty = faculty_repo
    svc._education = MagicMock()
    svc._experience = exp_repo
    svc._expertise = MagicMock()
    svc._document = MagicMock()
    svc._workload = MagicMock()
    return svc, faculty_repo, exp_repo


class TestAddExperience:
    def test_faculty_not_found_raises(self):
        svc, _, _ = _make_svc_with_exp(faculty=None)
        with pytest.raises(FacultyNotFoundError):
            svc.add_experience(
                uuid4(), organization="Org", designation_held="Eng",
                from_date=date(2018, 1, 1), actor_id=uuid4(),
            )

    def test_not_owner_raises(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=uuid4())
        svc, _, _ = _make_svc_with_exp(faculty=faculty)
        with pytest.raises(NotOwnerError):
            svc.add_experience(
                faculty.id, organization="Org", designation_held="Eng",
                from_date=date(2018, 1, 1), actor_id=actor,
            )

    def test_future_from_date_raises(self):
        from datetime import UTC, datetime, timedelta
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc, _, _ = _make_svc_with_exp(faculty=faculty)
        future = datetime.now(UTC).date() + timedelta(days=30)
        with pytest.raises(InvalidDateError, match="future"):
            svc.add_experience(
                faculty.id, organization="Org", designation_held="Eng",
                from_date=future, actor_id=actor,
            )

    def test_from_after_to_raises(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc, _, _ = _make_svc_with_exp(faculty=faculty)
        with pytest.raises(InvalidDateError, match="after"):
            svc.add_experience(
                faculty.id, organization="Org", designation_held="Eng",
                from_date=date(2020, 1, 1), to_date=date(2019, 1, 1),
                actor_id=actor,
            )

    def test_valid_open_ended_succeeds(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc, _, exp_repo = _make_svc_with_exp(faculty=faculty)
        svc.add_experience(
            faculty.id, organization="Org", designation_held="Eng",
            from_date=date(2018, 1, 1), to_date=None, actor_id=actor,
        )
        exp_repo.create.assert_called_once()
        created = exp_repo.create.call_args.args[0]
        assert created.organization == "Org"
        assert created.to_date is None


class TestUpdateExperience:
    def _make_exp(self, faculty_id):
        e = MagicMock()
        e.id = uuid4()
        e.faculty_id = faculty_id
        e.from_date = date(2018, 1, 1)
        e.to_date = None
        return e

    def test_not_found_raises(self):
        svc, _, _ = _make_svc_with_exp(faculty=_make_faculty(), exp=None)
        with pytest.raises(ExperienceNotFoundError):
            svc.update_experience(uuid4(), {}, uuid4())

    def test_not_owner_raises(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=uuid4())
        exp = self._make_exp(faculty.id)
        svc, faculty_repo, exp_repo = _make_svc_with_exp(faculty=faculty, exp=exp)
        exp_repo.get.return_value = exp
        faculty_repo.get.return_value = faculty
        with pytest.raises(NotOwnerError):
            svc.update_experience(exp.id, {}, actor)

    def test_invalid_date_in_fields_raises(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        exp = self._make_exp(faculty.id)
        svc, faculty_repo, exp_repo = _make_svc_with_exp(faculty=faculty, exp=exp)
        exp_repo.get.return_value = exp
        faculty_repo.get.return_value = faculty
        with pytest.raises(InvalidDateError):
            svc.update_experience(
                exp.id, {"from_date": date(2020, 1, 1), "to_date": date(2019, 1, 1)}, actor
            )

    def test_valid_calls_repo_update(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        exp = self._make_exp(faculty.id)
        svc, faculty_repo, exp_repo = _make_svc_with_exp(faculty=faculty, exp=exp)
        exp_repo.get.return_value = exp
        faculty_repo.get.return_value = faculty
        svc.update_experience(exp.id, {"organization": "New Org"}, actor)
        exp_repo.update.assert_called_once()


class TestRemoveExperience:
    def _make_exp(self, faculty_id):
        e = MagicMock()
        e.id = uuid4()
        e.faculty_id = faculty_id
        return e

    def test_not_found_raises(self):
        svc, _, _ = _make_svc_with_exp(faculty=_make_faculty(), exp=None)
        with pytest.raises(ExperienceNotFoundError):
            svc.remove_experience(uuid4(), uuid4())

    def test_not_owner_raises(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=uuid4())
        exp = self._make_exp(faculty.id)
        svc, faculty_repo, exp_repo = _make_svc_with_exp(faculty=faculty, exp=exp)
        exp_repo.get.return_value = exp
        faculty_repo.get.return_value = faculty
        with pytest.raises(NotOwnerError):
            svc.remove_experience(exp.id, actor)

    def test_valid_calls_soft_delete(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        exp = self._make_exp(faculty.id)
        svc, faculty_repo, exp_repo = _make_svc_with_exp(faculty=faculty, exp=exp)
        exp_repo.get.return_value = exp
        faculty_repo.get.return_value = faculty
        svc.remove_experience(exp.id, actor)
        exp_repo.soft_delete.assert_called_once_with(exp.id, actor)


class TestListExperienceSorted:
    def test_sorted_from_date_desc(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc, _, exp_repo = _make_svc_with_exp(faculty=faculty)

        def _exp(d):
            e = MagicMock()
            e.from_date = d
            return e

        exp_repo.list_by_faculty.return_value = [
            _exp(date(2010, 1, 1)), _exp(date(2020, 1, 1)), _exp(date(2015, 1, 1))
        ]
        result = svc.list_experience(faculty.id)
        assert [e.from_date for e in result] == [
            date(2020, 1, 1), date(2015, 1, 1), date(2010, 1, 1)
        ]


# ── Expertise CRUD (P3c) ──────────────────────────────────────────────────────


def _make_svc_with_xp(faculty=None, xp=None) -> tuple[FacultyService, object, object]:
    """Return (svc, faculty_repo_mock, expertise_repo_mock)."""
    faculty_repo = MagicMock()
    faculty_repo.get.return_value = faculty

    xp_repo = MagicMock()
    xp_repo.get.return_value = xp
    xp_repo.update.return_value = xp
    xp_repo.soft_delete.return_value = xp
    xp_repo.list_by_faculty.return_value = []

    svc = FacultyService.__new__(FacultyService)
    svc._faculty = faculty_repo
    svc._education = MagicMock()
    svc._experience = MagicMock()
    svc._expertise = xp_repo
    svc._document = MagicMock()
    svc._workload = MagicMock()
    return svc, faculty_repo, xp_repo


class TestAddExpertise:
    def test_faculty_not_found_raises(self):
        svc, _, _ = _make_svc_with_xp(faculty=None)
        with pytest.raises(FacultyNotFoundError):
            svc.add_expertise(uuid4(), area="ML", actor_id=uuid4())

    def test_not_owner_raises(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=uuid4())
        svc, _, _ = _make_svc_with_xp(faculty=faculty)
        with pytest.raises(NotOwnerError):
            svc.add_expertise(faculty.id, area="ML", actor_id=actor)

    def test_valid_succeeds_strips_area(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc, _, xp_repo = _make_svc_with_xp(faculty=faculty)
        svc.add_expertise(faculty.id, area="  ML  ", proficiency="Expert", actor_id=actor)
        xp_repo.create.assert_called_once()
        created = xp_repo.create.call_args.args[0]
        assert created.area == "ML"
        assert created.proficiency == "Expert"


class TestUpdateExpertise:
    def _make_xp(self, faculty_id):
        e = MagicMock()
        e.id = uuid4()
        e.faculty_id = faculty_id
        return e

    def test_not_found_raises(self):
        svc, _, _ = _make_svc_with_xp(faculty=_make_faculty(), xp=None)
        with pytest.raises(ExpertiseNotFoundError):
            svc.update_expertise(uuid4(), {}, uuid4())

    def test_not_owner_raises(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=uuid4())
        xp = self._make_xp(faculty.id)
        svc, faculty_repo, xp_repo = _make_svc_with_xp(faculty=faculty, xp=xp)
        xp_repo.get.return_value = xp
        faculty_repo.get.return_value = faculty
        with pytest.raises(NotOwnerError):
            svc.update_expertise(xp.id, {}, actor)

    def test_valid_calls_repo_update(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        xp = self._make_xp(faculty.id)
        svc, faculty_repo, xp_repo = _make_svc_with_xp(faculty=faculty, xp=xp)
        xp_repo.get.return_value = xp
        faculty_repo.get.return_value = faculty
        svc.update_expertise(xp.id, {"area": "NLP"}, actor)
        xp_repo.update.assert_called_once()


class TestRemoveExpertise:
    def _make_xp(self, faculty_id):
        e = MagicMock()
        e.id = uuid4()
        e.faculty_id = faculty_id
        return e

    def test_not_found_raises(self):
        svc, _, _ = _make_svc_with_xp(faculty=_make_faculty(), xp=None)
        with pytest.raises(ExpertiseNotFoundError):
            svc.remove_expertise(uuid4(), uuid4())

    def test_not_owner_raises(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=uuid4())
        xp = self._make_xp(faculty.id)
        svc, faculty_repo, xp_repo = _make_svc_with_xp(faculty=faculty, xp=xp)
        xp_repo.get.return_value = xp
        faculty_repo.get.return_value = faculty
        with pytest.raises(NotOwnerError):
            svc.remove_expertise(xp.id, actor)

    def test_valid_calls_soft_delete(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        xp = self._make_xp(faculty.id)
        svc, faculty_repo, xp_repo = _make_svc_with_xp(faculty=faculty, xp=xp)
        xp_repo.get.return_value = xp
        faculty_repo.get.return_value = faculty
        svc.remove_expertise(xp.id, actor)
        xp_repo.soft_delete.assert_called_once_with(xp.id, actor)


class TestListExpertiseSorted:
    def test_sorted_area_alpha(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc, _, xp_repo = _make_svc_with_xp(faculty=faculty)

        def _xp(area):
            e = MagicMock()
            e.area = area
            return e

        xp_repo.list_by_faculty.return_value = [_xp("Networks"), _xp("AI"), _xp("ml")]
        result = svc.list_expertise(faculty.id)
        assert [e.area for e in result] == ["AI", "ml", "Networks"]


# ── Document upload (P4) ──────────────────────────────────────────────────────

_SMALL_PDF = b"%PDF-1.4\n" + b"x" * 100
_OVER_2MB = b"x" * (2 * 1024 * 1024 + 1)


def _make_svc_with_doc(faculty=None, doc=None) -> tuple[FacultyService, object, object]:
    """Return (svc, faculty_repo_mock, document_repo_mock)."""
    faculty_repo = MagicMock()
    faculty_repo.get.return_value = faculty

    doc_repo = MagicMock()
    doc_repo.get.return_value = doc
    doc_repo.update.return_value = doc
    doc_repo.soft_delete.return_value = doc
    doc_repo.list_by_faculty.return_value = []

    svc = FacultyService.__new__(FacultyService)
    svc._faculty = faculty_repo
    svc._education = MagicMock()
    svc._experience = MagicMock()
    svc._expertise = MagicMock()
    svc._document = doc_repo
    svc._workload = MagicMock()
    return svc, faculty_repo, doc_repo


class TestUploadDocument:
    def test_invalid_mime_raises(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc, _, _ = _make_svc_with_doc(faculty=faculty)
        with pytest.raises(DocumentInvalidMimeError, match="PDF"):
            svc.upload_document(
                faculty.id, document_type="Cert", description=None,
                file_bytes=b"\xff\xd8\xff", original_filename="x.jpg",
                mime_type="image/jpeg", actor_id=actor,
            )

    def test_oversized_raises(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc, _, _ = _make_svc_with_doc(faculty=faculty)
        with pytest.raises(DocumentTooLargeError, match="2MB"):
            svc.upload_document(
                faculty.id, document_type="Cert", description=None,
                file_bytes=_OVER_2MB, original_filename="big.pdf",
                mime_type="application/pdf", actor_id=actor,
            )

    def test_faculty_not_found_raises(self):
        svc, _, _ = _make_svc_with_doc(faculty=None)
        with pytest.raises(FacultyNotFoundError):
            svc.upload_document(
                uuid4(), document_type="Cert", description=None,
                file_bytes=_SMALL_PDF, original_filename="x.pdf",
                mime_type="application/pdf", actor_id=uuid4(),
            )

    def test_not_owner_raises(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=uuid4())
        svc, _, _ = _make_svc_with_doc(faculty=faculty)
        with pytest.raises(NotOwnerError):
            svc.upload_document(
                faculty.id, document_type="Cert", description=None,
                file_bytes=_SMALL_PDF, original_filename="x.pdf",
                mime_type="application/pdf", actor_id=actor,
            )

    def test_valid_pdf_creates_file_asset_and_document(self):
        actor = uuid4()
        new_asset_id = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc, faculty_repo, doc_repo = _make_svc_with_doc(faculty=faculty)
        faculty_repo._session = MagicMock()

        mock_asset = MagicMock()
        mock_asset.id = new_asset_id
        mock_upload = MagicMock()
        mock_upload.upload.return_value = mock_asset
        doc_repo.create.side_effect = lambda d: d

        with patch("durgam.repositories.file_asset.FileAssetRepository"), \
             patch("durgam.services.upload.UploadService", return_value=mock_upload), \
             patch("durgam.storage.get_storage_backend"):
            doc = svc.upload_document(
                faculty.id, document_type="PhD Certificate",
                description="Awarded 2018", file_bytes=_SMALL_PDF,
                original_filename="phd.pdf", mime_type="application/pdf",
                actor_id=actor,
            )

        mock_upload.upload.assert_called_once()
        assert mock_upload.upload.call_args.kwargs["purpose"] == "faculty_document"
        doc_repo.create.assert_called_once()
        assert doc.file_asset_id == new_asset_id
        assert doc.doc_type == "PhD Certificate"


class TestUpdateDocumentMetadata:
    def _make_doc(self, faculty_id):
        d = MagicMock()
        d.id = uuid4()
        d.faculty_id = faculty_id
        d.file_asset_id = uuid4()
        return d

    def test_not_found_raises(self):
        svc, _, _ = _make_svc_with_doc(faculty=_make_faculty(), doc=None)
        with pytest.raises(DocumentNotFoundError):
            svc.update_document_metadata(
                uuid4(), document_type="X", description=None, actor_id=uuid4()
            )

    def test_not_owner_raises(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=uuid4())
        doc = self._make_doc(faculty.id)
        svc, faculty_repo, doc_repo = _make_svc_with_doc(faculty=faculty, doc=doc)
        doc_repo.get.return_value = doc
        faculty_repo.get.return_value = faculty
        with pytest.raises(NotOwnerError):
            svc.update_document_metadata(
                doc.id, document_type="X", description=None, actor_id=actor
            )

    def test_valid_updates_type_and_desc_only(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        doc = self._make_doc(faculty.id)
        svc, faculty_repo, doc_repo = _make_svc_with_doc(faculty=faculty, doc=doc)
        doc_repo.get.return_value = doc
        faculty_repo.get.return_value = faculty
        svc.update_document_metadata(
            doc.id, document_type="New Type", description="New desc", actor_id=actor
        )
        doc_repo.update.assert_called_once()
        fields = doc_repo.update.call_args.args[1]
        assert set(fields.keys()) == {"doc_type", "description"}
        assert "file_asset_id" not in fields


class TestRemoveDocumentAndFile:
    def _make_doc(self, faculty_id):
        d = MagicMock()
        d.id = uuid4()
        d.faculty_id = faculty_id
        d.file_asset_id = uuid4()
        return d

    def test_not_found_raises(self):
        svc, _, _ = _make_svc_with_doc(faculty=_make_faculty(), doc=None)
        with pytest.raises(DocumentNotFoundError):
            svc.remove_document_and_file(uuid4(), uuid4())

    def test_not_owner_raises(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=uuid4())
        doc = self._make_doc(faculty.id)
        svc, faculty_repo, doc_repo = _make_svc_with_doc(faculty=faculty, doc=doc)
        doc_repo.get.return_value = doc
        faculty_repo.get.return_value = faculty
        with pytest.raises(NotOwnerError):
            svc.remove_document_and_file(doc.id, actor)

    def test_valid_soft_deletes_doc_and_asset(self):
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        doc = self._make_doc(faculty.id)
        svc, faculty_repo, doc_repo = _make_svc_with_doc(faculty=faculty, doc=doc)
        doc_repo.get.return_value = doc
        faculty_repo.get.return_value = faculty

        mock_asset = MagicMock()
        mock_asset.is_deleted = False
        session = MagicMock()
        session.get.return_value = mock_asset
        faculty_repo._session = session

        mock_file_repo = MagicMock()
        with patch(
            "durgam.repositories.file_asset.FileAssetRepository",
            return_value=mock_file_repo,
        ):
            svc.remove_document_and_file(doc.id, actor)

        mock_file_repo.soft_delete.assert_called_once_with(mock_asset, actor)
        doc_repo.soft_delete.assert_called_once_with(doc.id, actor)


class TestListDocumentsSorted:
    def test_sorted_created_at_desc(self):
        from datetime import UTC, datetime, timedelta
        actor = uuid4()
        faculty = _make_faculty(user_id=actor)
        svc, _, doc_repo = _make_svc_with_doc(faculty=faculty)
        base = datetime.now(UTC)

        def _doc(offset_days):
            d = MagicMock()
            d.created_at = base - timedelta(days=offset_days)
            return d

        doc_repo.list_by_faculty.return_value = [_doc(5), _doc(0), _doc(2)]
        result = svc.list_documents(faculty.id)
        ats = [d.created_at for d in result]
        assert ats == sorted(ats, reverse=True)


# ── Admin directory listing (P6) ──────────────────────────────────────────────


def _make_svc_admin() -> tuple[FacultyService, object]:
    """Return (svc, faculty_repo_mock) for list_faculty_for_admin tests."""
    faculty_repo = MagicMock()
    svc = FacultyService.__new__(FacultyService)
    svc._faculty = faculty_repo
    svc._education = MagicMock()
    svc._experience = MagicMock()
    svc._expertise = MagicMock()
    svc._document = MagicMock()
    svc._workload = MagicMock()
    return svc, faculty_repo


def _admin_row(emp, first, last, desig, dept, campus):
    # mirrors the repo tuple shape:
    # (faculty_id, employee_id, title, first, middle, last, desig, dept_code, campus_code)
    return (uuid4(), emp, "Dr", first, None, last, desig, dept, campus)


class TestListFacultyForAdmin:
    def test_returns_flat_dicts_no_pii(self):
        svc, repo = _make_svc_admin()
        repo.list_with_filters.return_value = (
            [_admin_row("E1", "Asha", "Rao", "Professor", "DMACS", "PSN")],
            1,
        )
        rows, total = svc.list_faculty_for_admin()
        assert total == 1
        assert rows[0]["employee_id"] == "E1"
        assert rows[0]["name"] == "Dr Asha Rao"
        assert rows[0]["designation"] == "Professor"
        assert rows[0]["department_code"] == "DMACS"
        assert rows[0]["campus"] == "PSN"
        # No PII keys leak
        for forbidden in ("pan", "aadhaar", "pan_enc", "aadhaar_enc", "phone"):
            assert forbidden not in rows[0]

    def test_passes_filters_to_repo(self):
        svc, repo = _make_svc_admin()
        repo.list_with_filters.return_value = ([], 0)
        svc.list_faculty_for_admin(
            search="rao",
            department_codes=["DMACS"],
            campus_codes=["PSN"],
            designations=["Professor"],
            page=1,
            page_size=20,
        )
        kwargs = repo.list_with_filters.call_args.kwargs
        assert kwargs["search"] == "rao"
        assert kwargs["department_codes"] == ["DMACS"]
        assert kwargs["campus_codes"] == ["PSN"]
        assert kwargs["designations"] == ["Professor"]

    def test_pagination_offset_computed(self):
        svc, repo = _make_svc_admin()
        repo.list_with_filters.return_value = ([], 0)
        svc.list_faculty_for_admin(page=3, page_size=20)
        kwargs = repo.list_with_filters.call_args.kwargs
        assert kwargs["offset"] == 40
        assert kwargs["limit"] == 20

    def test_page_one_offset_zero(self):
        svc, repo = _make_svc_admin()
        repo.list_with_filters.return_value = ([], 0)
        svc.list_faculty_for_admin(page=1, page_size=25)
        assert repo.list_with_filters.call_args.kwargs["offset"] == 0

    def test_name_skips_missing_middle(self):
        svc, repo = _make_svc_admin()
        repo.list_with_filters.return_value = (
            [(uuid4(), "E2", "Mr", "Kiran", None, "Das", "Lecturer", "DPHY", "BLR")],
            1,
        )
        rows, _ = svc.list_faculty_for_admin()
        assert rows[0]["name"] == "Mr Kiran Das"

    def test_filter_options_delegates_to_repo(self):
        svc, repo = _make_svc_admin()
        repo.distinct_filter_options.return_value = (["DMACS"], ["PSN"], ["Professor"])
        depts, campuses, desigs = svc.faculty_filter_options()
        assert depts == ["DMACS"]
        assert campuses == ["PSN"]
        assert desigs == ["Professor"]
