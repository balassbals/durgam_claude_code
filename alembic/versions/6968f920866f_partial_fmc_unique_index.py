"""partial_fmc_unique_index

M10 Phase 11E — replace the full UniqueConstraint on faculty_mentor_confirmations
(academic_year_id, campus_id) with a partial unique index WHERE is_deleted = FALSE.

The full constraint blocked re-confirming a roster after invalidation: soft-deleting
a FacultyMentorConfirmation row left the (ay, campus) pair in the DB, so the next
INSERT from confirm_roster would hit a unique violation.

A partial unique index enforces "at most one ACTIVE confirmation per AY+campus"
while allowing the soft-deleted rows to coexist for audit chain purposes.

upgrade  = drop uq_fmc_ay_campus full constraint + create partial unique index
downgrade = drop partial index + recreate uq_fmc_ay_campus full constraint

Forward + reverse verified on the dev DB.

Revision ID: 6968f920866f
Revises: c9f1a2b3d417
Create Date: 2026-07-01
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6968f920866f'
down_revision: str | Sequence[str] | None = 'c9f1a2b3d417'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Replace full unique constraint with partial unique index."""
    op.drop_constraint('uq_fmc_ay_campus', 'faculty_mentor_confirmations', type_='unique')
    op.execute(
        "CREATE UNIQUE INDEX uq_fmc_ay_campus "
        "ON faculty_mentor_confirmations (academic_year_id, campus_id) "
        "WHERE is_deleted = FALSE"
    )


def downgrade() -> None:
    """Restore full unique constraint."""
    op.execute("DROP INDEX IF EXISTS uq_fmc_ay_campus")
    op.create_unique_constraint(
        'uq_fmc_ay_campus',
        'faculty_mentor_confirmations',
        ['academic_year_id', 'campus_id'],
    )
