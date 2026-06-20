"""nrf_contract_term_expansion

Adds M10 Phase 9A (D-022) contract-term fields to non_regular_faculty:
  - renewal_count (int, NOT NULL, default 0)
  - latest_contract_file_id (uuid, nullable, FK -> file_assets.id)

Narrowly scoped to the non_regular_faculty table only.

Revision ID: adfd6670acb9
Revises: c4d7e9f2a831
Create Date: 2026-06-20 17:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "adfd6670acb9"
down_revision: Union[str, Sequence[str], None] = "c4d7e9f2a831"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — add the two NRF contract-term columns."""
    # server_default="0" backfills existing rows so the NOT NULL constraint holds.
    op.add_column(
        "non_regular_faculty",
        sa.Column(
            "renewal_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "non_regular_faculty",
        sa.Column("latest_contract_file_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_nrf_latest_contract_file_id",
        "non_regular_faculty",
        "file_assets",
        ["latest_contract_file_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema — drop the two NRF contract-term columns."""
    op.drop_constraint(
        "fk_nrf_latest_contract_file_id",
        "non_regular_faculty",
        type_="foreignkey",
    )
    op.drop_column("non_regular_faculty", "latest_contract_file_id")
    op.drop_column("non_regular_faculty", "renewal_count")
