"""Vision and mission models for university and departments (E-001).

Both entities are update-only: soft-delete and hard-delete are blocked at the
service layer (VisionMissionService raises NotDeletableError). The models
intentionally inherit TimestampedSoftDelete for audit columns.

UniversityVisionMission: singleton — one row only, enforced at application level.
DepartmentVisionMission: one per Department, enforced by unique constraint.
"""

from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field

from .base import TimestampedSoftDelete


class UniversityVisionMission(TimestampedSoftDelete, table=True):
    """Singleton — one row holds the university's vision text."""

    __tablename__ = "university_vision_missions"

    vision: str = Field(nullable=False)


class UniversityMission(TimestampedSoftDelete, table=True):
    __tablename__ = "university_missions"
    __table_args__ = (
        sa.Index(
            "ix_university_missions_university_vision_id", "university_vision_id"
        ),
    )

    university_vision_id: UUID = Field(
        foreign_key="university_vision_missions.id", nullable=False
    )
    statement: str = Field(nullable=False)
    display_order: int = Field(default=0, nullable=False)


class DepartmentVisionMission(TimestampedSoftDelete, table=True):
    """One row per Department — unique constraint on department_id."""

    __tablename__ = "department_vision_missions"
    __table_args__ = (
        sa.UniqueConstraint(
            "department_id", name="uq_department_vision_missions_dept"
        ),
    )

    department_id: UUID = Field(foreign_key="departments.id", nullable=False)
    vision: str = Field(nullable=False)


class DepartmentMission(TimestampedSoftDelete, table=True):
    __tablename__ = "department_missions"
    __table_args__ = (
        sa.Index(
            "ix_department_missions_department_vision_id", "department_vision_id"
        ),
    )

    department_vision_id: UUID = Field(
        foreign_key="department_vision_missions.id", nullable=False
    )
    statement: str = Field(nullable=False)
    display_order: int = Field(default=0, nullable=False)
