"""
M10 Phase 1B — designation taxonomy expansion (4 legacy → 7 new codes).

Mutates existing data. Soft-delete-only for legacy rows; no hard-delete.

Forward (upgrade):
1. INSERT 7 new Designation rows via raw SQL with ON CONFLICT DO NOTHING
   on uq_designations_code. New codes + ranks:
     ('sr_prof',        'Senior Professor',                          1)
     ('prof',           'Professor',                                 2)
     ('assoc_prof',     'Associate Professor',                       3)
     ('asst_prof_l10',  'Assistant Professor (Academic Level 10)',   4)
     ('asst_prof_l11',  'Assistant Professor (Academic Level 11)',   5)
     ('asst_prof_l12',  'Assistant Professor (Academic Level 12)',   6)
     ('instructor',     'Instructor',                                7)
   Idempotent: re-running the migration on a DB that already has these
   codes is a no-op.

2. Remap PurchaseCommitteeTemplate.eligible_designations (jsonb array) on all
   existing rows. Per-row UPDATE rewrites the array:
     'senior_professor'     -> 'sr_prof'
     'professor'            -> 'prof'
     'associate_professor'  -> 'assoc_prof'
     'assistant_professor'  -> 'asst_prof_l10'  (lowest level, conservative default)
   Conservative-default rationale: legacy 'assistant_professor' rows can be
   manually re-mapped by Registrar to L11/L12 via admin UI (Phase 7 onward).
   Array order is preserved via WITH ORDINALITY.

3. Soft-delete legacy 4 Designation rows:
     UPDATE designations
        SET is_deleted = true, deleted_at = now()
      WHERE code IN ('senior_professor', 'professor',
                     'associate_professor', 'assistant_professor')
        AND is_deleted = false;
   Soft-delete-only per codebase policy; no hard-delete in migration.
   deleted_by is NULL (system migration actor; no user principal available).
   Bala authority: 2026-06-14 (Phase 1B prompt).

Reverse (downgrade):
1. Un-soft-delete the 4 legacy rows (set is_deleted=false, deleted_at=null).
2. Reverse-remap PCT.eligible_designations:
     'sr_prof'        -> 'senior_professor'
     'prof'           -> 'professor'
     'assoc_prof'     -> 'associate_professor'
     'asst_prof_l10'  -> 'assistant_professor'
   asst_prof_l11/l12 do NOT reverse-map (no legacy code for them); downgrade
   leaves these in place and the downgrade is non-lossless for L11/L12 rows.
3. Soft-delete the 7 new rows.

Down revision: f74557aa7d0d (Phase 1A faculty tables).
"""

from datetime import UTC, datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cb2de963f0b8"
down_revision: Union[str, Sequence[str], None] = "f74557aa7d0d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_DESIGNATIONS = [
    ("sr_prof",       "Senior Professor",                        1),
    ("prof",          "Professor",                               2),
    ("assoc_prof",    "Associate Professor",                     3),
    ("asst_prof_l10", "Assistant Professor (Academic Level 10)", 4),
    ("asst_prof_l11", "Assistant Professor (Academic Level 11)", 5),
    ("asst_prof_l12", "Assistant Professor (Academic Level 12)", 6),
    ("instructor",    "Instructor",                              7),
]

_LEGACY_CODES = (
    "senior_professor",
    "professor",
    "associate_professor",
    "assistant_professor",
)

_NEW_CODES = tuple(code for code, _, _ in _NEW_DESIGNATIONS)

# JSONB remap: old code -> new code (forward)
_FORWARD_MAP = {
    "senior_professor":    "sr_prof",
    "professor":           "prof",
    "associate_professor": "assoc_prof",
    "assistant_professor": "asst_prof_l10",
}

# JSONB remap: new code -> old code (reverse)
# asst_prof_l11 and asst_prof_l12 have no legacy equivalent; left unmapped.
_REVERSE_MAP = {v: k for k, v in _FORWARD_MAP.items()}


