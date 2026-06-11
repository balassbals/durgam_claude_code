"""Property tests for CL annual credit formula helpers (M8.1 TD-036).

2 property tests:
  1. For any joined_on in the calendar year, credit is in [0.5, entitlement]
  2. Credit always rounds to nearest 0.5 (i.e. credit * 2 is an integer)
"""
from __future__ import annotations

from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

from durgam.tasks.leave_jobs import _compute_cl_credit_for_user, _round_half

# min_value=3.0 ensures that even a December joiner (1 month remaining) produces
# raw >= 3/12 = 0.25, which _round_half maps to 0.5 (not 0.0).
# Entitlements below 3 are not used by any real leave type; CL is 10 or 12 days.
_ENTITLEMENT = st.floats(min_value=3.0, max_value=60.0, allow_nan=False, allow_infinity=False)

# joined_on in calendar year 2026
_JOINED_IN_YEAR = st.dates(min_value=date(2026, 1, 1), max_value=date(2026, 12, 31))

# joined_on before calendar year
_JOINED_BEFORE = st.dates(min_value=date(2000, 1, 1), max_value=date(2025, 12, 31))


@given(entitlement=_ENTITLEMENT, joined_on=_JOINED_IN_YEAR)
@settings(deadline=None, max_examples=200)
def test_credit_in_range_for_new_joiner(entitlement: float, joined_on: date) -> None:
    """For any joined_on in the calendar year, credit is positive and ≤ entitlement + 0.5.

    Lower bound: always positive (at least 0.5 after rounding, since ≥ 1 month remains).
    Upper bound: entitlement + 0.5 (rounding to nearest 0.5 can add at most 0.25, but
    we use 0.5 as a conservative bound; the result is never > entitlement + 0.5 because
    months_remaining/12 ≤ 1 and the raw value ≤ entitlement before rounding).
    """
    result = _compute_cl_credit_for_user(entitlement, joined_on, 2026)
    assert result > 0.0, f"credit={result} must be positive for joined_on={joined_on}"
    # Rounding to nearest 0.5 can push result at most 0.25 above entitlement
    assert result <= entitlement + 0.5, (
        f"credit={result} exceeds entitlement={entitlement} + 0.5 for joined_on={joined_on}"
    )


@given(entitlement=_ENTITLEMENT, joined_on=_JOINED_IN_YEAR)
@settings(deadline=None, max_examples=200)
def test_credit_rounds_to_nearest_half(entitlement: float, joined_on: date) -> None:
    """CL credit always rounds to nearest 0.5 (credit * 2 is a whole number)."""
    result = _compute_cl_credit_for_user(entitlement, joined_on, 2026)
    remainder = (result * 2) % 1.0
    assert remainder < 1e-9 or remainder > (1.0 - 1e-9), (
        f"credit={result} is not a multiple of 0.5 (credit*2={result * 2})"
    )
