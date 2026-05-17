"""Program and sub-entity models (§8.2, §9.3 M3).

Sub-entity UI (PEO/PO/PSO editing, regulation forms, scheme management) defers
to M13. The models and seed data meet the M3 gate clause.

ProgramSchemeCourse references courses.id (defined in course.py) via a string FK;
SQLAlchemy resolves it lazily after all models are imported.
"""

from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from .base import TimestampedSoftDelete


class Program(TimestampedSoftDelete, table=True):
    __tablename__ = "programs"
    __table_args__ = (
        sa.UniqueConstraint("code", name="uq_programs_code"),
        sa.Index("ix_programs_department_id", "department_id"),
    )

    code: str = Field(max_length=20, nullable=False)  # e.g. BSCMATH
    name: str = Field(max_length=200, nullable=False)
    department_id: UUID = Field(foreign_key="departments.id", nullable=False)
    # Unconstrained at M3; M13 introduces enum (OQ-M3-10)
    degree_type: str = Field(max_length=50, nullable=False)  # BSc | MSc | BTech | ...
    duration_years: int = Field(nullable=False)
    is_active: bool = Field(default=True, nullable=False)


class ProgramDepartment(SQLModel, table=True):
    """Additional departments for jointly-run programs."""

    __tablename__ = "program_departments"

    program_id: UUID = Field(foreign_key="programs.id", primary_key=True)
    department_id: UUID = Field(foreign_key="departments.id", primary_key=True)


class ProgramOutcome(TimestampedSoftDelete, table=True):
    """PEOs, POs, and PSOs — discriminated by outcome_type."""

    __tablename__ = "program_outcomes"
    __table_args__ = (
        sa.UniqueConstraint(
            "program_id",
            "outcome_type",
            "code",
            name="uq_program_outcomes_program_type_code",
        ),
        sa.Index("ix_program_outcomes_program_id", "program_id"),
    )

    program_id: UUID = Field(foreign_key="programs.id", nullable=False)
    outcome_type: str = Field(max_length=5, nullable=False)  # PEO | PO | PSO
    code: str = Field(max_length=10, nullable=False)  # PEO1 | PO1 | PSO1 | ...
    description: str = Field(nullable=False)
    display_order: int = Field(default=0, nullable=False)


class ProgramRegulation(TimestampedSoftDelete, table=True):
    __tablename__ = "program_regulations"
    __table_args__ = (
        sa.UniqueConstraint(
            "program_id", "code", name="uq_program_regulations_program_code"
        ),
        sa.Index("ix_program_regulations_program_id", "program_id"),
    )

    program_id: UUID = Field(foreign_key="programs.id", nullable=False)
    code: str = Field(max_length=20, nullable=False)  # R2019 | R2021 | ...
    effective_from_year: int = Field(nullable=False)
    description: str | None = Field(default=None, nullable=True)


class ProgramScheme(TimestampedSoftDelete, table=True):
    """Scheme of instruction — one row per (program, regulation, semester)."""

    __tablename__ = "program_schemes"
    __table_args__ = (
        sa.UniqueConstraint(
            "program_id",
            "regulation_id",
            "semester",
            name="uq_program_schemes_program_reg_sem",
        ),
        sa.Index("ix_program_schemes_program_id", "program_id"),
        sa.Index("ix_program_schemes_regulation_id", "regulation_id"),
    )

    program_id: UUID = Field(foreign_key="programs.id", nullable=False)
    regulation_id: UUID = Field(foreign_key="program_regulations.id", nullable=False)
    semester: int = Field(nullable=False)
    total_credits: int = Field(default=0, nullable=False)


class ProgramSchemeCourse(SQLModel, table=True):
    """Junction: courses included in a scheme of instruction."""

    __tablename__ = "program_scheme_courses"

    scheme_id: UUID = Field(foreign_key="program_schemes.id", primary_key=True)
    # courses.id resolved lazily — Course is defined in course.py
    course_id: UUID = Field(foreign_key="courses.id", primary_key=True)


class ProgramSpecialisation(TimestampedSoftDelete, table=True):
    __tablename__ = "program_specialisations"
    __table_args__ = (
        sa.UniqueConstraint(
            "program_id", "code", name="uq_program_specialisations_program_code"
        ),
        sa.Index("ix_program_specialisations_program_id", "program_id"),
    )

    program_id: UUID = Field(foreign_key="programs.id", nullable=False)
    code: str = Field(max_length=20, nullable=False)
    name: str = Field(max_length=200, nullable=False)
    description: str | None = Field(default=None, nullable=True)


class ProgramExitLevel(TimestampedSoftDelete, table=True):
    __tablename__ = "program_exit_levels"
    __table_args__ = (
        sa.UniqueConstraint(
            "program_id", "level_name", name="uq_program_exit_levels_program_level"
        ),
        sa.Index("ix_program_exit_levels_program_id", "program_id"),
    )

    program_id: UUID = Field(foreign_key="programs.id", nullable=False)
    level_name: str = Field(max_length=100, nullable=False)
    required_credits: int = Field(nullable=False)
    description: str | None = Field(default=None, nullable=True)