def _build_jsonb_remap_sql(mapping: dict[str, str]) -> str:
    """Build SQL fragment that remaps JSONB string array elements in-place.

    Uses jsonb_array_elements WITH ORDINALITY to preserve array order.
    Element text extracted via #>> '{}' (strips JSON quotes) for matching.
    Unrecognised elements pass through unchanged.
    """
    cases = "\n                ".join(
        f"WHEN {old!r} THEN to_jsonb({new!r}::text)"
        for old, new in mapping.items()
    )
    return (
        "(\n"
        "        SELECT jsonb_agg(\n"
        "            CASE elem #>> '{}'\n"
        f"                {cases}\n"
        "                ELSE elem\n"
        "            END\n"
        "            ORDER BY ordinality\n"
        "        )\n"
        "        FROM jsonb_array_elements(eligible_designations)\n"
        "             WITH ORDINALITY AS t(elem, ordinality)\n"
        "    )"
    )


def _codes_array_literal(codes: tuple[str, ...]) -> str:
    """Build a PostgreSQL ARRAY literal from a tuple of string codes.

    Example: ('a', 'b') -> "ARRAY['a', 'b']"
    Used instead of bind params because psycopg3 does not support tuple
    binding for SQL IN / = ANY() clauses via sa.text().
    The codes are migration constants, not user input — no injection risk.
    """
    return "ARRAY[" + ", ".join(f"'{c}'" for c in codes) + "]"


def upgrade() -> None:
    """Insert 7 new Designation rows, remap PCT arrays, soft-delete 4 legacy rows."""
    conn = op.get_bind()
    now = datetime.now(UTC)

    # 1. Insert new Designation rows.
    # ON CONFLICT DO UPDATE so re-running (e.g. after a downgrade+upgrade cycle)
    # un-soft-deletes rows that the downgrade soft-deleted.
    for code, name, rank in _NEW_DESIGNATIONS:
        conn.execute(
            sa.text(
                "INSERT INTO designations"
                " (id, created_at, updated_at, is_deleted, code, name, rank)"
                " VALUES (gen_random_uuid(), :now, :now, false, :code, :name, :rank)"
                " ON CONFLICT ON CONSTRAINT uq_designations_code"
                " DO UPDATE SET is_deleted = false, deleted_at = null, updated_at = :now"
            ),
            {"now": now, "code": code, "name": name, "rank": rank},
        )

    # 2. Remap eligible_designations JSONB array.
    remap_sql = _build_jsonb_remap_sql(_FORWARD_MAP)
    conn.execute(
        sa.text(
            f"UPDATE purchase_committee_templates"
            f" SET eligible_designations = {remap_sql}"
            f" WHERE is_deleted = false"
        )
    )

    # 3. Soft-delete legacy Designation rows.
    # Use = ANY(ARRAY[...]) literal — psycopg3 does not support tuple bind params.
    legacy_array = _codes_array_literal(_LEGACY_CODES)
    conn.execute(
        sa.text(
            f"UPDATE designations"
            f" SET is_deleted = true, deleted_at = :now"
            f" WHERE code = ANY({legacy_array}) AND is_deleted = false"
        ),
        {"now": now},
    )


def downgrade() -> None:
    """Reverse: un-soft-delete legacy rows, reverse-remap PCT, soft-delete new rows."""
    conn = op.get_bind()
    now = datetime.now(UTC)

    # 1. Un-soft-delete the 4 legacy Designation rows.
    legacy_array = _codes_array_literal(_LEGACY_CODES)
    conn.execute(
        sa.text(
            f"UPDATE designations"
            f" SET is_deleted = false, deleted_at = null"
            f" WHERE code = ANY({legacy_array})"
        )
    )

    # 2. Reverse-remap eligible_designations (asst_prof_l11/l12 left as-is;
    #    downgrade is non-lossless for rows that used L11/L12 in a live DB).
    remap_sql = _build_jsonb_remap_sql(_REVERSE_MAP)
    conn.execute(
        sa.text(
            f"UPDATE purchase_committee_templates"
            f" SET eligible_designations = {remap_sql}"
            f" WHERE is_deleted = false"
        )
    )

    # 3. Soft-delete the 7 new Designation rows.
    new_array = _codes_array_literal(_NEW_CODES)
    conn.execute(
        sa.text(
            f"UPDATE designations"
            f" SET is_deleted = true, deleted_at = :now"
            f" WHERE code = ANY({new_array}) AND is_deleted = false"
        ),
        {"now": now},
    )
