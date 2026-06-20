"""FacultyService — business rules for the Faculty Module (M10 Phase 2).

Layering: service owns validation rules; repositories own all SQL.
No session.commit() here — callers (page states) must commit.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

import structlog

from durgam.models.faculty import (
    Faculty,
    FacultyDocument,
    FacultyEducation,
    FacultyExperience,
    FacultyExpertise,
    FacultyWorkload,
)
from durgam.repositories.faculty import (
    FacultyDocumentRepository,
    FacultyEducationRepository,
    FacultyExperienceRepository,
    FacultyExpertiseRepository,
    FacultyRepository,
    FacultyWorkloadRepository,
)

log = structlog.get_logger(__name__)

# Fields a faculty member may edit on their own profile (Q6).
_FACULTY_SELF_EDITABLE: frozenset[str] = frozenset({
    "title",
    "first_name",
    "middle_name",
    "last_name",
    "phone",
    "whatsapp",
    "alt_phone",
    "alt_email",
    "photo_file_id",
    "emergency_contact_name",
    "emergency_contact_relation",
    "emergency_contact_phone",
    "is_phd",
    "phd_thesis_title",
    "phd_registration_number",
    "phd_awarding_institution",
    "phd_year",
    "orcid",
    "linkedin",
    "google_scholar",
    "researchgate",
})

# Fields only admin-tier users (Registrar / HR_HEAD) may set or change (Q6).
_FACULTY_ADMIN_EDITABLE: frozenset[str] = _FACULTY_SELF_EDITABLE | frozenset({
    "employee_id",
    "designation_id",
    "department_id",
    "campus_id",
    "joining_date",
    "is_vacation_employee",
})

_VALID_DOC_TYPES: frozenset[str] = frozenset({
    "degree_certificate",
    "phd_certificate",
    "other",
})


class FacultyServiceError(Exception):
    pass


class FacultyNotRegularTeachingError(FacultyServiceError):
    """Raised when a Faculty record is requested for a non-regular-teaching user."""


class UnauthorizedFieldEditError(FacultyServiceError):
    """Raised when a caller attempts to modify an admin-locked field without admin permission."""


class EmployeeIdConflictError(FacultyServiceError):
    """Raised when the requested employee_id is already taken by another faculty."""


class FacultyNotFoundError(FacultyServiceError):
    """Raised when no Faculty row exists for the given faculty_id."""


class NotOwnerError(FacultyServiceError):
    """Raised when actor_id is not the faculty's user_id (self-edit guard)."""


class InvalidPhdYearError(FacultyServiceError):
    """Raised when phd_year is outside [1900, current_year + 1]."""


class OrcidRequiredError(FacultyServiceError):
    """Raised when update_external_ids is called without a non-empty ORCID iD."""


class PhotoInvalidMimeError(FacultyServiceError):
    """Raised when uploaded photo MIME is not image/jpeg or image/png."""


class PhotoTooLargeError(FacultyServiceError):
    """Raised when uploaded photo exceeds 1MB."""


class EducationNotFoundError(FacultyServiceError):
    """Raised when an education record is not found or already deleted."""


class InvalidYearError(FacultyServiceError):
    """Raised when year_of_award is outside [1950, current_year + 1]."""


class ExperienceNotFoundError(FacultyServiceError):
    """Raised when an experience record is not found or already deleted."""


class InvalidDateError(FacultyServiceError):
    """Raised when experience dates are invalid (future from_date, or from > to)."""


class ExpertiseNotFoundError(FacultyServiceError):
    """Raised when an expertise record is not found or already deleted."""


class DocumentNotFoundError(FacultyServiceError):
    """Raised when a faculty document is not found or already deleted."""


class DocumentInvalidMimeError(FacultyServiceError):
    """Raised when an uploaded document MIME is not application/pdf."""


class DocumentTooLargeError(FacultyServiceError):
    """Raised when an uploaded document exceeds 2MB."""


_PHOTO_ALLOWED_MIMES: frozenset[str] = frozenset({"image/jpeg", "image/png"})
_PHOTO_MAX_BYTES: int = 1024 * 1024  # 1MB

# Document upload whitelist — additive, isolated to purpose="faculty_document".
_DOCUMENT_ALLOWED_MIMES: frozenset[str] = frozenset({"application/pdf"})
_DOCUMENT_MAX_BYTES: int = 2 * 1024 * 1024  # 2MB


