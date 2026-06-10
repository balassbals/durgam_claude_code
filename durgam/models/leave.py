"""Leave-module domain models (M8 §3b)."""

from datetime import date, datetime
from typing import Any, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field

from .base import TimestampedSoftDelete

_TIMESTAMPTZ: type[Any] = cast(type[Any], sa.DateTime(timezone=True))


class LeaveBalance(TimestampedSoftDelete, table=True):
    """Per-employee, per-leave-type, per-AY balance snapshot."""

    __tablename__ = "leave_balances"
    __table_args__ = (
        sa.UniqueConstraint(
            "employee_user_id",
            "leave_type",
            "academic_year_id",
            name="uq_leave_balances_user_type_ay",
        ),
        sa.Index("ix_leave_balances_user", "employee_user_id"),
        sa.Index("ix_leave_balances_ay", "academic_year_id"),
    )

    employee_user_id: UUID = Field(foreign_key="users.id", nullable=False)
    leave_type: str = Field(max_length=8, nullable=False)
    # CL | SCL | EL | HPL | CML | EOL | ML | SL
    academic_year_id: UUID = Field(foreign_key="academic_years.id", nullable=False)

    opening_balance: float = Field(default=0.0, nullable=False)
    credited: float = Field(default=0.0, nullable=False)
    availed: float = Field(default=0.0, nullable=False)
    forfeited: float = Field(default=0.0, nullable=False)
    encashed: float = Field(default=0.0, nullable=False)
    closing_balance: float = Field(default=0.0, nullable=False)

    # Idempotency anchor for the periodic EL/HPL credit job
    last_credited_at: datetime | None = Field(
        default=None, sa_type=_TIMESTAMPTZ, nullable=True
    )

    # Idempotency anchor for forfeit_late_cl: list of "YYYY-MM" strings already
    # processed so double-forfeiture is impossible even on re-run.
    forfeiture_applied_for: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


class LeaveRequest(TimestampedSoftDelete, table=True):
    """A single leave application from submission to terminal state."""

    __tablename__ = "leave_requests"
    __table_args__ = (
        sa.UniqueConstraint("approval_request_id", name="uq_leave_requests_approval"),
        sa.Index("ix_leave_requests_requestor", "requestor_user_id"),
        sa.Index("ix_leave_requests_ay", "academic_year_id"),
    )

    requestor_user_id: UUID = Field(foreign_key="users.id", nullable=False)
    academic_year_id: UUID = Field(foreign_key="academic_years.id", nullable=False)
    leave_type: str = Field(max_length=8, nullable=False)

    starts_on: date = Field(nullable=False)
    ends_on: date = Field(nullable=False)
    half_day: bool = Field(default=False, nullable=False)
    half_day_which: str | None = Field(default=None, max_length=5, nullable=True)
    # 'first' | 'last' | None; only relevant when half_day=True

    chargeable_days: float = Field(nullable=False)
    sanctioned_days: float | None = Field(default=None, nullable=True)
    # Set by approver on partial-modify; defaults to chargeable_days on final approval

    reason: str = Field(nullable=False)
    address_during_leave: str | None = Field(default=None, nullable=True)
    headquarters_left: bool = Field(default=False, nullable=False)
    alternate_arrangement: str | None = Field(default=None, nullable=True)
    intended_outside_india: bool = Field(default=False, nullable=False)
    in_charge_designation: str | None = Field(default=None, nullable=True)
    # Required when the applicant is a DIRECTOR (§11.10 Director note)

    state: str = Field(default="submitted", max_length=16, nullable=False)
    # submitted | in_review | approved | rejected | withdrawn | cancelled
    # Mirrors approval_request.state; updated by _finalize_leave_* callbacks

    medical_cert_file_id: UUID | None = Field(
        default=None, foreign_key="file_assets.id", nullable=True
    )
    fitness_cert_file_id: UUID | None = Field(
        default=None, foreign_key="file_assets.id", nullable=True
    )
    bond_file_id: UUID | None = Field(
        default=None, foreign_key="file_assets.id", nullable=True
    )

    approval_request_id: UUID = Field(foreign_key="approval_requests.id", nullable=False)
    cancellation_reason: str | None = Field(default=None, nullable=True)

    overstay_flagged: bool = Field(default=False, nullable=False)
    # Set True by nightly check_overstay job; full EOL auto-creation deferred to M13


