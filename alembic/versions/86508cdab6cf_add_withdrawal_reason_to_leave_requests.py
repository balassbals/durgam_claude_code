"""M8.1 E-017: add withdrawal_reason to leave_requests.

Adds a nullable VARCHAR(1000) column to store the admin-supplied or
requestor-supplied reason when withdrawing an already-approved leave request.
The column is NULL for pre-approval withdrawals (M8-frozen path).

Revision ID: 86508cdab6cf
Revises: b3c4d5e6f7a8
Create Date: 2026-06-10

Hand-written migration (autogenerate had a false-positive FK rename on
non_regular_faculty that is a no-op). Only the withdrawal_reason column is added.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '86508cdab6cf'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'leave_requests',
        sa.Column('withdrawal_reason', sa.String(length=1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('leave_requests', 'withdrawal_reason')
