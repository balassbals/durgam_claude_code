"""FacultyService — business rules for the Faculty Module (M10 Phase 2).

Layering: service owns validation rules; repositories own all SQL.
No session.commit() here — callers (page states) must commit.
"""

from __future__ import annotations

from datetime import UTC, datetime
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
        self._assert_faculty_exists(faculty_id)
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
            raise FacultyServiceError(f"Education record {edu_id} not found.")
        return self._education.update(edu_id, fields, actor_id)

    def remove_education(self, edu_id: UUID, actor_id: UUID) -> FacultyEducation:
        edu = self._education.get(edu_id)
        if edu is None:
            raise FacultyServiceError(f"Education record {edu_id} not found.")
        return self._education.soft_delete(edu_id, actor_id)

    def list_education(self, faculty_id: UUID) -> list[FacultyEducation]:
        return self._education.list_by_faculty(faculty_id)

    # ── Experience ────────────────────────────────────────────────────────────

    def add_experience(
        self,
        faculty_id: UUID,
        *,
        organization: str,
        designation_held: str,
        from_date: object,
        actor_id: UUID,
        to_date: object | None = None,
        responsibilities: str | None = None,
    ) -> FacultyExperience:
        self._assert_faculty_exists(faculty_id)
        now = datetime.now(UTC)
        exp = FacultyExperience(
            faculty_id=faculty_id,
            organization=organization.strip(),
            designation_held=designation_held.strip(),
            from_date=from_date,  # type: ignore[arg-type]
            to_date=to_date,  # type: ignore[arg-type]
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
            raise FacultyServiceError(f"Experience record {exp_id} not found.")
        return self._experience.update(exp_id, fields, actor_id)

    def remove_experience(self, exp_id: UUID, actor_id: UUID) -> FacultyExperience:
        exp = self._experience.get(exp_id)
        if exp is None:
            raise FacultyServiceError(f"Experience record {exp_id} not found.")
        return self._experience.soft_delete(exp_id, actor_id)

    def list_experience(self, faculty_id: UUID) -> list[FacultyExperience]:
        return self._experience.list_by_faculty(faculty_id)

    # ── Expertise ─────────────────────────────────────────────────────────────

    def add_expertise(
        self,
        faculty_id: UUID,
        *,
        area: str,
        actor_id: UUID,
        proficiency: str | None = None,
    ) -> FacultyExpertise:
        self._assert_faculty_exists(faculty_id)
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
            raise FacultyServiceError(f"Expertise record {exp_id} not found.")
        return self._expertise.update(exp_id, fields, actor_id)

    def remove_expertise(self, exp_id: UUID, actor_id: UUID) -> FacultyExpertise:
        exp = self._expertise.get(exp_id)
        if exp is None:
            raise FacultyServiceError(f"Expertise record {exp_id} not found.")
        return self._expertise.soft_delete(exp_id, actor_id)

    def list_expertise(self, faculty_id: UUID) -> list[FacultyExpertise]:
        return self._expertise.list_by_faculty(faculty_id)

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
        return self._document.list_by_faculty(faculty_id)

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