class LateAttendanceMarker(TimestampedSoftDelete, table=True):
    """One row per late-attendance occurrence.

    Pre-M13 Attendance Module: populated by HR admin via manual-entry page.
    Post-M13: populated automatically by the Attendance module.
    The forfeit_late_cl Celery job runs against these rows regardless of source.
    """

    __tablename__ = "late_attendance_markers"
    __table_args__ = (
        sa.UniqueConstraint(
            "employee_user_id",
            "occurred_on",
            name="uq_late_attendance_user_date",
        ),
        sa.Index("ix_late_attendance_user", "employee_user_id"),
        sa.Index("ix_late_attendance_date", "occurred_on"),
    )

    employee_user_id: UUID = Field(foreign_key="users.id", nullable=False)
    occurred_on: date = Field(nullable=False)
    recorded_by: UUID = Field(foreign_key="users.id", nullable=False)
    # HR admin who logged this entry
    notes: str | None = Field(default=None, nullable=True)


class LeaveCreditPolicy(TimestampedSoftDelete, table=True):
    """Annual CL credit entitlement policy per leave type (TD-036, M8.1).

    Seed-managed: one active row per leave_type (currently only "CL").
    Editable via /admin/leave/credit-policy; cannot be created/deleted at runtime.
    """

    __tablename__ = "leave_credit_policies"
    __table_args__ = (
        sa.UniqueConstraint("leave_type", name="uq_leave_credit_policies_leave_type"),
    )

    leave_type: str = Field(max_length=8, nullable=False)
    vacation_entitlement: float = Field(nullable=False)
    non_vacation_entitlement: float = Field(nullable=False)
    enabled: bool = Field(default=True, nullable=False)


class LeaveCreditRun(TimestampedSoftDelete, table=True):
    """Idempotency sidecar for credit_annual_cl (TD-036, M8.1).

    One row per (user_id, leave_type, calendar_year) ensures the job is a
    no-op if re-run for the same calendar year.
    """

    __tablename__ = "leave_credit_runs"
    __table_args__ = (
        sa.UniqueConstraint(
            "user_id",
            "leave_type",
            "calendar_year",
            name="uq_leave_credit_runs_user_type_year",
        ),
        sa.Index("ix_leave_credit_runs_user", "user_id"),
    )

    user_id: UUID = Field(foreign_key="users.id", nullable=False)
    leave_type: str = Field(max_length=8, nullable=False)
    calendar_year: int = Field(nullable=False)
    credited_days: float = Field(nullable=False)
    policy_id: UUID = Field(foreign_key="leave_credit_policies.id", nullable=False)
    ran_at: datetime = Field(sa_type=_TIMESTAMPTZ, nullable=False)


class LeaveSanctionAuthorityRule(TimestampedSoftDelete, table=True):
    """Encodes the sanctioning authority matrix (§11.10, §11.15).

    Loaded at first boot from seeds/leave_sanction_matrix.yaml.
    Live-editable by SYSTEM_ADMIN under audit.

    Office-staff routing uses the office role code directly as applicant_role_code
    (e.g. VC_OFFICE → sanctioner VC) — no separate applicant_office_of_code field.
    """

    __tablename__ = "leave_sanction_authority_rules"
    __table_args__ = (
        sa.Index("ix_lsar_leave_type", "leave_type"),
    )

    leave_type: str = Field(max_length=8, nullable=False)
    # CL | SCL | EL | HPL | CML | EOL | ML | SL | * (wildcard for all types)

    applicant_role_code: str = Field(max_length=64, nullable=False)
    # Exact role code or '*' for all roles.
    # Office-staff rules use the office role code directly (e.g. 'VC_OFFICE').

    applicant_designation_regex: str | None = Field(default=None, nullable=True)
    # Optional regex matched against the applicant's designation (pre-M10 stub)

    sanctioner_role_code: str = Field(max_length=64, nullable=False)

    recommend_via_role_code: str | None = Field(default=None, max_length=64, nullable=True)
    # If set, this role is a recommend-only stage preceding the sanctioner.
    # Used for SCL: Director recommends → VC approves.

    requires_in_charge: bool = Field(default=False, nullable=False)
    # True for Director's own leave: form must supply in_charge_designation

    scope_type: str | None = Field(default=None, max_length=16, nullable=True)
    # Scope for the sanctioner lookup: None=universitywide, 'campus', 'school', etc.

    notes: str | None = Field(default=None, nullable=True)

    priority: int = Field(default=100, nullable=False)
    # Lower number = higher priority; specific rules (low priority #) override wildcard
