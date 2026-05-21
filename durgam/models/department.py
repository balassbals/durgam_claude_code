"""Department, DepartmentCampus, SubDepartment, SubDepartmentCampus models (§8.2).

SubDepartmentCampus join table captures campus-specific sub-department presence
(Refinement 2: mirrors the DepartmentCampus pattern; Appendix A shows per-campus
sub-dept distribution).
"""

from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from .base import TimestampedSoftDelete


class Department(TimestampedSoftDelete, table=True):
    __tablename__ = "departments"
    __table_args__ = (
        sa.UniqueConstraint("code", name="uq_departments_code"),
        sa.Index("ix_departments_school_id", "school_id"),
    )

    code: str = Field(max_length=10, nullable=False)  # DBIO | DCHEM | DMACS | ...
    name: str = Field(max_length=200, nullable=False)
    school_id: UUID = Field(foreign_key="schools.id", nullable=False)
    main_campus_id: UUID = Field(foreign_key="campuses.id", nullable=False)


class DepartmentCampus(SQLModel, table=True):
    """Junction: campuses where this department operates."""

    __tablename__ = "department_campuses"

    department_id: UUID = Field(foreign_key="departments.id", primary_key=True)
    campus_id: UUID = Field(foreign_key="campuses.id", primary_key=True)
    has_ahod: bool = Field(default=False, nullable=False)


class SubDepartment(TimestampedSoftDelete, table=True):
    __tablename__ = "sub_departments"
    __table_args__ = (
        sa.UniqueConstraint("code", name="uq_sub_departments_code"),
        sa.Index("ix_sub_departments_parent_department_id", "parent_department_id"),
    )

    code: str = Field(max_length=10, nullable=False)  # SDPHIL | SDPSY | SDENG | ...
    name: str = Field(max_length=200, nullable=False)
    parent_department_id: UUID = Field(foreign_key="departments.id", nullable=False)


class SubDepartmentCampus(SQLModel, table=True):
    """Junction: campuses where this sub-department is present (Appendix A)."""

    __tablename__ = "sub_department_campuses"

    sub_department_id: UUID = Field(foreign_key="sub_departments.id", primary_key=True)
    campus_id: UUID = Field(foreign_key="campuses.id", primary_key=True)
