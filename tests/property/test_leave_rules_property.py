"""M8 Phase 3: hypothesis property tests for the leave rules engine."""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from hypothesis import given, settings, strategies as st

from durgam.services.leave_rules import (
    LeaveBalanceError,
    LeaveChannelError,
    check_balance,
    compute_leave_days,
    resolve_channel,
)

# ── Strategies ─────────────────────────────────────────────────────────────────

_LEAVE_TYPES = st.sampled_from(["CL", "SCL", "EL", "HPL", "CML", "EOL", "ML", "SL"])
_BALANCE_TYPES = st.sampled_from(["CL", "EL", "HPL"])
_FINITE_FLOAT = st.floats(
    min_value=0.0,
    max_value=400.0,
    allow_nan=False,
    allow_infinity=False,
)
_BALANCE_FLOAT = st.floats(
    min_value=-100.0,
    max_value=300.0,
    allow_nan=False,
    allow_infinity=False,
)


# ── Property 1: EOL check_balance never raises ─────────────────────────────────

@given(days=_FINITE_FLOAT, balance_days=_BALANCE_FLOAT)
@settings(deadline=None, max_examples=100)
def test_eol_check_balance_never_raises(days: float, balance_days: float) -> None:
    """For any (days, balance_days), EOL balance check NEVER raises.

    EOL has no running balance (§11.7); check_balance must always return
    without raising regardless of the balance value.
    """
    bal = SimpleNamespace(leave_type="EOL", closing_balance=balance_days)
    check_balance("EOL", days, bal)  # must not raise


# ── Property 2: SL check_balance never raises ──────────────────────────────────

@given(days=_FINITE_FLOAT, balance_days=_BALANCE_FLOAT)
@settings(deadline=None, max_examples=100)
def test_sl_check_balance_never_raises(days: float, balance_days: float) -> None:
    """For any (days, balance_days), SL balance check NEVER raises.

    SL is a one-time VC grant, not drawn from a running balance (§11.9).
    """
    bal = SimpleNamespace(leave_type="SL", closing_balance=balance_days)
    check_balance("SL", days, bal)  # must not raise


# ── Property 3: check_balance consistent for regular types ─────────────────────

@given(
    balance_days=st.floats(min_value=0.0, max_value=300.0, allow_nan=False, allow_infinity=False),
    request_days=st.floats(min_value=0.5, max_value=300.0, allow_nan=False, allow_infinity=False),
    leave_type=_BALANCE_TYPES,
)
@settings(deadline=None, max_examples=100)
def test_check_balance_consistent(
    balance_days: float, request_days: float, leave_type: str
) -> None:
    """balance >= request → no raise; balance < request → LeaveBalanceError.

    Applies to CL, EL, HPL (the types with simple closing_balance - days check).
    """
    bal = SimpleNamespace(leave_type=leave_type, closing_balance=balance_days)
    if balance_days >= request_days:
        check_balance(leave_type, request_days, bal)  # must not raise
    else:
        with pytest.raises(LeaveBalanceError):
            check_balance(leave_type, request_days, bal)


# ── Property 4: compute_leave_days is always non-negative ─────────────────────

@given(
    start_offset=st.integers(min_value=0, max_value=300),
    duration=st.integers(min_value=1, max_value=90),
    leave_type=_LEAVE_TYPES,
)
@settings(deadline=None, max_examples=100)
def test_compute_leave_days_non_negative(
    start_offset: int, duration: int, leave_type: str
) -> None:
    """compute_leave_days always returns a non-negative float."""
    starts = date(2026, 1, 1) + timedelta(days=start_offset)
    ends = starts + timedelta(days=duration - 1)
    days = compute_leave_days(starts, ends, leave_type, False, None, set())
    assert days >= 0.0


# ── Property 5: compute_leave_days bounded by calendar span ───────────────────

@given(
    start_offset=st.integers(min_value=0, max_value=300),
    duration=st.integers(min_value=1, max_value=90),
    leave_type=_LEAVE_TYPES,
)
@settings(deadline=None, max_examples=100)
def test_compute_leave_days_bounded_by_span(
    start_offset: int, duration: int, leave_type: str
) -> None:
    """compute_leave_days is always <= the calendar span (ends - starts + 1)."""
    starts = date(2026, 1, 1) + timedelta(days=start_offset)
    ends = starts + timedelta(days=duration - 1)
    span = (ends - starts).days + 1
    days = compute_leave_days(starts, ends, leave_type, False, None, set())
    assert days <= span


# ── Property 6: resolve_channel final entry is never recommend_only ────────────

@given(
    user_role=st.sampled_from(["FACULTY", "HOD", "PROFESSOR", "REGISTRAR", "STUDENT"]),
    leave_type=st.sampled_from(["SCL", "EOL"]),  # both have wildcard rules below
)
@settings(deadline=None, max_examples=50)
def test_resolve_channel_final_entry_not_recommend_only(
    user_role: str, leave_type: str
) -> None:
    """For all (role, leave_type) pairs with matching rules, the LAST channel entry
    has recommend_only=False.

    A channel may have a recommend-only stage in position 0 (e.g. SCL via Director),
    but the terminal sanctioner at the end of the channel is never recommend-only.
    """
    rules = [
        SimpleNamespace(
            leave_type="SCL",
            applicant_role_code="*",
            sanctioner_role_code="VC",
            recommend_via_role_code="DIRECTOR",
            scope_type="campus",
            priority=100,
        ),
        SimpleNamespace(
            leave_type="EOL",
            applicant_role_code="*",
            sanctioner_role_code="VC",
            recommend_via_role_code=None,
            scope_type=None,
            priority=100,
        ),
    ]
    channel = resolve_channel([user_role], leave_type, rules)
    assert len(channel) > 0, "channel must be non-empty"
    assert channel[-1]["recommend_only"] is False, (
        f"Last channel entry must not be recommend_only; got {channel}"
    )
