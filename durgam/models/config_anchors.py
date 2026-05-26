"""Academic-year anchors and configuration tables (§8.5, §9.3)."""

from datetime import date, datetime
from typing import Any, cast
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from .base import TimestampedSoftDelete

_TIMESTAMPTZ: type[Any] = cast(type[Any], sa.DateTime(timezone=True))


class AcademicYear(TimestampedSoftDelete, table=True):
    __tablename__ = "academic_years"
    __table_args__ = (sa.UniqueConstraint("code", name="uq_academic_years_code"),)

    code: str = Field(max_length=10, nullable=False)  # e.g. '2025-26'
    starts_on: date = Field(nullable=False)
    ends_on: date = Field(nullable=False)
    is_locked: bool = Field(default=False, nullable=False)
    master_calendar_locked: bool = Field(default=False, nullable=False)
    iqac_confirmed: bool = Field(default=False, nullable=False)


class Holiday(TimestampedSoftDelete, table=True):
    __tablename__ = "holidays"
    __table_args__ = (
        sa.UniqueConstraint("holiday_date", "academic_year_id", name="uq_holidays_date_ay"),
        sa.Index("ix_holidays_academic_year_id", "academic_year_id"),
    )

    academic_year_id: UUID = Field(foreign_key="academic_years.id", nullable=False)
    holiday_date: date = Field(nullable=False)
    name: str = Field(max_length=128, nullable=False)


class RoleEmail(TimestampedSoftDelete, table=True):
    """Email address bound to a role in a specific scope (§8.5)."""

    __tablename__ = "role_emails"
    __table_args__ = (
        sa.Index(
            "uq_role_emails_global",
            "role_code",
            unique=True,
            postgresql_where=sa.text("scope_type IS NULL AND is_deleted = false"),
        ),
        sa.Index(
            "uq_role_emails_scoped",
            "role_code",
            "scope_type",
            "scope_id",
            unique=True,
            postgresql_where=sa.text("is_deleted = false"),
        ),
    )

    role_code: str = Field(max_length=64, nullable=False)
    scope_type: str | None = Field(default=None, max_length=32)
    scope_id: UUID | None = Field(default=None)
    email: str = Field(max_length=254, nullable=False)


class DocumentTemplate(TimestampedSoftDelete, table=True):
    """Unified document template — letterheads + type-based templates (E-005)."""

    __tablename__ = "document_templates"
    __table_args__ = (
        sa.Index(
            "uq_document_templates_letterhead_global",
            "purpose",
            "role_code",
            unique=True,
            postgresql_where=sa.text(
                "scope_type IS NULL AND is_deleted = false AND role_code IS NOT NULL"
            ),
        ),
        sa.Index(
            "uq_document_templates_letterhead_scoped",
            "purpose",
            "role_code",
            "scope_type",
            "scope_id",
            unique=True,
            postgresql_where=sa.text(
                "is_deleted = false AND role_code IS NOT NULL"
            ),
        ),
        sa.Index(
            "uq_document_templates_type",
            "purpose",
            unique=True,
            postgresql_where=sa.text(
                "is_deleted = false AND role_code IS NULL"
            ),
        ),
    )

    purpose: str = Field(max_length=16, nullable=False)
    role_code: str | None = Field(default=None, max_length=64)
    scope_type: str | None = Field(default=None, max_length=32)
    scope_id: UUID | None = Field(default=None)
    file_id: UUID = Field(foreign_key="file_assets.id", nullable=False)


class StudentCategoryCount(TimestampedSoftDelete, table=True):
    """One row per academic year; enforced by unique constraint."""

    __tablename__ = "student_category_counts"
    __table_args__ = (
        sa.UniqueConstraint("academic_year_id", name="uq_student_category_counts_ay"),
    )

    academic_year_id: UUID = Field(foreign_key="academic_years.id", nullable=False)
    sc_count: int = Field(default=0, nullable=False)
    st_count: int = Field(default=0, nullable=False)
    obc_count: int = Field(default=0, nullable=False)
    ews_count: int = Field(default=0, nullable=False)
    general_count: int = Field(default=0, nullable=False)
    notes: str | None = Field(default=None)


