"""add_is_post_facto_to_leave_requests

Revision ID: b564ec03bd01
Revises: 86508cdab6cf
Create Date: 2026-06-11 04:27:14.185871

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b564ec03bd01'
down_revision: Union[str, Sequence[str], None] = '86508cdab6cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'leave_requests',
        sa.Column('is_post_facto', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )


def downgrade() -> None:
    op.drop_column('leave_requests', 'is_post_facto')
