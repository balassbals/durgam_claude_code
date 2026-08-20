"""
M10 Phase 5A — add faculty_requests table.

Strictly additive. No data shifts. No changes to existing tables.

Forward (upgrade):
1. CREATE TABLE faculty_requests (
     id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     faculty_id          UUID NOT NULL REFERENCES faculties(id) ON DELETE RESTRICT,
     request_type        VARCHAR(64) NOT NULL,
     payload_json        JSONB NULL,
     approval_request_id UUID NULL REFERENCES approval_requests(id) ON DELETE RESTRICT,
     status              VARCHAR(20) NOT NULL DEFAULT 'draft',
     -- TimestampedSoftDelete columns:
     created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
     updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
     created_by          UUID NULL,
     updated_by          UUID NULL,
     is_deleted          BOOLEAN NOT NULL DEFAULT false,
     deleted_at          TIMESTAMPTZ NULL,
     deleted_by          UUID NULL,
     CONSTRAINT ck_faculty_requests_status_enum
       CHECK (status IN ('approved', 'draft', 'rejected', 'submitted', 'withdrawn'))
   );

2. Indexes:
   - ix_faculty_requests_faculty_id (faculty_id) WHERE is_deleted = false
   - ix_faculty_requests_request_type (request_type) WHERE is_deleted = false
   - ix_faculty_requests_status (status) WHERE is_deleted = false
   - ix_faculty_requests_approval_request_id (approval_request_id)
       WHERE is_deleted = false AND approval_request_id IS NOT NULL

Note: request_type is NOT enforced via CHECK or FK — it's a free VARCHAR(64) validated
at the service layer against FACULTY_REQUEST_TYPES. This makes adding new request
types a Python-only change with no schema migration (per architectural commitment
to extensibility — Bala 2026-06-15).

Reverse (downgrade): DROP TABLE faculty_requests (data lost is acceptable — Phase 5A
ships no seed data; Phase 5B/5C ship the first actual records).

Down revision: 4bcc3e4671b8 (Phase 3A approval OR-set schema).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "bfccb3e6d537"
down_revision = "4bcc3e4671b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "faculty_requests",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("faculty_id", sa.UUID(), nullable=False),
        sa.Column("request_type", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("approval_request_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="draft",
        ),
        # TimestampedSoftDelete columns
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["faculty_id"],
            ["faculties.id"],
            name="fk_faculty_requests_faculty",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approval_request_id"],
            ["approval_requests.id"],
            name="fk_faculty_requests_approval_request",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('approved', 'draft', 'rejected', 'submitted', 'withdrawn')",
            name="ck_faculty_requests_status_enum",
        ),
    )
    op.create_index(
        "ix_faculty_requests_faculty_id",
        "faculty_requests",
        ["faculty_id"],
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ix_faculty_requests_request_type",
        "faculty_requests",
        ["request_type"],
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ix_faculty_requests_status",
        "faculty_requests",
        ["status"],
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ix_faculty_requests_approval_request_id",
        "faculty_requests",
        ["approval_request_id"],
        postgresql_where=sa.text(
            "is_deleted = false AND approval_request_id IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_faculty_requests_approval_request_id",
        table_name="faculty_requests",
    )
    op.drop_index(
        "ix_faculty_requests_status",
        table_name="faculty_requests",
    )
    op.drop_index(
        "ix_faculty_requests_request_type",
        table_name="faculty_requests",
    )
    op.drop_index(
        "ix_faculty_requests_faculty_id",
        table_name="faculty_requests",
    )
    op.drop_table("faculty_requests")
