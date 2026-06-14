"""Faculty module models (M10 Phase 1A — D-001 through D-004)."""

from datetime import date, datetime
from typing import Any, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel

from .base import TimestampedSoftDelete

_TIMESTAMPTZ: type[Any] = cast(type[Any], sa.DateTime(timezone=True))


class Faculty(TimestampedSoftDelete, table=True):
    """Regular-teaching faculty profile — 1:1 with User (RFP §8.3 Listing).

    Exists iff User.employee_type='regular_teaching' (Q2).
    PAN/Aadhaar remain on User (already there as pan_enc/aadhaar_enc).
    Gender remains on User (M8 ML eligibility).
    """

    __tablename__ = "faculties"
    __table_args__ = (
        sa.UniqueConstraint("employee_id", name="uq_faculties_employee_id"),
        sa.Index("ix_faculties_department_id", "department_id"),
        sa.Index("ix_faculties_campus_id", "campus_id"),
        sa.Index("ix_faculties_designation_id", "designation_id"),
    )

    user_id: UUID = Field(foreign_key="users.id", unique=True, nullable=False)
    employee_id: str = Field(max_length=64, nullable=False)
    title: str = Field(max_length=16, nullable=False)
    first_name: str = Field(max_length=64, nullable=False)
    middle_name: str | None = Field(default=None, max_length=64)
    last_name: str = Field(max_length=64, nullable=False)
    designation_id: UUID = Field(foreign_key="designations.id", nullable=False)
    department_id: UUID = Field(foreign_key="departments.id", nullable=False)
    campus_id: UUID = Field(foreign_key="campuses.id", nullable=False)
    joining_date: date = Field(nullable=False)
    is_vacation_employee: bool = Field(default=True, nullable=False)
    phone: str = Field(max_length=20, nullable=False)
    whatsapp: str | None = Field(default=None, max_length=20)
    alt_phone: str | None = Field(default=None, max_length=20)
    alt_email: str | None = Field(default=None, max_length=255)
    photo_file_id: UUID | None = Field(default=None, foreign_key="file_assets.id")
    emergency_contact_name: str = Field(max_length=128, nullable=False)
    emergency_contact_relation: str = Field(max_length=64, nullable=False)
    emergency_contact_phone: str = Field(max_length=20, nullable=False)
    is_phd: bool = Field(default=False, nullable=False)
    phd_thesis_title: str | None = Field(default=None, max_length=512)
    phd_registration_number: str | None = Field(default=None, max_length=64)
    phd_awarding_institution: str | None = Field(default=None, max_length=255)
    phd_year: int | None = Field(default=None)
    orcid: str | None = Field(default=None, max_length=64)
    linkedin: str | None = Field(default=None, max_length=255)
    google_scholar: str | None = Field(default=None, max_length=255)
    researchgate: str | None = Field(default=None, max_length=255)


class FacultyEducation(TimestampedSoftDelete, table=True):
    """Education credentials — multi-row per faculty (D-002)."""

    __tablename__ = "faculty_education"
    __table_args__ = (
        sa.Index("ix_faculty_education_faculty_id", "faculty_id"),
    )

    faculty_id: UUID = Field(foreign_key="faculties.id", nullable=False)
    degree_name: str = Field(max_length=128, nullable=False)
    specialization: str | None = Field(default=None, max_length=255)
    awarding_institution: str = Field(max_length=255, nullable=False)
    year_of_award: int = Field(nullable=False)
    distinction: str | None = Field(default=None, max_length=64)


class FacultyExperience(TimestampedSoftDelete, table=True):
    """Work experience — multi-row per faculty (D-002)."""

    __tablename__ = "faculty_experience"
    __table_args__ = (
        sa.Index("ix_faculty_experience_faculty_id", "faculty_id"),
    )

    faculty_id: UUID = Field(foreign_key="faculties.id", nullable=False)
    organization: str = Field(max_length=255, nullable=False)
    designation_held: str = Field(max_length=128, nullable=False)
    from_date: date = Field(nullable=False)
    to_date: date | None = Field(default=None)
    responsibilities: str | None = Field(default=None)


class FacultyExpertise(TimestampedSoftDelete, table=True):
    """Expertise areas — multi-row per faculty (D-002)."""

    __tablename__ = "faculty_expertise"
    __table_args__ = (
        sa.Index("ix_faculty_expertise_faculty_id", "faculty_id"),
    )

    faculty_id: UUID = Field(foreign_key="faculties.id", nullable=False)
    area: str = Field(max_length=255, nullable=False)
    proficiency: str | None = Field(default=None, max_length=32)


class FacultyDocument(TimestampedSoftDelete, table=True):
    """Faculty-uploaded documents backed by FileAsset (D-003).

    purpose="faculty_document" on the FileAsset;
    doc_type ∈ {"degree_certificate", "phd_certificate", "other"} enforced at
    service layer, not via DB CHECK constraint.
    """

    __tablename__ = "faculty_documents"
    __table_args__ = (
        sa.Index("ix_faculty_documents_faculty_id", "faculty_id"),
        sa.Index("ix_faculty_documents_file_asset_id", "file_asset_id"),
    )

    faculty_id: UUID = Field(foreign_key="faculties.id", nullable=False)
    file_asset_id: UUID = Field(foreign_key="file_assets.id", nullable=False)
    doc_type: str = Field(max_length=64, nullable=False)
    description: str | None = Field(default=None, max_length=255)


class FacultyWorkload(TimestampedSoftDelete, table=True):
    """Manual workload entry per faculty per AY/semester (D-004).

    propagation hooks from course allocation reserved for M13.
    No unique constraint on (faculty, AY, semester) at M10 — rule lands at M13.
    """

    __tablename__ = "faculty_workload"
    __table_args__ = (
        sa.Index(
            "ix_faculty_workload_faculty_ay",
            "faculty_id",
            "academic_year_id",
            "semester",
        ),
    )

    faculty_id: UUID = Field(foreign_key="faculties.id", nullable=False)
    academic_year_id: UUID = Field(
        foreign_key="academic_years.id", nullable=False
    )
    semester: str = Field(max_length=16, nullable=False)
    entries_json: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, default=list),
    )
    notes: str | None = Field(default=None)
