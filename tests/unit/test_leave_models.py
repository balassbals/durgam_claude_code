"""M8 Phase 2: smoke tests for the four leave domain models."""
from uuid import uuid4

import pytest

from durgam.models.leave import (
    LateAttendanceMarker,
    LeaveBalance,
    LeaveRequest,
    LeaveSanctionAuthorityRule,
)


def test_leave_balance_tablename() -> None:
    assert LeaveBalance.__tablename__ == "leave_balances"


def test_leave_request_tablename() -> None:
    assert LeaveRequest.__tablename__ == "leave_requests"


def test_late_attendance_marker_tablename() -> None:
    assert LateAttendanceMarker.__tablename__ == "late_attendance_markers"


def test_leave_sanction_authority_rule_tablename() -> None:
    assert LeaveSanctionAuthorityRule.__tablename__ == "leave_sanction_authority_rules"


def test_leave_request_overstay_flagged_default() -> None:
    lr = LeaveRequest(
        requestor_user_id=uuid4(),
        academic_year_id=uuid4(),
        leave_type="CL",
        starts_on="2026-07-01",
        ends_on="2026-07-01",
        chargeable_days=1.0,
        reason="Personal work",
        approval_request_id=uuid4(),
    )
    assert lr.overstay_flagged is False


def test_leave_balance_forfeiture_applied_for_default() -> None:
    lb = LeaveBalance(
        employee_user_id=uuid4(),
        leave_type="CL",
        academic_year_id=uuid4(),
    )
    assert lb.forfeiture_applied_for == []


def test_leave_balance_last_credited_at_default() -> None:
    lb = LeaveBalance(
        employee_user_id=uuid4(),
        leave_type="EL",
        academic_year_id=uuid4(),
    )
    assert lb.last_credited_at is None


def test_leave_sanction_authority_rule_requires_in_charge_default() -> None:
    rule = LeaveSanctionAuthorityRule(
        leave_type="CL",
        applicant_role_code="PROFESSOR",
        sanctioner_role_code="VC",
    )
    assert rule.requires_in_charge is False


def test_leave_sanction_authority_rule_priority_default() -> None:
    rule = LeaveSanctionAuthorityRule(
        leave_type="CL",
        applicant_role_code="FACULTY",
        sanctioner_role_code="DIRECTOR",
    )
    assert rule.priority == 100


def test_leave_balance_numeric_field_defaults() -> None:
    lb = LeaveBalance(
        employee_user_id=uuid4(),
        leave_type="HPL",
        academic_year_id=uuid4(),
    )
    assert lb.opening_balance == 0.0
    assert lb.credited == 0.0
    assert lb.availed == 0.0
    assert lb.forfeited == 0.0
    assert lb.encashed == 0.0
    assert lb.closing_balance == 0.0


def test_leave_request_boolean_defaults() -> None:
    lr = LeaveRequest(
        requestor_user_id=uuid4(),
        academic_year_id=uuid4(),
        leave_type="EL",
        starts_on="2026-07-01",
        ends_on="2026-07-05",
        chargeable_days=4.0,
        reason="Rest",
        approval_request_id=uuid4(),
    )
    assert lr.half_day is False
    assert lr.headquarters_left is False
    assert lr.intended_outside_india is False
    assert lr.overstay_flagged is False
    assert lr.state == "submitted"
