"""cca_faculty_id_backfill

M10 Phase 11A (Q-P11.4 / D-020) — backfill faculty_id on class_coordinator_assignments.
Per-table migration. Sequence: ADD nullable FK + ix → UPDATE map placeholder →
employee_id → faculties.id → ALTER NOT NULL → DROP placeholder. Empty table → step 2
no-op. Reverse restores the placeholder (best-effort) and drops faculty_id.

Revision ID: e4b0c1d8a295
Revises: d3a9b2c7f184
Create Date: 2026-06-21 13:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e4b0c1d8a295"
down_revision: Union[str, Sequence[str], None] = "d3a9b2c7f184"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TBL = "class_coordinator_assignments"


def upgrade() -> None:
    op.add_column(_TBL, sa.Column("faculty_id", sa.Uuid(), nullable=True))
    op.create_index("ix_cca_faculty_id", _TBL, ["faculty_id"])
    op.create_foreign_key(
        "fk_cca_faculty_id", _TBL, "faculties", ["faculty_id"], ["id"]
    )
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
    op.drop_constraint("fk_cca_faculty_id", _TBL, type_="foreignkey")
    op.drop_index("ix_cca_faculty_id", table_name=_TBL)
    op.drop_column(_TBL, "faculty_id")
