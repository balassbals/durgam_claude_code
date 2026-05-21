"""Course model — M3 basic fields (§8.2, §9.3 M3).

M13 will extend with: course_type, delivery_mode, mooc_agency, has_iks,
is_skill_based, is_value_education, revised_year (Refinement 3).
"""

from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field

from .base import TimestampedSoftDelete


class Course(TimestampedSoftDelete, table=True):
    __tablename__ = "courses"
    __table_args__ = (
        sa.UniqueConstraint("code", name="uq_courses_code"),
        sa.Index("ix_courses_program_id", "program_id"),
        sa.Index("ix_courses_department_id", "department_id"),
    )

    code: str = Field(max_length=20, nullable=False)  # e.g. MAT101
    name: str = Field(max_length=200, nullable=False)
    program_id: UUID = Field(foreign_key="programs.id", nullable=False)
    department_id: UUID = Field(foreign_key="departments.id", nullable=False)
    credits: int = Field(nullable=False)
    lecture: int = Field(default=0, nullable=False)
    tutorial: int = Field(default=0, nullable=False)
    practical: int = Field(default=0, nullable=False)
    evaluation: str = Field(max_length=5, nullable=False)  # I | E | IE
    is_active: bool = Field(default=True, nullable=False)
