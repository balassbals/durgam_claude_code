"""add_faculty_mentor_confirmations

Revision ID: 0fbb76dffe96
Revises: 8b7a27af057f
Create Date: 2026-06-01 06:56:15.951136

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0fbb76dffe96'
down_revision: Union[str, Sequence[str], None] = '8b7a27af057f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- Y1: FacultyMentorConfirmation table ---
    op.create_table('faculty_mentor_confirmations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('updated_by', sa.Uuid(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.Uuid(), nullable=True),
        sa.Column('academic_year_id', sa.Uuid(), nullable=False),
        sa.Column('campus_id', sa.Uuid(), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmed_by_user_id', sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id']),
        sa.ForeignKeyConstraint(['campus_id'], ['campuses.id']),
        sa.ForeignKeyConstraint(['confirmed_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('academic_year_id', 'campus_id', name='uq_fmc_ay_campus'),
    )

    # --- AA1: Rename visiting_faculty → non_regular_faculty ---
    op.rename_table('visiting_faculty', 'non_regular_faculty')
    op.add_column('non_regular_faculty',
        sa.Column('non_regular_type', sa.String(32), nullable=False, server_default='visiting'),
    )
    op.execute("ALTER INDEX ix_vf_department_id RENAME TO ix_nrf_department_id")
    op.execute(
        "ALTER TABLE non_regular_faculty RENAME CONSTRAINT "
        "visiting_faculty_department_id_fkey TO non_regular_faculty_department_id_fkey"
    )
    op.execute(
        "ALTER TABLE non_regular_faculty RENAME CONSTRAINT "
        "visiting_faculty_pkey TO non_regular_faculty_pkey"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # --- AA1 reverse ---
    op.execute(
        "ALTER TABLE non_regular_faculty RENAME CONSTRAINT "
        "non_regular_faculty_pkey TO visiting_faculty_pkey"
    )
    op.execute(
        "ALTER TABLE non_regular_faculty RENAME CONSTRAINT "
        "non_regular_faculty_department_id_fkey TO visiting_faculty_department_id_fkey"
    )
    op.execute("ALTER INDEX ix_nrf_department_id RENAME TO ix_vf_department_id")
    op.drop_column('non_regular_faculty', 'non_regular_type')
    op.rename_table('non_regular_faculty', 'visiting_faculty')

    # --- Y1 reverse ---
    op.drop_table('faculty_mentor_confirmations')
