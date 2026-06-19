"""FacultyRequest — single parametric model for faculty-initiated requests (M10 Phase 5A).

Per Q3 freeze: one table, request_type discriminator + payload_json + optional FK
to ApprovalRequest. Any future request type is added by:
1. Adding a new constant + entry in FACULTY_REQUEST_TYPES
2. Seeding its ApprovalProcess in scripts/seed.py
3. (Optional) Registering new resolvers in approval_resolvers.RESOLVERS

No schema migration required for new request types.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import CheckConstraint, Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from durgam.models.base import TimestampedSoftDelete


# ── Request type registry (extensible at Python level, no migration needed) ──
REQUEST_TYPE_NOC = "noc"
REQUEST_TYPE_INVITED_TALK = "invited_talk"
REQUEST_TYPE_PROFESSIONAL_MEMBERSHIP = "professional_membership"
REQUEST_TYPE_WFH = "wfh"
REQUEST_TYPE_FIELD_VISIT = "field_visit"
REQUEST_TYPE_APC = "apc"
REQUEST_TYPE_TRAVEL = "travel"
REQUEST_TYPE_EXTERNAL_GRANT_PROPOSAL = "external_grant_proposal"

FACULTY_REQUEST_TYPES: frozenset[str] = frozenset({
    REQUEST_TYPE_NOC,
    REQUEST_TYPE_INVITED_TALK,
    REQUEST_TYPE_PROFESSIONAL_MEMBERSHIP,
    REQUEST_TYPE_WFH,
    REQUEST_TYPE_FIELD_VISIT,
    REQUEST_TYPE_APC,
    REQUEST_TYPE_TRAVEL,
    REQUEST_TYPE_EXTERNAL_GRANT_PROPOSAL,
})

# ── Status lifecycle (stable; enforced via DB CHECK constraint) ──
STATUS_DRAFT = "draft"
STATUS_SUBMITTED = "submitted"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_WITHDRAWN = "withdrawn"

FACULTY_REQUEST_STATUSES: frozenset[str] = frozenset({
    STATUS_DRAFT,
    STATUS_SUBMITTED,
    STATUS_APPROVED,
    STATUS_REJECTED,
    STATUS_WITHDRAWN,
})

# Pre-compute sorted list for the CHECK constraint expression.
_SORTED_STATUSES = sorted(FACULTY_REQUEST_STATUSES)


class FacultyRequest(TimestampedSoftDelete, table=True):
    """Faculty-initiated request with type + payload + lifecycle status.

    Phase 5A: model + basic CRUD. Submission to approval workflow added in Phase 5B.
    """

    __tablename__ = "faculty_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in _SORTED_STATUSES) + ")",
            name="ck_faculty_requests_status_enum",
        ),
    )

    faculty_id: UUID = Field(
        sa_column=Column(
            ForeignKey("faculties.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
    )

    # request_type is VARCHAR(64) — NOT enum, NOT FK — so new types add via Python only
    request_type: str = Field(
        sa_column=Column(String(64), nullable=False, index=True),
    )

    payload_json: dict | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )

    approval_request_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            ForeignKey("approval_requests.id", ondelete="RESTRICT"),
            nullable=True,
            index=True,
        ),
    )

    status: str = Field(
        default=STATUS_DRAFT,
        sa_column=Column(
            String(20), nullable=False, server_default=STATUS_DRAFT, index=True
        ),
    )
