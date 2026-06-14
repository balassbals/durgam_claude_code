"""m9 add publish_delay_seconds to announcement_categories

Revision ID: aa2ce5577e9e
Revises: 442168676909
Create Date: 2026-06-14 06:03:45.872129

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa2ce5577e9e'
down_revision: Union[str, Sequence[str], None] = '442168676909'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'announcement_categories',
        sa.Column('publish_delay_seconds', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('announcement_categories', 'publish_delay_seconds')