class FacultyService:
    def __init__(
        self,
        faculty_repo: FacultyRepository,
        education_repo: FacultyEducationRepository,
        experience_repo: FacultyExperienceRepository,
        expertise_repo: FacultyExpertiseRepository,
        document_repo: FacultyDocumentRepository,
        workload_repo: FacultyWorkloadRepository,
    ) -> None:
        self._faculty = faculty_repo
        self._education = education_repo
        self._experience = experience_repo
        self._expertise = expertise_repo
        self._document = document_repo
        self._workload = workload_repo

    # ── Faculty CRUD ──────────────────────────────────────────────────────────

    def get_faculty(self, faculty_id: UUID) -> Faculty:
        faculty = self._faculty.get(faculty_id)
        if faculty is None:
            raise FacultyServiceError(f"Faculty {faculty_id} not found.")
        return faculty

    def get_by_user_id(self, user_id: UUID) -> Faculty | None:
        return self._faculty.get_by_user_id(user_id)

    def get_my_faculty(self, user_id: UUID) -> Faculty:
        """Return the Faculty record for the calling user; raises if absent."""
        faculty = self._faculty.get_by_user_id(user_id)
        if faculty is None:
            raise FacultyServiceError("No faculty profile found for this user.")
        return faculty

    def create_faculty(
        self,
        *,
        user_id: UUID,
        employee_id: str,
        title: str,
        first_name: str,
        last_name: str,
        designation_id: UUID,
        department_id: UUID,
        campus_id: UUID,
        joining_date: object,
        phone: str,
        emergency_contact_name: str,
        emergency_contact_relation: str,
        emergency_contact_phone: str,
        actor_id: UUID,
        **optional_fields: object,
    ) -> Faculty:
        self._assert_employee_id_unique(employee_id, exclude_id=None)
        now = datetime.now(UTC)
        faculty = Faculty(
            user_id=user_id,
            employee_id=employee_id.strip(),
            title=title.strip(),
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            designation_id=designation_id,
            department_id=department_id,
            campus_id=campus_id,
            joining_date=joining_date,  # type: ignore[arg-type]
            phone=phone.strip(),
            emergency_contact_name=emergency_contact_name.strip(),
            emergency_contact_relation=emergency_contact_relation.strip(),
            emergency_contact_phone=emergency_contact_phone.strip(),
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        for k, v in optional_fields.items():
            if k in _FACULTY_ADMIN_EDITABLE:
                setattr(faculty, k, v)
        faculty = self._faculty.create(faculty)
        log.info("faculty_created", faculty_id=str(faculty.id), actor=str(actor_id))
        return faculty

    def update_faculty(
        self,
        faculty_id: UUID,
        fields: dict,
        actor_id: UUID,
        *,
        is_admin: bool = False,
    ) -> Faculty:
        self._assert_faculty_exists(faculty_id)
        allowed = _FACULTY_ADMIN_EDITABLE if is_admin else _FACULTY_SELF_EDITABLE
        bad_keys = set(fields) - allowed
        if bad_keys:
            raise UnauthorizedFieldEditError(
                f"Field(s) {bad_keys!r} cannot be edited with current permissions."
            )
        if "employee_id" in fields:
            self._assert_employee_id_unique(fields["employee_id"], exclude_id=faculty_id)
        faculty = self._faculty.update(faculty_id, fields, actor_id)
        log.info("faculty_updated", faculty_id=str(faculty_id), actor=str(actor_id))
        return faculty

    def soft_delete_faculty(self, faculty_id: UUID, actor_id: UUID) -> Faculty:
        self._assert_faculty_exists(faculty_id)
        faculty = self._faculty.soft_delete(faculty_id, actor_id)
        log.info("faculty_deleted", faculty_id=str(faculty_id), actor=str(actor_id))
        return faculty

    def list_faculty(
        self, offset: int = 0, limit: int = 50
    ) -> tuple[list[Faculty], int]:
        return self._faculty.list_paginated(offset=offset, limit=limit)

    def list_by_department(self, department_id: UUID) -> list[Faculty]:
        return self._faculty.list_by_department(department_id)

    def list_by_campus(self, campus_id: UUID) -> list[Faculty]:
        return self._faculty.list_by_campus(campus_id)

    # ── Education ─────────────────────────────────────────────────────────────

    def add_education(
        self,
        faculty_id: UUID,
        *,
        degree_name: str,
        awarding_institution: str,
        year_of_award: int,
        actor_id: UUID,
        specialization: str | None = None,
        distinction: str | None = None,
    ) -> FacultyEducation:
        faculty = self._faculty.get(faculty_id)
        if faculty is None:
            raise FacultyNotFoundError(f"Faculty {faculty_id} not found.")
        if faculty.user_id != actor_id:
            raise NotOwnerError("You can only edit your own education records.")
        current_year = datetime.now(UTC).year
        if not (1950 <= year_of_award <= current_year + 1):
            raise InvalidYearError(
                f"Year of award must be between 1950 and {current_year + 1}."
            )
        now = datetime.now(UTC)
        edu = FacultyEducation(
            faculty_id=faculty_id,
            degree_name=degree_name.strip(),
            specialization=specialization,
            awarding_institution=awarding_institution.strip(),
            year_of_award=year_of_award,
            distinction=distinction,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        return self._education.create(edu)

    def update_education(
        self, edu_id: UUID, fields: dict, actor_id: UUID
    ) -> FacultyEducation:
        edu = self._education.get(edu_id)
        if edu is None:
            raise EducationNotFoundError(f"Education record {edu_id} not found.")
        faculty = self._faculty.get(edu.faculty_id)
        if faculty is None or faculty.user_id != actor_id:
            raise NotOwnerError("You can only edit your own education records.")
        if "year_of_award" in fields:
            year = fields["year_of_award"]
            current_year = datetime.now(UTC).year
            if not (1950 <= year <= current_year + 1):
                raise InvalidYearError(
                    f"Year of award must be between 1950 and {current_year + 1}."
                )
        return self._education.update(edu_id, fields, actor_id)

    def remove_education(self, edu_id: UUID, actor_id: UUID) -> FacultyEducation:
        edu = self._education.get(edu_id)
        if edu is None:
            raise EducationNotFoundError(f"Education record {edu_id} not found.")
        faculty = self._faculty.get(edu.faculty_id)
        if faculty is None or faculty.user_id != actor_id:
            raise NotOwnerError("You can only delete your own education records.")
        return self._education.soft_delete(edu_id, actor_id)

    def list_education(self, faculty_id: UUID) -> list[FacultyEducation]:
        records = self._education.list_by_faculty(faculty_id)
        return sorted(records, key=lambda e: e.year_of_award, reverse=True)

    # ── Experience ────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_experience_dates(
        from_date: date, to_date: date | None
    ) -> None:
        today = datetime.now(UTC).date()
        if from_date > today:
            raise InvalidDateError("From date cannot be in the future.")
        if to_date is not None and from_date > to_date:
            raise InvalidDateError("From date cannot be after To date.")

    def add_experience(
        self,
        faculty_id: UUID,
        *,
        organization: str,
        designation_held: str,
        from_date: date,
        actor_id: UUID,
        to_date: date | None = None,
        responsibilities: str | None = None,
    ) -> FacultyExperience:
        faculty = self._faculty.get(faculty_id)
        if faculty is None:
            raise FacultyNotFoundError(f"Faculty {faculty_id} not found.")
        if faculty.user_id != actor_id:
            raise NotOwnerError("You can only edit your own experience records.")
        self._validate_experience_dates(from_date, to_date)
        now = datetime.now(UTC)
        exp = FacultyExperience(
            faculty_id=faculty_id,
            organization=organization.strip(),
            designation_held=designation_held.strip(),
            from_date=from_date,
            to_date=to_date,
            responsibilities=responsibilities,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        return self._experience.create(exp)

    def update_experience(
        self, exp_id: UUID, fields: dict, actor_id: UUID
    ) -> FacultyExperience:
        exp = self._experience.get(exp_id)
        if exp is None:
            raise ExperienceNotFoundError(f"Experience record {exp_id} not found.")
        faculty = self._faculty.get(exp.faculty_id)
        if faculty is None or faculty.user_id != actor_id:
            raise NotOwnerError("You can only edit your own experience records.")
        new_from = fields.get("from_date", exp.from_date)
        new_to = fields.get("to_date", exp.to_date)
        self._validate_experience_dates(new_from, new_to)
        return self._experience.update(exp_id, fields, actor_id)

    def remove_experience(self, exp_id: UUID, actor_id: UUID) -> FacultyExperience:
        exp = self._experience.get(exp_id)
        if exp is None:
            raise ExperienceNotFoundError(f"Experience record {exp_id} not found.")
        faculty = self._faculty.get(exp.faculty_id)
        if faculty is None or faculty.user_id != actor_id:
            raise NotOwnerError("You can only delete your own experience records.")
        return self._experience.soft_delete(exp_id, actor_id)

    def list_experience(self, faculty_id: UUID) -> list[FacultyExperience]:
        records = self._experience.list_by_faculty(faculty_id)
        return sorted(records, key=lambda e: e.from_date, reverse=True)

    # ── Expertise ─────────────────────────────────────────────────────────────

    def add_expertise(
        self,
        faculty_id: UUID,
        *,
        area: str,
        actor_id: UUID,
        proficiency: str | None = None,
    ) -> FacultyExpertise:
        faculty = self._faculty.get(faculty_id)
        if faculty is None:
            raise FacultyNotFoundError(f"Faculty {faculty_id} not found.")
        if faculty.user_id != actor_id:
            raise NotOwnerError("You can only edit your own expertise records.")
        now = datetime.now(UTC)
        exp = FacultyExpertise(
            faculty_id=faculty_id,
            area=area.strip(),
            proficiency=proficiency,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        return self._expertise.create(exp)

    def update_expertise(
        self, exp_id: UUID, fields: dict, actor_id: UUID
    ) -> FacultyExpertise:
        exp = self._expertise.get(exp_id)
        if exp is None:
            raise ExpertiseNotFoundError(f"Expertise record {exp_id} not found.")
        faculty = self._faculty.get(exp.faculty_id)
        if faculty is None or faculty.user_id != actor_id:
            raise NotOwnerError("You can only edit your own expertise records.")
        return self._expertise.update(exp_id, fields, actor_id)

    def remove_expertise(self, exp_id: UUID, actor_id: UUID) -> FacultyExpertise:
        exp = self._expertise.get(exp_id)
        if exp is None:
            raise ExpertiseNotFoundError(f"Expertise record {exp_id} not found.")
        faculty = self._faculty.get(exp.faculty_id)
        if faculty is None or faculty.user_id != actor_id:
            raise NotOwnerError("You can only delete your own expertise records.")
        return self._expertise.soft_delete(exp_id, actor_id)

    def list_expertise(self, faculty_id: UUID) -> list[FacultyExpertise]:
        records = self._expertise.list_by_faculty(faculty_id)
        return sorted(records, key=lambda e: e.area.lower())

    # ── Documents ─────────────────────────────────────────────────────────────

    def add_document(
        self,
        faculty_id: UUID,
        *,
        file_asset_id: UUID,
        doc_type: str,
        actor_id: UUID,
        description: str | None = None,
    ) -> FacultyDocument:
        self._assert_faculty_exists(faculty_id)
        if doc_type not in _VALID_DOC_TYPES:
            raise FacultyServiceError(
                f"doc_type must be one of: {', '.join(sorted(_VALID_DOC_TYPES))}."
            )
        now = datetime.now(UTC)
        doc = FacultyDocument(
            faculty_id=faculty_id,
            file_asset_id=file_asset_id,
            doc_type=doc_type,
            description=description,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        return self._document.create(doc)

    def update_document(
        self, doc_id: UUID, fields: dict, actor_id: UUID
    ) -> FacultyDocument:
        doc = self._document.get(doc_id)
        if doc is None:
            raise FacultyServiceError(f"Document record {doc_id} not found.")
        if "doc_type" in fields and fields["doc_type"] not in _VALID_DOC_TYPES:
            raise FacultyServiceError(
                f"doc_type must be one of: {', '.join(sorted(_VALID_DOC_TYPES))}."
            )
        return self._document.update(doc_id, fields, actor_id)

    def remove_document(self, doc_id: UUID, actor_id: UUID) -> FacultyDocument:
        doc = self._document.get(doc_id)
        if doc is None:
            raise FacultyServiceError(f"Document record {doc_id} not found.")
        return self._document.soft_delete(doc_id, actor_id)

    def list_documents(self, faculty_id: UUID) -> list[FacultyDocument]:
        records = self._document.list_by_faculty(faculty_id)
        return sorted(records, key=lambda d: d.created_at, reverse=True)

    # ── Document upload path (P4 — free-form type + file bytes) ───────────────

    def upload_document(
        self,
        faculty_id: UUID,
        *,
        document_type: str,
        description: str | None,
        file_bytes: bytes,
        original_filename: str,
        mime_type: str,
        actor_id: UUID,
    ) -> FacultyDocument:
        """Validate PDF MIME + 2MB cap, upload bytes, create FileAsset + FacultyDocument.

        Mirrors update_photo's storage flow (P2.3 corrected path).
        Raises DocumentInvalidMimeError / DocumentTooLargeError / FacultyNotFoundError /
        NotOwnerError.
        """
        if mime_type not in _DOCUMENT_ALLOWED_MIMES:
            raise DocumentInvalidMimeError("Document must be PDF.")
        if len(file_bytes) > _DOCUMENT_MAX_BYTES:
            raise DocumentTooLargeError("Document must be 2MB or less.")

        faculty = self._faculty.get(faculty_id)
        if faculty is None:
            raise FacultyNotFoundError(f"Faculty {faculty_id} not found.")
        if faculty.user_id != actor_id:
            raise NotOwnerError("You can only edit your own Faculty profile.")

        from durgam.repositories.file_asset import FileAssetRepository
        from durgam.services.upload import UploadService
        from durgam.storage import get_storage_backend

        file_repo = FileAssetRepository(self._faculty._session)
        upload_svc = UploadService(
            file_repo=file_repo,
            backend=get_storage_backend(),
            allowed_mimes=_DOCUMENT_ALLOWED_MIMES,
            max_size_mb=2,
        )
        new_asset = upload_svc.upload(
            data=file_bytes,
            original_name=original_filename,
            mime_type=mime_type,
            actor_id=actor_id,
            purpose="faculty_document",
        )

        now = datetime.now(UTC)
        doc = FacultyDocument(
            faculty_id=faculty_id,
            file_asset_id=new_asset.id,
            doc_type=document_type.strip(),
            description=description,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        return self._document.create(doc)

    def update_document_metadata(
        self,
        doc_id: UUID,
        *,
        document_type: str,
        description: str | None,
        actor_id: UUID,
    ) -> FacultyDocument:
        """Update document type + description only. File is immutable post-upload."""
        doc = self._document.get(doc_id)
        if doc is None:
            raise DocumentNotFoundError(f"Document record {doc_id} not found.")
        faculty = self._faculty.get(doc.faculty_id)
        if faculty is None or faculty.user_id != actor_id:
            raise NotOwnerError("You can only edit your own documents.")
        return self._document.update(
            doc_id,
            {"doc_type": document_type.strip(), "description": description},
            actor_id,
        )

    def remove_document_and_file(
        self, doc_id: UUID, actor_id: UUID
    ) -> FacultyDocument:
        """Soft-delete both the FacultyDocument and its linked FileAsset."""
        doc = self._document.get(doc_id)
        if doc is None:
            raise DocumentNotFoundError(f"Document record {doc_id} not found.")
        faculty = self._faculty.get(doc.faculty_id)
        if faculty is None or faculty.user_id != actor_id:
            raise NotOwnerError("You can only delete your own documents.")

        from durgam.models.crosscutting import FileAsset
        from durgam.repositories.file_asset import FileAssetRepository

        file_repo = FileAssetRepository(self._faculty._session)
        asset = self._faculty._session.get(FileAsset, doc.file_asset_id)
        if asset is not None and not asset.is_deleted:
            file_repo.soft_delete(asset, actor_id)
        return self._document.soft_delete(doc_id, actor_id)

    # ── Workload ──────────────────────────────────────────────────────────────

    def upsert_workload(
        self,
        faculty_id: UUID,
        academic_year_id: UUID,
        semester: str,
        entries: list[dict],
        actor_id: UUID,
        notes: str | None = None,
    ) -> FacultyWorkload:
        self._assert_faculty_exists(faculty_id)
        if not semester.strip():
            raise FacultyServiceError("Semester is required.")
        return self._workload.upsert(
            faculty_id=faculty_id,
            academic_year_id=academic_year_id,
            semester=semester.strip(),
            entries=entries,
            notes=notes,
            actor_id=actor_id,
        )

    def list_workload(self, faculty_id: UUID) -> list[FacultyWorkload]:
        return self._workload.list_by_faculty(faculty_id)

    def list_workload_by_ay(
        self, faculty_id: UUID, academic_year_id: UUID
    ) -> list[FacultyWorkload]:
        return self._workload.list_by_faculty_ay(faculty_id, academic_year_id)

    def remove_workload(self, wl_id: UUID, actor_id: UUID) -> FacultyWorkload:
        wl = self._workload.get(wl_id)
        if wl is None:
            raise FacultyServiceError(f"Workload record {wl_id} not found.")
        return self._workload.soft_delete(wl_id, actor_id)

    # ── Private validators ────────────────────────────────────────────────────

    # ── Section-specific self-edit methods (P1) ──────────────────────────────

    def update_contact(
        self,
        faculty_id: UUID,
        *,
        phone: str,
        whatsapp: str | None,
        alt_phone: str | None,
        alt_email: str | None,
        emergency_contact_name: str,
        emergency_contact_relation: str,
        emergency_contact_phone: str,
        actor_id: UUID,
    ) -> Faculty:
        """Update contact + emergency contact fields. Other fields untouched."""
        faculty = self._faculty.get(faculty_id)
        if faculty is None:
            raise FacultyNotFoundError(f"Faculty {faculty_id} not found.")
        if faculty.user_id != actor_id:
            raise NotOwnerError("You can only edit your own Faculty profile.")
        return self._faculty.update(faculty_id, {
            "phone": phone.strip(),
            "whatsapp": whatsapp.strip() if whatsapp else None,
            "alt_phone": alt_phone.strip() if alt_phone else None,
            "alt_email": alt_email.strip() if alt_email else None,
            "emergency_contact_name": emergency_contact_name.strip(),
            "emergency_contact_relation": emergency_contact_relation.strip(),
            "emergency_contact_phone": emergency_contact_phone.strip(),
        }, actor_id)

    def update_external_ids(
        self,
        faculty_id: UUID,
        *,
        orcid: str | None,
        linkedin: str | None,
        google_scholar: str | None,
        researchgate: str | None,
        actor_id: UUID,
    ) -> Faculty:
        """Update external IDs. Other fields untouched."""
        faculty = self._faculty.get(faculty_id)
        if faculty is None:
            raise FacultyNotFoundError(f"Faculty {faculty_id} not found.")
        if faculty.user_id != actor_id:
            raise NotOwnerError("You can only edit your own Faculty profile.")
        if not orcid or not orcid.strip():
            raise OrcidRequiredError("ORCID iD is required.")
        return self._faculty.update(faculty_id, {
            "orcid": orcid.strip(),
            "linkedin": linkedin.strip() if linkedin else None,
            "google_scholar": google_scholar.strip() if google_scholar else None,
            "researchgate": researchgate.strip() if researchgate else None,
        }, actor_id)

    def update_phd_section(
        self,
        faculty_id: UUID,
        *,
        is_phd: bool,
        phd_thesis_title: str | None,
        phd_registration_number: str | None,
        phd_awarding_institution: str | None,
        phd_year: int | None,
        actor_id: UUID,
    ) -> Faculty:
        """Update PhD section. If is_phd=False, clears all 4 phd_* fields."""
        faculty = self._faculty.get(faculty_id)
        if faculty is None:
            raise FacultyNotFoundError(f"Faculty {faculty_id} not found.")
        if faculty.user_id != actor_id:
            raise NotOwnerError("You can only edit your own Faculty profile.")
        if not is_phd:
            fields: dict = {
                "is_phd": False,
                "phd_thesis_title": None,
                "phd_registration_number": None,
                "phd_awarding_institution": None,
                "phd_year": None,
            }
        else:
            if phd_year is not None:
                current_year = datetime.now(UTC).year
                if not (1900 <= phd_year <= current_year + 1):
                    raise InvalidPhdYearError(
                        f"PhD year {phd_year} must be in [1900, {current_year + 1}]."
                    )
            fields = {
                "is_phd": True,
                "phd_thesis_title": phd_thesis_title.strip() if phd_thesis_title else None,
                "phd_registration_number": phd_registration_number.strip() if phd_registration_number else None,
                "phd_awarding_institution": phd_awarding_institution.strip() if phd_awarding_institution else None,
                "phd_year": phd_year,
            }
        return self._faculty.update(faculty_id, fields, actor_id)

    # ── Photo management ──────────────────────────────────────────────────────

    def update_photo(
        self,
        faculty_id: UUID,
        *,
        file_bytes: bytes,
        original_filename: str,
        mime_type: str,
        actor_id: UUID,
    ) -> Faculty:
        """Validate MIME + size, soft-delete previous photo, upload new, update FK.

        Raises PhotoInvalidMimeError for non-image MIME.
        Raises PhotoTooLargeError when file_bytes exceeds 1MB.
        Raises FacultyNotFoundError / NotOwnerError when appropriate.
        """
        if mime_type not in _PHOTO_ALLOWED_MIMES:
            raise PhotoInvalidMimeError(
                f"Photo must be JPEG or PNG, got '{mime_type}'."
            )
        if len(file_bytes) > _PHOTO_MAX_BYTES:
            raise PhotoTooLargeError("Photo must be 1MB or less.")

        faculty = self._faculty.get(faculty_id)
        if faculty is None:
            raise FacultyNotFoundError(f"Faculty {faculty_id} not found.")
        if faculty.user_id != actor_id:
            raise NotOwnerError("You can only edit your own Faculty profile.")

        from durgam.models.crosscutting import FileAsset
        from durgam.repositories.file_asset import FileAssetRepository
        from durgam.services.upload import UploadService
        from durgam.storage import get_storage_backend

        file_repo = FileAssetRepository(self._faculty._session)
        upload_svc = UploadService(
            file_repo=file_repo,
            backend=get_storage_backend(),
            allowed_mimes=_PHOTO_ALLOWED_MIMES,
            max_size_mb=1,
        )

        if faculty.photo_file_id is not None:
            old_asset = self._faculty._session.get(FileAsset, faculty.photo_file_id)
            if old_asset is not None and not old_asset.is_deleted:
                file_repo.soft_delete(old_asset, actor_id)

        new_asset = upload_svc.upload(
            data=file_bytes,
            original_name=original_filename,
            mime_type=mime_type,
            actor_id=actor_id,
            purpose="faculty_photo",
        )
        return self._faculty.update(faculty_id, {"photo_file_id": new_asset.id}, actor_id)

    def remove_photo(
        self,
        faculty_id: UUID,
        *,
        actor_id: UUID,
    ) -> Faculty:
        """Soft-delete current photo FileAsset and clear Faculty.photo_file_id.

        No-op (no error) if no photo is currently set.
        """
        faculty = self._faculty.get(faculty_id)
        if faculty is None:
            raise FacultyNotFoundError(f"Faculty {faculty_id} not found.")
        if faculty.user_id != actor_id:
            raise NotOwnerError("You can only edit your own Faculty profile.")

        if faculty.photo_file_id is not None:
            from durgam.models.crosscutting import FileAsset
            from durgam.repositories.file_asset import FileAssetRepository

            file_repo = FileAssetRepository(self._faculty._session)
            old_asset = self._faculty._session.get(FileAsset, faculty.photo_file_id)
            if old_asset is not None and not old_asset.is_deleted:
                file_repo.soft_delete(old_asset, actor_id)
            return self._faculty.update(faculty_id, {"photo_file_id": None}, actor_id)

        return faculty

    # ── Private validators ────────────────────────────────────────────────────

    def _assert_faculty_exists(self, faculty_id: UUID) -> None:
        if self._faculty.get(faculty_id) is None:
            raise FacultyServiceError(f"Faculty {faculty_id} not found.")

    def _assert_employee_id_unique(
        self, employee_id: str, exclude_id: UUID | None
    ) -> None:
        existing = self._faculty.get_by_employee_id(employee_id.strip())
        if existing is not None and existing.id != exclude_id:
            raise EmployeeIdConflictError(
                f"Employee ID '{employee_id}' is already assigned to another faculty member."
            )
