"""M8 Phase 3: unit tests for the leave rules engine.

All stubs use types.SimpleNamespace so the tests remain pure-Python
with zero DB or session dependency.
"""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from durgam.services.leave_rules import (
    VACATION_EMPLOYEE_TYPES,
    LeaveBalanceError,
    LeaveChannelError,
    LeaveEligibilityError,
    LeaveRuleError,
    check_balance,
    check_combination,
    check_eligibility,
    check_max_at_a_time,
    compute_leave_days,
    is_vacation_employee,
    resolve_channel,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _bal(leave_type: str, closing: float) -> SimpleNamespace:
    return SimpleNamespace(leave_type=leave_type, closing_balance=closing)


def _rule(
    leave_type: str,
    applicant_role_code: str,
    sanctioner_role_code: str,
    priority: int = 100,
    recommend_via_role_code: str | None = None,
    requires_in_charge: bool = False,
    scope_type: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        leave_type=leave_type,
        applicant_role_code=applicant_role_code,
        sanctioner_role_code=sanctioner_role_code,
        priority=priority,
        recommend_via_role_code=recommend_via_role_code,
        requires_in_charge=requires_in_charge,
        scope_type=scope_type,
    )


def _user(
    gender: str | None = "M",
    joined_on: date | None = None,
    employee_type: str = "regular_teaching",
    is_active: bool = True,
) -> dict:
    return {
        "gender": gender,
        "joined_on": joined_on,
        "employee_type": employee_type,
        "is_active": is_active,
    }


# Reference Monday 2026-07-06: weekday()=0 (Mon), not a Sunday
_MON = date(2026, 7, 6)   # Monday
_FRI = date(2026, 7, 10)  # Friday
_SUN = date(2026, 7, 12)  # Sunday (weekday 6)
# A 5-day period Mon–Fri (5 working days, no Sundays)
_WEEK = (_MON, _FRI)
# A 7-day period Mon–Sun (6 working days + 1 Sunday)
_MON_SUN = (_MON, date(2026, 7, 12))


# ── compute_leave_days ─────────────────────────────────────────────────────────

def test_compute_leave_days_cl_excludes_internal_holiday() -> None:
    """CL: a holiday falling inside the period is not chargeable (§11.3)."""
    holiday_wed = date(2026, 7, 8)  # Wednesday
    # Mon–Fri with Wed as holiday → 4 chargeable days (Mon, Tue, Thu, Fri)
    days = compute_leave_days(_MON, _FRI, "CL", False, None, {holiday_wed})
    assert days == 4.0


def test_compute_leave_days_cl_excludes_internal_sunday() -> None:
    """CL: Sunday inside the period is not chargeable (§11.3)."""
    # Mon (7/6) to Mon (7/13): 8 calendar days, 1 Sunday (7/12); 7 chargeable
    starts = _MON
    ends = date(2026, 7, 13)  # next Monday
    days = compute_leave_days(starts, ends, "CL", False, None, set())
    assert days == 7.0


def test_compute_leave_days_cl_half_day_returns_0_5() -> None:
    """CL single day with half_day=True returns 0.5 (§11.3)."""
    days = compute_leave_days(_MON, _MON, "CL", True, "first", set())
    assert days == 0.5


def test_compute_leave_days_non_cl_counts_internal_holiday() -> None:
    """Non-CL: internal holiday DOES count as a leave day (§11.3 exclusion is CL-only)."""
    holiday_wed = date(2026, 7, 8)  # Wednesday
    # EL Mon–Fri with Wed holiday → 5 chargeable days (holiday counts)
    days = compute_leave_days(_MON, _FRI, "EL", False, None, {holiday_wed})
    assert days == 5.0


def test_compute_leave_days_non_cl_excludes_internal_sunday() -> None:
    """Non-CL: Sunday inside the period is not chargeable (universal weekly off)."""
    # Mon (7/6) to Mon (7/13): 8 calendar days, 1 Sunday (7/12); 7 chargeable
    starts = _MON
    ends = date(2026, 7, 13)
    days = compute_leave_days(starts, ends, "EL", False, None, set())
    assert days == 7.0


def test_compute_leave_days_starts_after_ends_raises_value_error() -> None:
    """starts_on > ends_on raises ValueError."""
    with pytest.raises(ValueError, match="starts_on"):
        compute_leave_days(_FRI, _MON, "CL", False, None, set())


def test_compute_leave_days_half_day_non_cl_raises() -> None:
    """half_day=True for a non-CL leave type raises LeaveRuleError."""
    with pytest.raises(LeaveRuleError, match="Casual Leave"):
        compute_leave_days(_MON, _MON, "EL", True, "first", set())


def test_compute_leave_days_half_day_multi_day_raises() -> None:
    """half_day=True for a multi-day CL period raises LeaveRuleError."""
    with pytest.raises(LeaveRuleError, match="single-day"):
        compute_leave_days(_MON, _FRI, "CL", True, "first", set())


# ── check_max_at_a_time ────────────────────────────────────────────────────────

def test_check_max_cl_chargeable_7_ok() -> None:
    """CL 7 chargeable days with span <= 10 passes."""
    check_max_at_a_time("CL", 7.0, total_span_days=7)  # no raise


def test_check_max_cl_chargeable_8_raises() -> None:
    """CL 8 chargeable days raises LeaveRuleError (ceiling is 7)."""
    with pytest.raises(LeaveRuleError, match="7"):
        check_max_at_a_time("CL", 8.0, total_span_days=8)


def test_check_max_cl_span_11_raises() -> None:
    """CL 7 chargeable but total span 11 raises (§11.3 second ceiling = 10)."""
    with pytest.raises(LeaveRuleError, match="10"):
        check_max_at_a_time("CL", 7.0, total_span_days=11)


def test_check_max_el_60_ok() -> None:
    """EL 60 days passes without exception flags."""
    check_max_at_a_time("EL", 60.0)  # no raise


def test_check_max_el_61_no_exception_raises() -> None:
    """EL 61 days without any exception flag raises LeaveRuleError."""
    with pytest.raises(LeaveRuleError, match="60"):
        check_max_at_a_time("EL", 61.0)


def test_check_max_el_61_outside_india_ok() -> None:
    """EL 61 days with intended_outside_india=True passes (§11.5)."""
    check_max_at_a_time("EL", 61.0, intended_outside_india=True)  # no raise


def test_check_max_el_61_medical_cert_ok() -> None:
    """EL 61 days with has_medical_cert=True passes (§11.5)."""
    check_max_at_a_time("EL", 61.0, has_medical_cert=True)  # no raise


def test_check_max_el_61_higher_study_ok() -> None:
    """EL 61 days with exception_reason='higher_study' passes (§11.5)."""
    check_max_at_a_time("EL", 61.0, exception_reason="higher_study")  # no raise


def test_check_max_eol_180_ok() -> None:
    """EOL 180 days passes (exactly at ceiling)."""
    check_max_at_a_time("EOL", 180.0)  # no raise


def test_check_max_eol_181_raises() -> None:
    """EOL 181 days raises LeaveRuleError (ceiling is 180 per §11.7)."""
    with pytest.raises(LeaveRuleError, match="180"):
        check_max_at_a_time("EOL", 181.0)


def test_check_max_cml_60_ok() -> None:
    """CML 60 days passes (exactly at ceiling per §11.6.b)."""
    check_max_at_a_time("CML", 60.0)  # no raise


def test_check_max_cml_61_raises() -> None:
    """CML 61 days raises LeaveRuleError (ceiling is 60 per §11.6.b)."""
    with pytest.raises(LeaveRuleError, match="60"):
        check_max_at_a_time("CML", 61.0)


@pytest.mark.parametrize("leave_type", ["SCL", "HPL", "ML", "SL"])
def test_check_max_no_ceiling_types_pass(leave_type: str) -> None:
    """SCL, HPL, ML, SL have no single-request ceiling; any value passes."""
    check_max_at_a_time(leave_type, 999.0)  # no raise


# ── check_balance ──────────────────────────────────────────────────────────────

def test_check_balance_eol_never_raises() -> None:
    """EOL check never raises even with zero balance (§11.7)."""
    check_balance("EOL", 180.0, _bal("EOL", 0.0))  # no raise


def test_check_balance_sl_never_raises() -> None:
    """SL check never raises even with zero balance (§11.9 one-time VC grant)."""
    check_balance("SL", 180.0, _bal("SL", 0.0))  # no raise


def test_check_balance_cml_uses_hpl_balance() -> None:
    """CML debits HPL at 2× rate (§11.6.d): 5 CML days → debit 10 from HPL."""
    hpl = _bal("HPL", 20.0)
    # 5 days CML → 10 HPL debit; 20 - 10 = 10 >= 0 → pass
    check_balance("CML", 5.0, hpl)  # no raise
    # 11 days CML → 22 HPL debit; 20 - 22 < 0 → raise
    with pytest.raises(LeaveBalanceError, match="HPL"):
        check_balance("CML", 11.0, hpl)


def test_check_balance_cml_wrong_balance_type_raises_rule_error() -> None:
    """Passing a non-HPL balance for CML raises LeaveRuleError (§11.6.d guard)."""
    wrong = _bal("CML", 60.0)
    with pytest.raises(LeaveRuleError, match="HPL"):
        check_balance("CML", 5.0, wrong)


def test_check_balance_cl_negative_raises() -> None:
    """CL request exceeding balance raises LeaveBalanceError."""
    with pytest.raises(LeaveBalanceError):
        check_balance("CL", 5.0, _bal("CL", 3.0))


def test_check_balance_cl_exact_zero_ok() -> None:
    """CL request equal to balance passes (closing - requested = 0, not negative)."""
    check_balance("CL", 5.0, _bal("CL", 5.0))  # no raise


# ── check_combination ──────────────────────────────────────────────────────────

def test_check_combination_cl_with_el_raises() -> None:
    """Proposing CL with an existing EL request raises LeaveRuleError (§11.2 Rule 9)."""
    with pytest.raises(LeaveRuleError, match="Casual Leave cannot be combined"):
        check_combination("CL", [SimpleNamespace(leave_type="EL")])


def test_check_combination_el_with_cl_raises() -> None:
    """Proposing EL with an existing CL request raises LeaveRuleError (symmetric)."""
    with pytest.raises(LeaveRuleError, match="Casual Leave cannot be combined"):
        check_combination("EL", [SimpleNamespace(leave_type="CL")])


def test_check_combination_el_with_hpl_ok() -> None:
    """EL combined with HPL is allowed (§11.2 Rule 9 — only CL is restricted)."""
    check_combination("EL", [SimpleNamespace(leave_type="HPL")])  # no raise


def test_check_combination_empty_overlapping_ok() -> None:
    """No overlapping requests: any leave type passes."""
    check_combination("CL", [])  # no raise


# ── check_eligibility ──────────────────────────────────────────────────────────

def test_check_eligibility_ml_male_raises() -> None:
    """ML for a male employee raises LeaveEligibilityError (§11.8)."""
    with pytest.raises(LeaveEligibilityError, match="female"):
        check_eligibility(_user(gender="M"), "ML", 26 * 7)


def test_check_eligibility_ml_short_service_raises() -> None:
    """ML for female with < 1 year service raises LeaveEligibilityError (§11.8)."""
    recent = date.today() - timedelta(days=100)  # ~3.3 months
    with pytest.raises(LeaveEligibilityError, match="1 year"):
        check_eligibility(_user(gender="F", joined_on=recent), "ML", 182)


def test_check_eligibility_ml_no_joined_on_raises() -> None:
    """ML with joined_on=None raises LeaveEligibilityError (cannot compute service)."""
    with pytest.raises(LeaveEligibilityError, match="joined_on"):
        check_eligibility(_user(gender="F", joined_on=None), "ML", 182)


def test_check_eligibility_ml_female_1y_passes() -> None:
    """ML for female with >= 1 year service passes (§11.8)."""
    over_1y = date.today() - timedelta(days=400)  # ~13 months
    check_eligibility(_user(gender="F", joined_on=over_1y), "ML", 182)  # no raise


def test_check_eligibility_sl_non_teaching_raises() -> None:
    """SL for non-teaching employee raises LeaveEligibilityError (§11.9)."""
    over_5y = date.today() - timedelta(days=1920)
    with pytest.raises(LeaveEligibilityError, match="regular teaching"):
        check_eligibility(
            _user(employee_type="regular_non_teaching", joined_on=over_5y),
            "SL",
            365,
        )


def test_check_eligibility_sl_short_service_raises() -> None:
    """SL for teaching staff with < 5 years service raises LeaveEligibilityError."""
    under_5y = date.today() - timedelta(days=1000)  # ~2.7 years
    with pytest.raises(LeaveEligibilityError, match="5 years"):
        check_eligibility(
            _user(employee_type="regular_teaching", joined_on=under_5y),
            "SL",
            365,
        )


def test_check_eligibility_sl_no_joined_on_raises() -> None:
    """SL with joined_on=None raises LeaveEligibilityError."""
    with pytest.raises(LeaveEligibilityError, match="joined_on"):
        check_eligibility(_user(employee_type="regular_teaching", joined_on=None), "SL", 365)


def test_check_eligibility_sl_teaching_5y_passes() -> None:
    """SL for regular teaching staff with >= 5 years service passes (§11.9)."""
    over_5y = date.today() - timedelta(days=1920)  # ~5.25 years
    check_eligibility(
        _user(employee_type="regular_teaching", joined_on=over_5y), "SL", 365
    )  # no raise


def test_check_eligibility_inactive_user_raises() -> None:
    """Inactive employee cannot request any leave."""
    with pytest.raises(LeaveEligibilityError, match="Inactive"):
        check_eligibility(_user(is_active=False), "CL", 1)


# ── resolve_channel ────────────────────────────────────────────────────────────

def test_resolve_channel_scl_has_recommend_stage() -> None:
    """SCL channel: DIRECTOR as recommend-only stage, then VC as sanctioner (§11.10)."""
    rules = [
        _rule("SCL", "*", "VC", priority=100, recommend_via_role_code="DIRECTOR",
              scope_type="campus"),
    ]
    channel = resolve_channel(["FACULTY"], "SCL", rules)
    assert len(channel) == 2
    assert channel[0]["role_code"] == "DIRECTOR"
    assert channel[0]["recommend_only"] is True
    assert channel[0]["scope_type"] == "campus"
    assert channel[1]["role_code"] == "VC"
    assert channel[1]["recommend_only"] is False
    assert channel[1]["scope_type"] is None


def test_resolve_channel_director_requires_in_charge_rule_returned() -> None:
    """DIRECTOR applying CL: matched rule has sanctioner=VC (§11.10).

    The requires_in_charge flag lives on the matched rule (validated by the
    service in Phase 5); the channel dict only carries role_code + recommend_only.
    """
    specific = _rule("CL", "DIRECTOR", "VC", priority=20, requires_in_charge=True)
    wildcard = _rule("CL", "*", "DIRECTOR", priority=50)
    channel = resolve_channel(["DIRECTOR"], "CL", [wildcard, specific])
    # Specific rule (priority=20) beats wildcard (priority=50)
    assert len(channel) == 1
    assert channel[0]["role_code"] == "VC"
    assert channel[0]["recommend_only"] is False


def test_resolve_channel_no_rule_raises() -> None:
    """No matching rule for (user_roles, leave_type) raises LeaveChannelError."""
    rules = [_rule("CL", "FACULTY", "DIRECTOR")]
    with pytest.raises(LeaveChannelError, match="EL"):
        resolve_channel(["FACULTY"], "EL", rules)


def test_resolve_channel_priority_lower_wins() -> None:
    """Lower priority number is more specific and wins over higher (wildcard)."""
    wildcard = _rule("CL", "*", "DIRECTOR", priority=50)
    specific = _rule("CL", "PROFESSOR", "VC", priority=20)
    channel = resolve_channel(["PROFESSOR"], "CL", [wildcard, specific])
    # priority 20 wins → sanctioner is VC
    assert channel[0]["role_code"] == "VC"


def test_resolve_channel_wildcard_leave_type_matches() -> None:
    """A rule with leave_type='*' matches any leave type."""
    rules = [_rule("*", "*", "VC", priority=100)]
    channel = resolve_channel(["STUDENT"], "EOL", rules)
    assert channel[0]["role_code"] == "VC"


def test_resolve_channel_single_stage_no_recommend() -> None:
    """When recommend_via_role_code is None, channel has exactly one entry."""
    rules = [_rule("CL", "FACULTY", "DIRECTOR", priority=30, recommend_via_role_code=None)]
    channel = resolve_channel(["FACULTY"], "CL", rules)
    assert len(channel) == 1
    assert channel[0]["recommend_only"] is False
