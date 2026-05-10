"""Academic-year anchors and configuration tables (§8.5)."""

from datetime import date
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from .base import TimestampedSoftDelete


class AcademicYear(TimestampedSoftDelete, table=True):
    __tablename__ = "academic_years"
    __table_args__ = (sa.UniqueConstraint("code", name="uq_academic_years_code"),)

    code: str = Field(max_length=10, nullable=False)  # e.g. '2025-26'
    starts_on: date = Field(nullable=False)
    ends_on: date = Field(nullable=False)
    is_locked: bool = Field(default=False, nullable=False)


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