class ClassTimingsConfig(TimestampedSoftDelete, table=True):
    """Singleton — one row defines institute-wide class period timings.

    Enforced at application level (OQ-M3-9). Break fields are optional
    because some timetable configurations may not define a fixed break period.
    """

    __tablename__ = "class_timings_configs"

    periods_per_day: int = Field(nullable=False)
    period_duration_minutes: int = Field(nullable=False)
    first_period_start: str = Field(max_length=5, nullable=False)  # HH:MM
    break_after_period: int | None = Field(default=None, nullable=True)
    break_duration_minutes: int | None = Field(default=None, nullable=True)


class WorkingDaysConfig(TimestampedSoftDelete, table=True):
    """Singleton — 5-day or 6-day work week; enforced at application level."""

    __tablename__ = "working_days_configs"

    days_per_week: int = Field(nullable=False)  # 5 or 6


class CalendarEntry(TimestampedSoftDelete, table=True):
    """AY-scoped calendar entry with role-based ownership (§8.5, §9.3)."""

    __tablename__ = "calendar_entries"
    __table_args__ = (
        sa.Index("ix_calendar_entries_academic_year_id", "academic_year_id"),
        sa.Index("ix_calendar_entries_entry_type", "entry_type"),
    )

    academic_year_id: UUID = Field(foreign_key="academic_years.id", nullable=False)
    title: str = Field(max_length=256, nullable=False)
    entry_type: str = Field(max_length=32, nullable=False)
    starts_at: datetime = Field(sa_type=_TIMESTAMPTZ, nullable=False)
    ends_at: datetime = Field(sa_type=_TIMESTAMPTZ, nullable=False)
    owner_user_id: UUID = Field(foreign_key="users.id", nullable=False)
    owner_role_code: str = Field(max_length=64, nullable=False)
    scope_type: str | None = Field(default=None, max_length=32)
    scope_id: UUID | None = Field(default=None)
    notes: str | None = Field(default=None)


# ── M5b: Assignments & Counsellor ─────────────────────────────────────────────


class MentalHealthCounsellor(TimestampedSoftDelete, table=True):
    """Campus-wise mental health counsellor roster (§9.3, line 146)."""

    __tablename__ = "mental_health_counsellors"
    __table_args__ = (
        sa.Index("ix_mhc_ay_campus", "academic_year_id", "campus_id"),
    )

    academic_year_id: UUID = Field(foreign_key="academic_years.id", nullable=False)
    campus_id: UUID = Field(foreign_key="campuses.id", nullable=False)
    name: str = Field(max_length=128, nullable=False)
    qualification: str = Field(max_length=128, nullable=False)
    specialisation: str = Field(max_length=128, nullable=False)
    mode_of_appointment: str = Field(max_length=16, nullable=False)
    appointment_start: date = Field(nullable=False)
    appointment_end: date = Field(nullable=False)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=254)
    appointment_letter_file_id: UUID | None = Field(
        default=None, foreign_key="file_assets.id",
    )
    qualification_proof_file_id: UUID | None = Field(
        default=None, foreign_key="file_assets.id",
    )
    display_order: int = Field(default=0, nullable=False)


class FacultyMentorAssignment(TimestampedSoftDelete, table=True):
    """Faculty-to-student mentor assignment (§9.3, line 147)."""

    __tablename__ = "faculty_mentor_assignments"
    __table_args__ = (
        sa.Index("ix_fma_ay_campus", "academic_year_id", "campus_id"),
    )

    academic_year_id: UUID = Field(foreign_key="academic_years.id", nullable=False)
    campus_id: UUID = Field(foreign_key="campuses.id", nullable=False)
    faculty_id_placeholder: str = Field(max_length=128, nullable=False)
    student_id_placeholder: str = Field(max_length=128, nullable=False)
    notes: str | None = Field(default=None)


