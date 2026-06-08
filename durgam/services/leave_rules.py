"""Pure-Python leave rules engine (M8).

Phase 1 stub: only the vacation-employee helper was implemented.
Phase 3: adds custom exceptions + 6 engine functions.

Layering contract: ZERO imports from durgam.db, durgam.models, or SQLModel.
All DB reads are injected as pre-fetched plain Python values (duck-typed).
Every function is deterministic given the same inputs (pure).

Saturday convention: Saturdays are working days. §XXVIII of SSSIHL Statutes
names only "Sundays and declared holidays" as weekly-off/prefix-suffix eligible.
No Saturday exclusion appears anywhere in §11.2–§11.9 of the RFP.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any


VACATION_EMPLOYEE_TYPES: frozenset[str] = frozenset({
    "regular_teaching",
    "honorary_teaching",
    "superannuated_teaching",
})


def is_vacation_employee(employee_type: str) -> bool:
    """Return True if the employee_type denotes a vacation employee.

    Vacation employees (teachers) get 10 days CL/year; non-vacation employees
    get 12 days CL/year per SSSIHL Statutes §XXVIII clause 14.
    """
    return employee_type in VACATION_EMPLOYEE_TYPES


# ── Custom exceptions ──────────────────────────────────────────────────────────


class LeaveError(Exception):
    """Base for all leave rule errors."""


class LeaveBalanceError(LeaveError):
    """Insufficient leave balance."""


class LeaveEligibilityError(LeaveError):
    """Applicant does not satisfy eligibility for this leave type."""


class LeaveRuleError(LeaveError):
    """Generic leave-rule violation (ceilings, combinations, type-specific rules)."""


class LeaveChannelError(LeaveError):
    """No sanctioning authority configured for this (leave_type, applicant)."""


# ── Rules engine functions ─────────────────────────────────────────────────────


def compute_leave_days(
    starts_on: date,
    ends_on: date,
    leave_type: str,
    half_day: bool,
    half_day_which: str | None,  # 'first' | 'last' | None
    holidays: set[date],
) -> float:
    """Return chargeable leave days for the requested period.

    §11.2 Rule 3 (all types): Sundays and declared holidays at the boundary
    of the leave period may be prefixed/suffixed and are excluded from the leave
    count. Since the caller supplies start/end dates that already incorporate
    this choice, no additional boundary logic is needed here.

    §11.3 (CL): Sundays and declared holidays WITHIN the leave period are NOT
    counted as leave days. Saturday is a working day (not mentioned as weekly-off
    in §XXVIII; SSSIHL follows a 6-day working week).

    Non-CL: Internal holidays count as leave (§11.3 exclusion is CL-specific).
    Internal Sundays are excluded for all leave types (universal weekly off).
    """
    if starts_on > ends_on:
        raise ValueError(
            f"starts_on ({starts_on}) must be <= ends_on ({ends_on})"
        )
    if half_day:
        if leave_type != "CL":
            raise LeaveRuleError(
                "Half-day leave is only available for Casual Leave (CL) (§11.3)"
            )
        if starts_on != ends_on:
            raise LeaveRuleError(
                "Half-day leave requires a single-day date range (starts_on == ends_on)"
            )
        return 0.5

    days = 0.0
    current = starts_on
    while current <= ends_on:
        is_sunday = current.weekday() == 6  # 0=Mon … 6=Sun
        is_holiday = current in holidays
        if leave_type == "CL":
            # §11.3: internal Sundays and holidays are NOT chargeable for CL
            if not is_sunday and not is_holiday:
                days += 1.0
        else:
            # Non-CL: only Sundays are excluded; holidays count as leave days
            if not is_sunday:
                days += 1.0
        current += timedelta(days=1)
    return days


def check_balance(leave_type: str, chargeable_days: float, balance: Any) -> None:
    """Raise LeaveBalanceError if the requested leave would exhaust the balance.

    §11.7 (EOL): no running balance — no check performed.
    §11.9 (SL): a one-time VC grant, not drawn from a running balance — no check.
    §11.6.d (CML): "Whenever CML is granted, twice the days availed are debited
    against HPL due." Caller MUST pass the HPL balance object when leave_type is
    CML. Raises LeaveRuleError if a non-HPL balance is passed. The effective check
    is: HPL closing_balance - (chargeable_days × 2) >= 0.
    All other types: closing_balance - chargeable_days >= 0.
    """
    if leave_type in ("EOL", "SL"):
        return

    if leave_type == "CML":
        bal_type = getattr(balance, "leave_type", None)
        if bal_type != "HPL":
            raise LeaveRuleError(
                "check_balance for CML requires the HPL balance object "
                "(CML debits HPL at 2× rate per §11.6.d). "
                f"Got balance.leave_type={bal_type!r}"
            )
        if balance.closing_balance - (chargeable_days * 2) < 0:
            raise LeaveBalanceError(
                f"Insufficient HPL balance for Commuted Leave: "
                f"HPL closing={balance.closing_balance:.1f}, "
                f"CML requested={chargeable_days:.1f} "
                f"(2× debit={chargeable_days * 2:.1f} days against HPL)"
            )
        return

    if balance.closing_balance - chargeable_days < 0:
        raise LeaveBalanceError(
            f"Insufficient {leave_type} balance: "
            f"closing={balance.closing_balance:.1f}, "
            f"requested={chargeable_days:.1f}"
        )


def check_max_at_a_time(
    leave_type: str,
    chargeable_days: float,
    *,
    total_span_days: int = 0,
    intended_outside_india: bool = False,
    has_medical_cert: bool = False,
    exception_reason: str | None = None,
) -> None:
    """Raise LeaveRuleError if the single-request ceiling is exceeded.

    §11.3 (CL): chargeable_days <= 7 (A2 ceiling 1) AND total_span_days <= 10
    (A2 ceiling 2 — including Sundays/holidays within the span).
    §11.5 (EL): <= 60 days unless: intended_outside_india, has_medical_cert,
    or exception_reason in {'higher_study', 'training'}.
    §11.6.b (CML): <= 60 days at one time.
    §11.7 (EOL): <= 180 days at one time.
    SCL, HPL, ML, SL: no single-request ceiling.
    """
    if leave_type == "CL":
        if chargeable_days > 7:
            raise LeaveRuleError(
                f"Casual Leave chargeable days cannot exceed 7 at a time "
                f"(§11.3); requested {chargeable_days:.1f} chargeable days"
            )
        if total_span_days > 10:
            raise LeaveRuleError(
                f"Casual Leave total span (including Sundays/holidays) cannot exceed "
                f"10 days (§11.3); span={total_span_days} days"
            )
    elif leave_type == "EL":
        if chargeable_days > 60:
            has_exception = (
                intended_outside_india
                or has_medical_cert
                or exception_reason in {"higher_study", "training"}
            )
            if not has_exception:
                raise LeaveRuleError(
                    f"Earned Leave at one time cannot exceed 60 days without a "
                    f"recognised exception (§11.5); requested {chargeable_days:.1f} days. "
                    "Exceptions: intended_outside_india=True, has_medical_cert=True, "
                    "or exception_reason in {'higher_study', 'training'}"
                )
    elif leave_type == "CML":
        if chargeable_days > 60:
            raise LeaveRuleError(
                f"Commuted Leave at one time cannot exceed 60 days (§11.6.b); "
                f"requested {chargeable_days:.1f} days"
            )
    elif leave_type == "EOL":
        if chargeable_days > 180:
            raise LeaveRuleError(
                f"Extraordinary Leave at one time cannot exceed 180 days (§11.7); "
                f"requested {chargeable_days:.1f} days"
            )
    # SCL, HPL, ML, SL: no single-request ceiling; return without raising


def check_combination(leave_type: str, overlapping_requests: list[Any]) -> None:
    """Raise LeaveRuleError if the proposed leave violates combination rules.

    §11.2 Rule 9: Any leave except Casual may be combined with any other kind.
    Equivalently: CL cannot be combined with any other leave type (bidirectional).
    """
    for req in overlapping_requests:
        other_type = req.leave_type
        if leave_type == "CL" and other_type != "CL":
            raise LeaveRuleError(
                "Casual Leave cannot be combined with any other leave type "
                "(§11.2 Rule 9)"
            )
        if leave_type != "CL" and other_type == "CL":
            raise LeaveRuleError(
                "Casual Leave cannot be combined with any other leave type "
                "(§11.2 Rule 9)"
            )


def check_eligibility(
    user_fields: dict,
    leave_type: str,
    chargeable_days: float,
) -> None:
    """Raise LeaveEligibilityError if the user does not qualify for this leave type.

    Always: inactive employees cannot request any leave (§11.2).

    ML (§11.8): available to married women employees with >= 1 year of service.
      - gender must be 'F'.
      - joined_on must be set; service >= 1 year required.

    SL (§11.9): generally admissible to regular teaching staff with >= 5 years service.
      - employee_type must be 'regular_teaching'.
      - joined_on must be set; service >= 5 years required.
      - Age > 45 is 'not ordinarily' admissible per §11.9 — advisory only; NOT
        enforced as a hard block in v1.

    All other types: no additional eligibility checks here. Entitlement-amount
    differences for honorary/superannuated/visiting staff are handled by the
    balance credit job, not at submission time.
    """
    if not user_fields.get("is_active", True):
        raise LeaveEligibilityError("Inactive user cannot request leave")

    if leave_type == "ML":
        if user_fields.get("gender") != "F":
            raise LeaveEligibilityError(
                "Maternity Leave is available only to female employees "
                "(gender field) (§11.8)"
            )
        joined_on: date | None = user_fields.get("joined_on")
        if joined_on is None:
            raise LeaveEligibilityError(
                "joined_on must be set to evaluate ML service-years eligibility"
            )
        service_years = (date.today() - joined_on).days / 365.25
        if service_years < 1:
            raise LeaveEligibilityError(
                f"Maternity Leave requires at least 1 year of service "
                f"(§11.8); service={service_years:.2f} years"
            )

    elif leave_type == "SL":
        if user_fields.get("employee_type") != "regular_teaching":
            raise LeaveEligibilityError(
                "Study Leave generally admissible only to regular teaching staff (§11.9)"
            )
        joined_on = user_fields.get("joined_on")
        if joined_on is None:
            raise LeaveEligibilityError(
                "joined_on must be set to evaluate SL service-years eligibility"
            )
        service_years = (date.today() - joined_on).days / 365.25
        if service_years < 5:
            raise LeaveEligibilityError(
                f"Study Leave requires at least 5 years of service "
                f"(§11.9); service={service_years:.2f} years"
            )
        # Age > 45: advisory per §11.9, not a hard block. Not enforced in v1.


def resolve_channel(
    user_roles: list[str],
    leave_type: str,
    rules: list[Any],  # LeaveSanctionAuthorityRule duck-typed
) -> list[dict]:
    """Return the approval channel for (user_roles, leave_type).

    Each dict in the returned list has:
      role_code: str          — the approver role to route to at this stage
      recommend_only: bool    — True for a recommend-only stage (e.g. Director for SCL)
      scope_type: str | None  — scope hint for the routing lookup

    Algorithm (§11.10, §11.15 sanctioning matrix):
    1. Filter rules matching leave_type == leave_type OR leave_type == '*'.
    2. Filter rules matching applicant_role_code in user_roles OR == '*'.
    3. Sort by priority ASC (lower number = more specific rule wins).
    4. Take first match; raise LeaveChannelError if no match found.
    5. Build channel: if recommend_via_role_code is set, prepend a recommend-only
       stage; then append the sanctioner stage.

    Duck-typed rule attributes used: leave_type, applicant_role_code,
    sanctioner_role_code, recommend_via_role_code, scope_type, priority.
    """
    candidates = [
        r for r in rules
        if (r.leave_type == leave_type or r.leave_type == "*")
        and (r.applicant_role_code in user_roles or r.applicant_role_code == "*")
    ]
    if not candidates:
        raise LeaveChannelError(
            f"No sanctioning authority configured for "
            f"leave_type={leave_type!r}, user_roles={user_roles}"
        )

    rule = sorted(candidates, key=lambda r: r.priority)[0]

    channel: list[dict] = []
    if rule.recommend_via_role_code is not None:
        channel.append({
            "role_code": rule.recommend_via_role_code,
            "recommend_only": True,
            "scope_type": rule.scope_type,
        })
    channel.append({
        "role_code": rule.sanctioner_role_code,
        "recommend_only": False,
        "scope_type": None,
    })
    return channel
