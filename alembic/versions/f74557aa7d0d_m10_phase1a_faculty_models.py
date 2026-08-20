"""M10 Phase 1A — add Faculty + 5 sub-model tables.

Forward (upgrade):
1. create_table('faculties', ...) — 1:1 with users via user_id unique FK; FKs to
   users, designations, departments, campuses, file_assets (photo); indexes on
   campus_id, department_id, designation_id; unique constraint on employee_id and
   on user_id.
2. create_table('faculty_documents', ...) — FKs to faculties.id and file_assets.id;
   indexes on faculty_id and file_asset_id.
3. create_table('faculty_education', ...) — FK to faculties.id; index on faculty_id.
4. create_table('faculty_experience', ...) — FK to faculties.id; index on faculty_id.
5. create_table('faculty_expertise', ...) — FK to faculties.id; index on faculty_id.
6. create_table('faculty_workload', ...) — FKs to faculties.id and academic_years.id;
   JSONB entries_json column (nullable=False); composite index on
   (faculty_id, academic_year_id, semester).

Reverse (downgrade): drop tables in reverse order (6, 5, 4, 3, 2, 1); indexes are
dropped automatically with their tables. No data loss concern: downgrade is for
migration tests only — soft-delete is the production delete policy.

Spurious diff note: autogenerate detected a FK name difference on non_regular_faculty
(fk_nrf_approval_request_id with ondelete='SET NULL' in DB vs unnamed in model).
This is a pre-existing metadata mismatch; it is NOT part of Phase 1A scope and has
been removed from this migration. The non_regular_faculty table is unchanged.

Down revision: aa2ce5577e9e
Revises: f74557aa7d0d
"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel  # noqa: F401 — ensures AutoString is available
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f74557aa7d0d"
down_revision: Union[str, Sequence[str], None] = "aa2ce5577e9e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Faculty + 5 sub-model tables (M10 Phase 1A)."""
    op.create_table(
        "faculties",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column("first_name", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("middle_name", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column("last_name", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("designation_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("campus_id", sa.Uuid(), nullable=False),
        sa.Column("joining_date", sa.Date(), nullable=False),
        sa.Column("is_vacation_employee", sa.Boolean(), nullable=False),
        sa.Column("phone", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("whatsapp", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=True),
        sa.Column("alt_phone", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=True),
        sa.Column("alt_email", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("photo_file_id", sa.Uuid(), nullable=True),
        sa.Column("emergency_contact_name", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column("emergency_contact_relation", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("emergency_contact_phone", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("is_phd", sa.Boolean(), nullable=False),
        sa.Column("phd_thesis_title", sqlmodel.sql.sqltypes.AutoString(length=512), nullable=True),
        sa.Column("phd_registration_number", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column("phd_awarding_institution", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("phd_year", sa.Integer(), nullable=True),
        sa.Column("orcid", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column("linkedin", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("google_scholar", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("researchgate", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["designation_id"], ["designations.id"]),
        sa.ForeignKeyConstraint(["photo_file_id"], ["file_assets.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", name="uq_faculties_employee_id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_faculties_campus_id", "faculties", ["campus_id"], unique=False)
    op.create_index("ix_faculties_department_id", "faculties", ["department_id"], unique=False)
    op.create_index("ix_faculties_designation_id", "faculties", ["designation_id"], unique=False)

    op.create_table(
        "faculty_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("faculty_id", sa.Uuid(), nullable=False),
        sa.Column("file_asset_id", sa.Uuid(), nullable=False),
        sa.Column("doc_type", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.ForeignKeyConstraint(["faculty_id"], ["faculties.id"]),
        sa.ForeignKeyConstraint(["file_asset_id"], ["file_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_faculty_documents_faculty_id", "faculty_documents", ["faculty_id"], unique=False)
    op.create_index("ix_faculty_documents_file_asset_id", "faculty_documents", ["file_asset_id"], unique=False)

    op.create_table(
        "faculty_education",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("faculty_id", sa.Uuid(), nullable=False),
        sa.Column("degree_name", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column("specialization", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("awarding_institution", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("year_of_award", sa.Integer(), nullable=False),
        sa.Column("distinction", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.ForeignKeyConstraint(["faculty_id"], ["faculties.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_faculty_education_faculty_id", "faculty_education", ["faculty_id"], unique=False)

    op.create_table(
        "faculty_experience",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("faculty_id", sa.Uuid(), nullable=False),
        sa.Column("organization", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("designation_held", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column("from_date", sa.Date(), nullable=False),
        sa.Column("to_date", sa.Date(), nullable=True),
        sa.Column("responsibilities", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["faculty_id"], ["faculties.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_faculty_experience_faculty_id", "faculty_experience", ["faculty_id"], unique=False)

    op.create_table(
        "faculty_expertise",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("faculty_id", sa.Uuid(), nullable=False),
        sa.Column("area", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("proficiency", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
        sa.ForeignKeyConstraint(["faculty_id"], ["faculties.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_faculty_expertise_faculty_id", "faculty_expertise", ["faculty_id"], unique=False)

    op.create_table(
        "faculty_workload",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("faculty_id", sa.Uuid(), nullable=False),
        sa.Column("academic_year_id", sa.Uuid(), nullable=False),
        sa.Column("semester", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column("entries_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"]),
        sa.ForeignKeyConstraint(["faculty_id"], ["faculties.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_faculty_workload_faculty_ay",
        "faculty_workload",
        ["faculty_id", "academic_year_id", "semester"],
        unique=False,
    )


def downgrade() -> None:
    """Drop Faculty + 5 sub-model tables in reverse creation order."""
    op.drop_index("ix_faculty_workload_faculty_ay", table_name="faculty_workload")
    op.drop_table("faculty_workload")
    op.drop_index("ix_faculty_expertise_faculty_id", table_name="faculty_expertise")
    op.drop_table("faculty_expertise")
    op.drop_index("ix_faculty_experience_faculty_id", table_name="faculty_experience")
    op.drop_table("faculty_experience")
    op.drop_index("ix_faculty_education_faculty_id", table_name="faculty_education")
    op.drop_table("faculty_education")
    op.drop_index("ix_faculty_documents_file_asset_id", table_name="faculty_documents")
    op.drop_index("ix_faculty_documents_faculty_id", table_name="faculty_documents")
    op.drop_table("faculty_documents")
    op.drop_index("ix_faculties_designation_id", table_name="faculties")
    op.drop_index("ix_faculties_department_id", table_name="faculties")
    op.drop_index("ix_faculties_campus_id", table_name="faculties")
    op.drop_table("faculties")
