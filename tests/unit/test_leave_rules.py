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
    applicant_designation_codes: list[str] | None = None,
    applicant_employee_types: list[str] | None = None,
    recommend_via_resolver: str | None = None,
    requires_optin: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        leave_type=leave_type,
        applicant_role_code=applicant_role_code,
        sanctioner_role_code=sanctioner_role_code,
        priority=priority,
        recommend_via_role_code=recommend_via_role_code,
        requires_in_charge=requires_in_charge,
        scope_type=scope_type,
        applicant_designation_codes=applicant_designation_codes,
        applicant_employee_types=applicant_employee_types,
        recommend_via_resolver=recommend_via_resolver,
        requires_optin=requires_optin,
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


def test_check_balance_scl_never_raises() -> None:
    """SCL check never raises even with zero balance (§11.4 management-granted on approval)."""
    bal = SimpleNamespace(leave_type="SCL", closing_balance=0.0)
    check_balance("SCL", 30.0, bal)  # must not raise


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


# ── Phase 10A: HoD recommend-via (STEP-A throwaway proof, Q-P10) ──────────────
# Proves resolve_channel prepends a HoD recommend-only stage when a matrix rule
# sets recommend_via_role_code="HOD". Mechanism is M8-built; this is the Q-P10.4
# STEP-A proof on a throwaway rule. NO live LEAVE_APPROVAL wiring (that is 10B).


def test_resolve_channel_hod_recommend_prepended() -> None:
    rule = _rule(
        "CL", "FACULTY", "DIRECTOR", priority=30,
        recommend_via_role_code="HOD", scope_type="department",
    )
    channel = resolve_channel(["FACULTY"], "CL", [rule])
    assert len(channel) == 2
    assert channel[0]["role_code"] == "HOD"
    assert channel[0]["recommend_only"] is True
    assert channel[1]["role_code"] == "DIRECTOR"
    assert channel[1]["recommend_only"] is False


def test_resolve_channel_hod_recommend_carries_scope_hint() -> None:
    rule = _rule(
        "EL", "FACULTY", "DIRECTOR", priority=30,
        recommend_via_role_code="HOD", scope_type="department",
    )
    channel = resolve_channel(["FACULTY"], "EL", [rule])
    assert channel[0]["scope_type"] == "department"


def test_resolve_channel_hod_recommend_ordering_recommend_before_sanctioner() -> None:
    rule = _rule(
        "HPL", "FACULTY", "DIRECTOR", priority=30, recommend_via_role_code="HOD",
    )
    channel = resolve_channel(["FACULTY"], "HPL", [rule])
    # recommend stage strictly precedes the authoritative sanction stage
    recommend_idx = next(i for i, s in enumerate(channel) if s["recommend_only"])
    sanction_idx = next(i for i, s in enumerate(channel) if not s["recommend_only"])
    assert recommend_idx < sanction_idx


def test_resolve_channel_no_hod_recommend_when_unset_control() -> None:
    # Control: without recommend_via_role_code, no HoD prepend (single sanction stage).
    rule = _rule("CL", "FACULTY", "DIRECTOR", priority=30, recommend_via_role_code=None)
    channel = resolve_channel(["FACULTY"], "CL", [rule])
    assert len(channel) == 1
    assert channel[0]["recommend_only"] is False


# ── Phase 10B: designation/employee_type keying + resolver + opt-in (Q-P10) ───


def test_matcher_designation_codes_matches_only_listed() -> None:
    rule = _rule(
        "CL", "FACULTY", "DIRECTOR", priority=25,
        recommend_via_resolver="dept_head_at_requestor_campus",
        applicant_designation_codes=["asst_prof_l10", "instructor"],
    )
    generic = _rule("CL", "FACULTY", "DIRECTOR", priority=30)
    ch = resolve_channel(
        ["FACULTY"], "CL", [rule, generic],
        applicant_designation_code="asst_prof_l10",
    )
    assert ch[0]["resolver_name"] == "dept_head_at_requestor_campus"
    assert ch[0]["recommend_only"] is True


def test_matcher_designation_codes_non_member_falls_to_generic() -> None:
    rule = _rule(
        "CL", "FACULTY", "DIRECTOR", priority=25,
        recommend_via_resolver="dept_head_at_requestor_campus",
        applicant_designation_codes=["asst_prof_l10"],
    )
    generic = _rule("CL", "FACULTY", "DIRECTOR", priority=30)
    ch = resolve_channel(
        ["FACULTY"], "CL", [rule, generic],
        applicant_designation_code="prof",
    )
    assert len(ch) == 1  # generic only, no HoD prepend
    assert ch[0]["recommend_only"] is False


