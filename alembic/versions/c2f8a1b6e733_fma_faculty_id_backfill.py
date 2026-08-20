"""fma_faculty_id_backfill

M10 Phase 11A (Q-P11.4 / D-020) — backfill faculty_id on faculty_mentor_assignments.
Per-table migration (never bundled). Sequence per D-020:
  1. ADD faculty_id UUID NULL + FK -> faculties.id + ix index
  2. UPDATE rows mapping faculty_id_placeholder -> Faculty.employee_id -> faculties.id
  3. ALTER faculty_id NOT NULL
  4. DROP faculty_id_placeholder

The table is empty in seed + dev DB, so step 2 is a no-op in practice; the UPDATE
is written for correctness against any data. Reverse migration restores the
placeholder column (best-effort: copies employee_id back) and drops faculty_id.

Revision ID: c2f8a1b6e733
Revises: b1e7c9a4d250
Create Date: 2026-06-21 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c2f8a1b6e733"
down_revision: Union[str, Sequence[str], None] = "b1e7c9a4d250"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TBL = "faculty_mentor_assignments"


def upgrade() -> None:
    op.add_column(_TBL, sa.Column("faculty_id", sa.Uuid(), nullable=True))
    op.create_index("ix_fma_faculty_id", _TBL, ["faculty_id"])
    op.create_foreign_key(
        "fk_fma_faculty_id", _TBL, "faculties", ["faculty_id"], ["id"]
    )
    # Map placeholder -> Faculty.employee_id -> faculties.id (no-op on empty table).
    op.execute(
        f"""
        UPDATE {_TBL} AS a
        SET faculty_id = f.id
        FROM faculties f
        WHERE f.employee_id = a.faculty_id_placeholder
          AND f.is_deleted = false
        """
    )
    op.alter_column(_TBL, "faculty_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column(_TBL, "faculty_id_placeholder")


def downgrade() -> None:
    op.add_column(
        _TBL,
        sa.Column("faculty_id_placeholder", sa.String(length=128), nullable=True),
    )
    # Best-effort restore: copy the faculty's employee_id back into the placeholder.
    op.execute(
        f"""
        UPDATE {_TBL} AS a
        SET faculty_id_placeholder = f.employee_id
        FROM faculties f
        WHERE f.id = a.faculty_id
        """
    )
    op.alter_column(
        _TBL, "faculty_id_placeholder", existing_type=sa.String(length=128),
        nullable=False,
    )
    op.drop_constraint("fk_fma_faculty_id", _TBL, type_="foreignkey")
    op.drop_index("ix_fma_faculty_id", table_name=_TBL)
    op.drop_column(_TBL, "faculty_id")
