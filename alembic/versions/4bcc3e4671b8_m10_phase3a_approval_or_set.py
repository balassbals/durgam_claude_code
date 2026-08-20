"""
M10 Phase 3A — approval engine OR-set schema (STEP-A).

Strictly additive. No data shifts. Legacy approval stages and processes are
unchanged; OR-set behaviour is opt-in via presence of approval_stage_options
rows for a (process, stage_index) pair.

HONEST DEVIATION from prompt: The prompt assumed an `approval_stages` table
(with approval_stage_id FK). No such table exists in the codebase; stages are
implicit indices in approval_process.channel_role_codes / resolved_channel_json.
Adaptation:
  - approval_stage_options.approval_process_id FK → approval_processes(id)
  - approval_stage_options.stage_index INTEGER (1-based, matches current_stage)
  - pick_mode stored as stage_pick_modes_json JSONB NULL on approval_processes
    (dict: {"1": "approver", "2": "requestor"}; per-stage, not per-option)

Forward (upgrade):
1. CREATE TABLE approval_stage_options (
     id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     approval_process_id UUID NOT NULL
       REFERENCES approval_processes(id) ON DELETE CASCADE,
     stage_index     INTEGER NOT NULL (1-based; matches ApprovalRequest.current_stage),
     resolver_name   VARCHAR(200) NOT NULL,
     label           VARCHAR(200) NOT NULL,
     sort_order      INTEGER NOT NULL DEFAULT 0,
     -- TimestampedSoftDelete columns:
     created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
     updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
     created_by      UUID NULL,
     updated_by      UUID NULL,
     is_deleted      BOOLEAN NOT NULL DEFAULT false,
     deleted_at      TIMESTAMPTZ NULL,
     deleted_by      UUID NULL
   );
2. CREATE INDEX ix_approval_stage_options_process_stage
     ON approval_stage_options (approval_process_id, stage_index)
     WHERE is_deleted = false;
3. CREATE UNIQUE INDEX uq_approval_stage_options_process_stage_resolver
     ON approval_stage_options (approval_process_id, stage_index, resolver_name)
     WHERE is_deleted = false;
   (Same resolver cannot appear twice on the same stage among active rows.)
4. ALTER TABLE approval_processes
     ADD COLUMN stage_pick_modes_json JSONB NULL;
   Per-stage pick_mode stored as {"1": "approver", "2": "requestor"}.
   NULL = no OR-set stages configured; all legacy behaviour.

Reverse (downgrade):
1. DROP COLUMN approval_processes.stage_pick_modes_json (no data — column added empty).
2. DROP TABLE approval_stage_options (data lost acceptable — no production process
   uses OR-set yet at Phase 3A; Phase 3B+ will populate this table).

Down revision: cb2de963f0b8 (M10 Phase 1B designation expansion).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "4bcc3e4671b8"
down_revision = "cb2de963f0b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "approval_stage_options",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("approval_process_id", sa.UUID(), nullable=False),
        sa.Column("stage_index", sa.Integer(), nullable=False),
        sa.Column("resolver_name", sa.String(200), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["approval_process_id"],
            ["approval_processes.id"],
            name="fk_approval_stage_options_process",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_approval_stage_options_process_stage",
        "approval_stage_options",
        ["approval_process_id", "stage_index"],
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "uq_approval_stage_options_process_stage_resolver",
        "approval_stage_options",
        ["approval_process_id", "stage_index", "resolver_name"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.add_column(
        "approval_processes",
        sa.Column("stage_pick_modes_json", sa.dialects.postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("approval_processes", "stage_pick_modes_json")
    op.drop_table("approval_stage_options")
