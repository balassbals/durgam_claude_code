"""
M10 Phase 6 — add attachment config column to approval_processes.

Strictly additive. Existing rows get safe defaults (NULL = no attachments allowed).

Phase 6 design note: The `max_upward_attachments` and `max_attachment_mb` columns
already exist on `approval_processes` (from M7). This migration adds ONLY the
missing MIME whitelist column. The `max_attachment_count` column specified in the
Phase 6 brief was not added because `max_upward_attachments` already covers the
same semantic (upward = requestor → approver attachments for FacultyRequest types).

Forward (upgrade):
1. ALTER TABLE approval_processes
     ADD COLUMN allowed_attachment_mime_types_json JSONB NULL;

   Semantics:
   - allowed_attachment_mime_types_json: JSON list of allowed MIME strings, e.g.
     ["application/pdf", "image/jpeg"]. NULL = no attachments allowed.
     Existing M7/M8 processes (CPC_FUND_RELEASE, DSW_CLEARANCE, etc.) default to NULL
     (no attachments). Opt-in by seed update or future Phase 7+ sys admin UI.
   - max_upward_attachments (existing M7 column): max files per request. 0 = not
     allowed. Used as the count limit for FacultyRequest attachment uploads.
   - max_attachment_mb (existing M7 column): per-file size limit in MB. Already
     DB-driven; no migration needed. faculty_noc already has max_attachment_mb=5.

2. No indexes added — these columns are read during attachment upload validation,
   always via the parent ApprovalProcess record's PK lookup.

Reverse (downgrade): DROP COLUMN. Data loss acceptable — no production attachments
yet for FacultyRequest, and existing M7/M8 attachments don't depend on this column.

Down revision: e5d2a1c8f094 (Phase 5B picked_option_ids_json).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic
revision: str = "ba82bc8f6ab9"
down_revision: str = "e5d2a1c8f094"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "approval_processes",
        sa.Column("allowed_attachment_mime_types_json", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("approval_processes", "allowed_attachment_mime_types_json")
