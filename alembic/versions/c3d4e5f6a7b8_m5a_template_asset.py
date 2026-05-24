"""M5a: create template_assets table with per-type partial unique index.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-24

Hand-written migration. Creates the template_assets table and a partial
unique index on template_type WHERE is_deleted = false — one active
template per type.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "template_assets",
        sa.Column("id", sa.dialects.postgresql.UUID(), nullable=False),
        sa.Column("template_type", sa.String(16), nullable=False),
        sa.Column("file_id", sa.dialects.postgresql.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.dialects.postgresql.UUID(), nullable=True),
        sa.Column("updated_by", sa.dialects.postgresql.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.dialects.postgresql.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["file_id"], ["file_assets.id"]),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_template_assets_type "
        "ON template_assets (template_type) "
        "WHERE is_deleted = false"
    )


def downgrade() -> None:
    op.drop_index("uq_template_assets_type", table_name="template_assets")
    op.drop_table("template_assets")
