"""Academic-year anchors and configuration tables (§8.5)."""

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


class RoleEmail(SQLModel, table=True):
    """Email address bound to a role in a specific scope."""

    __tablename__ = "role_emails"
    __table_args__ = (
        sa.UniqueConstraint(
            "role_code", "scope_type", "scope_id", name="uq_role_emails_role_scope"
        ),
    )

    id: int = Field(default=None, primary_key=True)
    role_code: str = Field(max_length=64, nullable=False)
    scope_type: str | None = Field(default=None, max_length=32)
    scope_id: UUID | None = Field(default=None)
    email: str = Field(max_length=254, nullable=False)


class LetterheadAsset(TimestampedSoftDelete, table=True):
    __tablename__ = "letterhead_assets"

    role_code: str = Field(max_length=64, nullable=False)
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
