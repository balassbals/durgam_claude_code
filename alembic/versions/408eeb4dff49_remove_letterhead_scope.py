"""remove_letterhead_scope

Revision ID: 408eeb4dff49
Revises: d8ed0623c3c7
Create Date: 2026-05-27 21:55:06.312500

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '408eeb4dff49'
down_revision: Union[str, Sequence[str], None] = 'd8ed0623c3c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index('uq_document_templates_letterhead_global', table_name='document_templates', postgresql_where='((scope_type IS NULL) AND (is_deleted = false) AND (role_code IS NOT NULL))')
    op.drop_index('uq_document_templates_letterhead_scoped', table_name='document_templates', postgresql_where='((is_deleted = false) AND (role_code IS NOT NULL))')
    op.drop_column('document_templates', 'scope_type')
    op.drop_column('document_templates', 'scope_id')
    op.create_index('uq_document_templates_letterhead_role', 'document_templates', ['purpose', 'role_code'], unique=True, postgresql_where=sa.text('is_deleted = false AND role_code IS NOT NULL'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_document_templates_letterhead_role', table_name='document_templates', postgresql_where=sa.text('is_deleted = false AND role_code IS NOT NULL'))
    op.add_column('document_templates', sa.Column('scope_id', sa.UUID(), autoincrement=False, nullable=True))
    op.add_column('document_templates', sa.Column('scope_type', sa.VARCHAR(length=32), autoincrement=False, nullable=True))
    op.create_index('uq_document_templates_letterhead_scoped', 'document_templates', ['purpose', 'role_code', 'scope_type', 'scope_id'], unique=True, postgresql_where='((is_deleted = false) AND (role_code IS NOT NULL))')
    op.create_index('uq_document_templates_letterhead_global', 'document_templates', ['purpose', 'role_code'], unique=True, postgresql_where='((scope_type IS NULL) AND (is_deleted = false) AND (role_code IS NOT NULL))')
