"""M10 Phase 5B: add picked_option_ids_json to approval_requests.

Revision ID: e5d2a1c8f094
Revises: bfccb3e6d537
Create Date: 2026-06-15
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5d2a1c8f094"
down_revision: str = "bfccb3e6d537"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "approval_requests",
        sa.Column("picked_option_ids_json", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("approval_requests", "picked_option_ids_json")
