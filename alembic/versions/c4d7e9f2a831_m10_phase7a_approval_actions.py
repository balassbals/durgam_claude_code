"""m10_phase7a_approval_actions

Adds the approval_actions table for visibility-controlled per-decision action records
(M10 Phase 7A). Each approve/reject decision writes one ApprovalStep row (engine
bookkeeping, unchanged) AND one ApprovalAction row (surfaced to users via visibility
flags: is_visible_to_requestor, visible_to_lower_user_ids_json).

Revision ID: c4d7e9f2a831
Revises: ba82bc8f6ab9
Create Date: 2026-06-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "c4d7e9f2a831"
down_revision = "ba82bc8f6ab9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "approval_actions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("approval_request_id", sa.UUID(), nullable=False),
        sa.Column("stage_index", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=False),
        sa.Column("action_type", sa.String(length=20), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("downward_attachment_file_ids_json", JSONB(), nullable=True),
        sa.Column("is_visible_to_requestor", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("visible_to_lower_user_ids_json", JSONB(), nullable=True),
        # TimestampedSoftDelete columns
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["approval_request_id"],
            ["approval_requests.id"],
            name="fk_approval_actions_approval_request_id",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_approval_actions_actor_user_id",
        ),
        sa.CheckConstraint(
            "action_type IN ('approve', 'reject')",
            name="ck_approval_actions_action_type",
        ),
    )
    op.create_index(
        "ix_approval_actions_request_id",
        "approval_actions",
        ["approval_request_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_approval_actions_request_id", table_name="approval_actions")
    op.drop_table("approval_actions")
