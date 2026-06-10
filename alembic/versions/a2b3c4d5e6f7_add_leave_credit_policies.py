"""M8.1 TD-036: add leave_credit_policies table.

Revision ID: a2b3c4d5e6f7
Revises: 1c54065ea5fd
Create Date: 2026-06-10

Hand-written migration. Creates leave_credit_policies — one row per
leave_type defining vacation_entitlement and non_vacation_entitlement.
Seeded with a single CL row via scripts/seed.py.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: str | Sequence[str] | None = "1c54065ea5fd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leave_credit_policies",
        sa.Column("id", sa.dialects.postgresql.UUID(), nullable=False),
        sa.Column("leave_type", sa.String(8), nullable=False),
        sa.Column("vacation_entitlement", sa.Float(), nullable=False),
        sa.Column("non_vacation_entitlement", sa.Float(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.dialects.postgresql.UUID(), nullable=True),
        sa.Column("updated_by", sa.dialects.postgresql.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.dialects.postgresql.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("leave_type", name="uq_leave_credit_policies_leave_type"),
    )


def downgrade() -> None:
    op.drop_table("leave_credit_policies")
