"""drop_class_coordinator_assignments

M10 Phase 11D (Q-P11D.1) — remove class_coordinator_assignments entirely.

Walkthrough finding: the table was built with faculty_id, but per SSSIHL domain
class coordinators are STUDENTS (max 2 per class, appointed by the class
teacher), not faculty. No students domain exists yet; the table has 0 rows.
Decision: drop it now and re-introduce correctly (student_id, student picker,
max-2-per-class) when the student domain ships (TD-088).

upgrade  = DROP TABLE class_coordinator_assignments (0 rows; no FK references it).
downgrade = recreate the table in its post-11A shape (faculty_id UUID NOT NULL
FK -> faculties.id + ix_cca_ay_dept + ix_cca_faculty_id), matching the schema
produced by e4b0c1d8a295 (the 11A cca backfill). Forward + reverse verified on
the dev DB.

Revision ID: c9f1a2b3d417
Revises: a7d2e4b1c508
Create Date: 2026-07-01 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "c9f1a2b3d417"
down_revision: Union[str, Sequence[str], None] = "a7d2e4b1c508"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TBL = "class_coordinator_assignments"


def upgrade() -> None:
    op.drop_table(_TBL)


def downgrade() -> None:
    op.create_table(
        _TBL,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("academic_year_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("faculty_id", sa.Uuid(), nullable=False),
        sa.Column(
            "class_identifier",
            sqlmodel.sql.sqltypes.AutoString(length=64),
            nullable=False,
        ),
        sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(
            ["faculty_id"], ["faculties.id"], name="fk_cca_faculty_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cca_ay_dept", _TBL, ["academic_year_id", "department_id"], unique=False
    )
    op.create_index("ix_cca_faculty_id", _TBL, ["faculty_id"], unique=False)
