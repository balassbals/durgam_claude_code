"""M5a: add partial unique indexes to letterhead_assets.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-24

Hand-written migration. Adds two partial unique indexes to the existing
letterhead_assets table — same pattern as RoleEmail (E-004):
  - uq_letterhead_assets_global: one active row per role_code (NULL scope)
  - uq_letterhead_assets_scoped: one active row per (role_code, scope_type, scope_id)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX uq_letterhead_assets_global "
        "ON letterhead_assets (role_code) "
        "WHERE scope_type IS NULL AND is_deleted = false"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_letterhead_assets_scoped "
        "ON letterhead_assets (role_code, scope_type, scope_id) "
        "WHERE is_deleted = false"
    )


def downgrade() -> None:
    op.drop_index("uq_letterhead_assets_scoped", table_name="letterhead_assets")
    op.drop_index("uq_letterhead_assets_global", table_name="letterhead_assets")
