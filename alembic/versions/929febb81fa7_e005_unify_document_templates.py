"""E-005: unify letterhead_assets + template_assets into document_templates.

Revision ID: 929febb81fa7
Revises: c3d4e5f6a7b8
Create Date: 2026-05-26 21:01:54.388531

Hand-written migration. Creates document_templates, copies data from both
old tables (letterhead_assets with purpose='letterhead', template_assets
with purpose=template_type), then drops the old tables.

Downgrade reverses: creates old tables, copies data back, drops
document_templates.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

import sqlmodel.sql.sqltypes

revision: str = "929febb81fa7"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create document_templates table
    op.create_table(
        "document_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column(
            "purpose",
            sqlmodel.sql.sqltypes.AutoString(length=16),
            nullable=False,
        ),
        sa.Column(
            "role_code",
            sqlmodel.sql.sqltypes.AutoString(length=64),
            nullable=True,
        ),
        sa.Column(
            "scope_type",
            sqlmodel.sql.sqltypes.AutoString(length=32),
            nullable=True,
        ),
        sa.Column("scope_id", sa.Uuid(), nullable=True),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["file_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_document_templates_letterhead_global",
        "document_templates",
        ["purpose", "role_code"],
        unique=True,
        postgresql_where=sa.text(
            "scope_type IS NULL AND is_deleted = false AND role_code IS NOT NULL"
        ),
    )
    op.create_index(
        "uq_document_templates_letterhead_scoped",
        "document_templates",
        ["purpose", "role_code", "scope_type", "scope_id"],
        unique=True,
        postgresql_where=sa.text(
            "is_deleted = false AND role_code IS NOT NULL"
        ),
    )
    op.create_index(
        "uq_document_templates_type",
        "document_templates",
        ["purpose"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false AND role_code IS NULL"),
    )

    # 2. Copy data from letterhead_assets → document_templates (purpose='letterhead')
    op.execute(
        """
        INSERT INTO document_templates
            (id, created_at, updated_at, created_by, updated_by,
             is_deleted, deleted_at, deleted_by,
             purpose, role_code, scope_type, scope_id, file_id)
        SELECT
            id, created_at, updated_at, created_by, updated_by,
            is_deleted, deleted_at, deleted_by,
            'letterhead', role_code, scope_type, scope_id, file_id
        FROM letterhead_assets
        """
    )

    # 3. Copy data from template_assets → document_templates (purpose=template_type)
    op.execute(
        """
        INSERT INTO document_templates
            (id, created_at, updated_at, created_by, updated_by,
             is_deleted, deleted_at, deleted_by,
             purpose, role_code, scope_type, scope_id, file_id)
        SELECT
            id, created_at, updated_at, created_by, updated_by,
            is_deleted, deleted_at, deleted_by,
            template_type, NULL, NULL, NULL, file_id
        FROM template_assets
        """
    )

    # 4. Drop old tables
    op.drop_index(
        "uq_template_assets_type",
        table_name="template_assets",
    )
    op.drop_table("template_assets")
    op.drop_index(
        "uq_letterhead_assets_global",
        table_name="letterhead_assets",
    )
    op.drop_index(
        "uq_letterhead_assets_scoped",
        table_name="letterhead_assets",
    )
    op.drop_table("letterhead_assets")


def downgrade() -> None:
    # 1. Recreate old tables
    op.create_table(
        "letterhead_assets",
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), autoincrement=False, nullable=True),
        sa.Column("updated_by", sa.UUID(), autoincrement=False, nullable=True),
        sa.Column(
            "is_deleted", sa.BOOLEAN(), autoincrement=False, nullable=False
        ),
        sa.Column(
            "deleted_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column("deleted_by", sa.UUID(), autoincrement=False, nullable=True),
        sa.Column(
            "role_code",
            sa.VARCHAR(length=64),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "scope_type",
            sa.VARCHAR(length=32),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column("scope_id", sa.UUID(), autoincrement=False, nullable=True),
        sa.Column("file_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["file_assets.id"],
            name="letterhead_assets_file_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="letterhead_assets_pkey"),
    )
    op.create_index(
        "uq_letterhead_assets_scoped",
        "letterhead_assets",
        ["role_code", "scope_type", "scope_id"],
        unique=True,
        postgresql_where="(is_deleted = false)",
    )
    op.create_index(
        "uq_letterhead_assets_global",
        "letterhead_assets",
        ["role_code"],
        unique=True,
        postgresql_where="((scope_type IS NULL) AND (is_deleted = false))",
    )

    op.create_table(
        "template_assets",
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "template_type",
            sa.VARCHAR(length=16),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("file_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), autoincrement=False, nullable=True),
        sa.Column("updated_by", sa.UUID(), autoincrement=False, nullable=True),
        sa.Column(
            "is_deleted",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "deleted_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column("deleted_by", sa.UUID(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["file_assets.id"],
            name="template_assets_file_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="template_assets_pkey"),
    )
    op.create_index(
        "uq_template_assets_type",
        "template_assets",
        ["template_type"],
        unique=True,
        postgresql_where="(is_deleted = false)",
    )

    # 2. Copy data back from document_templates → old tables
    op.execute(
        """
        INSERT INTO letterhead_assets
            (id, created_at, updated_at, created_by, updated_by,
             is_deleted, deleted_at, deleted_by,
             role_code, scope_type, scope_id, file_id)
        SELECT
            id, created_at, updated_at, created_by, updated_by,
            is_deleted, deleted_at, deleted_by,
            role_code, scope_type, scope_id, file_id
        FROM document_templates
        WHERE purpose = 'letterhead'
        """
    )
    op.execute(
        """
        INSERT INTO template_assets
            (id, created_at, updated_at, created_by, updated_by,
             is_deleted, deleted_at, deleted_by,
             template_type, file_id)
        SELECT
            id, created_at, updated_at, created_by, updated_by,
            is_deleted, deleted_at, deleted_by,
            purpose, file_id
        FROM document_templates
        WHERE purpose != 'letterhead'
        """
    )

    # 3. Drop document_templates
    op.drop_index(
        "uq_document_templates_type",
        table_name="document_templates",
    )
    op.drop_index(
        "uq_document_templates_letterhead_scoped",
        table_name="document_templates",
    )
    op.drop_index(
        "uq_document_templates_letterhead_global",
        table_name="document_templates",
    )
    op.drop_table("document_templates")
