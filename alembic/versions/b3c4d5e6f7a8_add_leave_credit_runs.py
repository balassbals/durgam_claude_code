"""M8.1 TD-036: add leave_credit_runs sidecar table.

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-06-10

Hand-written migration. Creates leave_credit_runs — idempotency sidecar for
credit_annual_cl. One row per (user_id, leave_type, calendar_year). The unique
constraint uq_leave_credit_runs_user_type_year is the idempotency gate.

Note: calendar_year is a plain integer (not ay_id) because CL credit is
calendar-year scoped per §XXVIII clause 14, not academic-year scoped.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: str | Sequence[str] | None = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leave_credit_runs",
        sa.Column("id", sa.dialects.postgresql.UUID(), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(), nullable=False),
        sa.Column("leave_type", sa.String(8), nullable=False),
        sa.Column("calendar_year", sa.Integer(), nullable=False),
        sa.Column("credited_days", sa.Float(), nullable=False),
        sa.Column("policy_id", sa.dialects.postgresql.UUID(), nullable=False),
        sa.Column("ran_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.dialects.postgresql.UUID(), nullable=True),
        sa.Column("updated_by", sa.dialects.postgresql.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.dialects.postgresql.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["policy_id"], ["leave_credit_policies.id"]),
        sa.UniqueConstraint(
            "user_id", "leave_type", "calendar_year",
            name="uq_leave_credit_runs_user_type_year",
        ),
    )
    op.create_index("ix_leave_credit_runs_user", "leave_credit_runs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_leave_credit_runs_user", table_name="leave_credit_runs")
    op.drop_table("leave_credit_runs")
