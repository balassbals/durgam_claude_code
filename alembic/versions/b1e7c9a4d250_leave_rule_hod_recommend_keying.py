"""leave_rule_hod_recommend_keying

M10 Phase 10B (Q-P10) — designation/employee-type-keyed HoD recommend-via.
Adds four columns to leave_sanction_authority_rules:
  - applicant_designation_codes (jsonb, nullable; NULL = wildcard)
  - applicant_employee_types    (jsonb, nullable; NULL = wildcard)
  - recommend_via_resolver      (varchar, nullable; alt to recommend_via_role_code)
  - requires_optin              (boolean, NOT NULL, server_default false)

Narrowly scoped to leave_sanction_authority_rules only. All additions are
backward-compatible: NULL/false on existing rows preserves prior behaviour.

Revision ID: b1e7c9a4d250
Revises: adfd6670acb9
Create Date: 2026-06-21 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "b1e7c9a4d250"
down_revision: Union[str, Sequence[str], None] = "adfd6670acb9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — add the four HoD-recommend keying columns."""
    op.add_column(
        "leave_sanction_authority_rules",
        sa.Column("applicant_designation_codes", JSONB(), nullable=True),
    )
    op.add_column(
        "leave_sanction_authority_rules",
        sa.Column("applicant_employee_types", JSONB(), nullable=True),
    )
    op.add_column(
        "leave_sanction_authority_rules",
        sa.Column("recommend_via_resolver", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "leave_sanction_authority_rules",
        sa.Column(
            "requires_optin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema — drop the four columns."""
    op.drop_column("leave_sanction_authority_rules", "requires_optin")
    op.drop_column("leave_sanction_authority_rules", "recommend_via_resolver")
    op.drop_column("leave_sanction_authority_rules", "applicant_employee_types")
    op.drop_column("leave_sanction_authority_rules", "applicant_designation_codes")