class ClassTeacherAssignment(TimestampedSoftDelete, table=True):
    """Class teacher assignment per department (§9.3, line 150)."""

    __tablename__ = "class_teacher_assignments"
    __table_args__ = (
        sa.Index("ix_cta_ay_dept", "academic_year_id", "department_id"),
    )

    academic_year_id: UUID = Field(foreign_key="academic_years.id", nullable=False)
    department_id: UUID = Field(foreign_key="departments.id", nullable=False)
    faculty_id_placeholder: str = Field(max_length=128, nullable=False)
    class_identifier: str = Field(max_length=64, nullable=False)
    notes: str | None = Field(default=None)


class ClassCoordinatorAssignment(TimestampedSoftDelete, table=True):
    """Class coordinator assignment — max 2 per class per AY (§9.3, line 150)."""

    __tablename__ = "class_coordinator_assignments"
    __table_args__ = (
        sa.Index("ix_cca_ay_dept", "academic_year_id", "department_id"),
    )

    academic_year_id: UUID = Field(foreign_key="academic_years.id", nullable=False)
    department_id: UUID = Field(foreign_key="departments.id", nullable=False)
    faculty_id_placeholder: str = Field(max_length=128, nullable=False)
    class_identifier: str = Field(max_length=64, nullable=False)
    notes: str | None = Field(default=None)


class VisitingFaculty(TimestampedSoftDelete, table=True):
    """External visiting/adjunct/guest faculty (DQ-M5b-4, §9.10).

    Date-windowed, not AY-locked — availability may straddle academic years.
    No academic_year_id; AY-lock machinery does not apply.
    """

    __tablename__ = "visiting_faculty"
    __table_args__ = (
        sa.Index("ix_vf_department_id", "department_id"),
    )

    department_id: UUID = Field(foreign_key="departments.id", nullable=False)
    name: str = Field(max_length=128, nullable=False)
    designation: str = Field(max_length=128, nullable=False)
    organization: str = Field(max_length=256, nullable=False)
    expertise: str = Field(max_length=256, nullable=False)
    available_from: date = Field(nullable=False)
    available_to: date = Field(nullable=False)
    is_admin_approved: bool = Field(default=False, nullable=False)


class NonOwnedCourse(TimestampedSoftDelete, table=True):
    """Course not owned by any department — MDC, awareness, etc. (§9.3, line 151).

    AY-scoped. Faculty assignment is a placeholder until M10 Faculty exists.
    No department_id — the whole point is that these belong to no department.
    """

    __tablename__ = "non_owned_courses"
    __table_args__ = (
        sa.Index("ix_noc_academic_year_id", "academic_year_id"),
    )

    academic_year_id: UUID = Field(foreign_key="academic_years.id", nullable=False)
    course_code: str = Field(max_length=20, nullable=False)
    course_name: str = Field(max_length=200, nullable=False)
    credits: int = Field(default=0, nullable=False)
    semester: str = Field(max_length=10, nullable=False)
    faculty_id_placeholder: str = Field(max_length=128, nullable=False)
    notes: str | None = Field(default=None)


class UGTimetable(TimestampedSoftDelete, table=True):
    """Director's master UG timetable grid for 1st/2nd year (§9.3, line 152).

    AY-scoped. Each row is one period slot. Dept-projection is M13/M14.
    Unique constraint prevents double-booking a slot.
    """

    __tablename__ = "ug_timetable"
    __table_args__ = (
        sa.UniqueConstraint(
            "academic_year_id", "semester", "year_of_study",
            "day_of_week", "period_number",
            name="uq_ug_timetable_slot",
        ),
        sa.Index("ix_ugt_academic_year_id", "academic_year_id"),
    )

    academic_year_id: UUID = Field(foreign_key="academic_years.id", nullable=False)
    semester: str = Field(max_length=10, nullable=False)
    year_of_study: int = Field(nullable=False)
    day_of_week: int = Field(nullable=False)
    period_number: int = Field(nullable=False)
    course_code: str = Field(max_length=20, nullable=False)
    course_name: str = Field(max_length=200, nullable=False)
    faculty_id_placeholder: str = Field(max_length=128, nullable=False)
    room: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None)