def test_matcher_employee_types_matches_only_listed() -> None:
    rule = _rule(
        "EL", "FACULTY", "DIRECTOR", priority=26,
        recommend_via_resolver="dept_head_at_requestor_campus",
        applicant_employee_types=["honorary_teaching", "visiting_fellow"],
    )
    generic = _rule("EL", "FACULTY", "DIRECTOR", priority=30)
    ch = resolve_channel(
        ["FACULTY"], "EL", [rule, generic],
        applicant_employee_type="honorary_teaching",
    )
    assert ch[0]["resolver_name"] == "dept_head_at_requestor_campus"


def test_matcher_null_designation_codes_is_wildcard() -> None:
    # Existing rows (no designation/employee_type) match regardless — regression.
    rule = _rule("CL", "FACULTY", "DIRECTOR", priority=30)
    ch = resolve_channel(
        ["FACULTY"], "CL", [rule], applicant_designation_code="anything"
    )
    assert ch[0]["role_code"] == "DIRECTOR"


def test_requires_optin_rule_skipped_when_optin_false() -> None:
    optin_rule = _rule(
        "CL", "FACULTY", "DIRECTOR", priority=27,
        recommend_via_resolver="dept_head_at_requestor_campus",
        applicant_designation_codes=["prof", "assoc_prof", "sr_prof"],
        requires_optin=True,
    )
    generic = _rule("CL", "FACULTY", "DIRECTOR", priority=30)
    ch = resolve_channel(
        ["FACULTY"], "CL", [optin_rule, generic],
        applicant_designation_code="prof", optin=False,
    )
    assert len(ch) == 1  # opt-in rule skipped → generic only
    assert ch[0]["recommend_only"] is False


def test_requires_optin_rule_matches_when_optin_true() -> None:
    optin_rule = _rule(
        "CL", "FACULTY", "DIRECTOR", priority=27,
        recommend_via_resolver="dept_head_at_requestor_campus",
        applicant_designation_codes=["prof", "assoc_prof", "sr_prof"],
        requires_optin=True,
    )
    generic = _rule("CL", "FACULTY", "DIRECTOR", priority=30)
    ch = resolve_channel(
        ["FACULTY"], "CL", [optin_rule, generic],
        applicant_designation_code="prof", optin=True,
    )
    assert ch[0]["resolver_name"] == "dept_head_at_requestor_campus"
    assert ch[0]["recommend_only"] is True


def test_optin_false_rule_matches_regardless_of_optin() -> None:
    # Q-P10.1 rows (requires_optin=False) fire even when optin=False.
    auto_rule = _rule(
        "CL", "FACULTY", "DIRECTOR", priority=25,
        recommend_via_resolver="dept_head_at_requestor_campus",
        applicant_designation_codes=["asst_prof_l10"],
        requires_optin=False,
    )
    ch = resolve_channel(
        ["FACULTY"], "CL", [auto_rule],
        applicant_designation_code="asst_prof_l10", optin=False,
    )
    assert ch[0]["resolver_name"] == "dept_head_at_requestor_campus"


def test_resolver_branch_emits_resolver_role_code_none() -> None:
    rule = _rule(
        "CL", "FACULTY", "DIRECTOR", priority=25,
        recommend_via_resolver="dept_head_at_requestor_campus",
    )
    ch = resolve_channel(["FACULTY"], "CL", [rule])
    assert ch[0]["resolver_name"] == "dept_head_at_requestor_campus"
    assert ch[0]["role_code"] is None


def test_role_code_branch_still_works_regression() -> None:
    # recommend_via_role_code path unchanged; resolver_name is None.
    rule = _rule(
        "SCL", "*", "VC", priority=100, recommend_via_role_code="DIRECTOR",
    )
    ch = resolve_channel(["FACULTY"], "SCL", [rule])
    assert ch[0]["role_code"] == "DIRECTOR"
    assert ch[0]["resolver_name"] is None
    assert ch[0]["recommend_only"] is True


def test_no_duplication_single_rule_wins_by_priority() -> None:
    # asst_prof_l10 WITH optin: designation rule (25) wins; opt-in prof rule (27)
    # doesn't match designation. Single prepend, no duplication.
    desig_rule = _rule(
        "CL", "FACULTY", "DIRECTOR", priority=25,
        recommend_via_resolver="dept_head_at_requestor_campus",
        applicant_designation_codes=["asst_prof_l10"],
    )
    prof_rule = _rule(
        "CL", "FACULTY", "DIRECTOR", priority=27,
        recommend_via_resolver="dept_head_at_requestor_campus",
        applicant_designation_codes=["prof"], requires_optin=True,
    )
    generic = _rule("CL", "FACULTY", "DIRECTOR", priority=30)
    ch = resolve_channel(
        ["FACULTY"], "CL", [desig_rule, prof_rule, generic],
        applicant_designation_code="asst_prof_l10", optin=True,
    )
    assert len([s for s in ch if s["recommend_only"]]) == 1  # exactly one HoD stage
