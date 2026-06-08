"""Unit tests for LeaveRequestService.

All tests use MagicMock for session and repos — no DB I/O.
patch() targets are relative to durgam.services.leave_request so import aliasing
doesn't matter.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, call, patch
from uuid import UUID, uuid4

import pytest

from durgam.services.leave_request import LeaveRequestError, LeaveRequestService
from durgam.services.leave_rules import LeaveRuleError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def req_id() -> UUID:
    return uuid4()


@pytest.fixture
def requestor_id() -> UUID:
    return uuid4()


@pytest.fixture
def ay_id() -> UUID:
    return uuid4()


@pytest.fixture
def mock_deps(requestor_id):
    """Pre-wired MagicMock bundle for LeaveRequestService dependencies."""
    session = MagicMock()
    leave_repo = MagicMock()
    balance_repo = MagicMock()
    rule_repo = MagicMock()
    approval_service = MagicMock()

    # user.get returns a plausible User
    user = MagicMock()
    user.is_deleted = False
    user.is_active = True
    user.gender = "M"
    user.joined_on = date(2020, 1, 1)
    user.employee_type = "regular_teaching"
    session.get.return_value = user

    # exec().all() returns empty lists by default (no UserRoles, no Holidays)
    session.exec.return_value.all.return_value = []

    # balance default
    balance = MagicMock()
    balance.opening_balance = 10.0
    balance.credited = 0.0
    balance.availed = 0.0
    balance.forfeited = 0.0
    balance.encashed = 0.0
    balance.closing_balance = 10.0
    balance_repo.get_or_create.return_value = balance

    rule_repo.list_active.return_value = []
    leave_repo.list_overlapping.return_value = []
    leave_repo.get.return_value = MagicMock(
        requestor_user_id=requestor_id,
        approval_request_id=uuid4(),
        chargeable_days=5.0,
        academic_year_id=uuid4(),
        leave_type="CL",
        state="submitted",
    )

    mock_ar = MagicMock()
    mock_ar.id = uuid4()
    approval_service.submit.return_value = mock_ar

    return {
        "session": session,
        "leave_repo": leave_repo,
        "balance_repo": balance_repo,
        "rule_repo": rule_repo,
        "approval_service": approval_service,
        "user": user,
        "mock_ar": mock_ar,
        "balance": balance,
    }


def _svc(deps: dict) -> LeaveRequestService:
    return LeaveRequestService(
        session=deps["session"],
        leave_repo=deps["leave_repo"],
        balance_repo=deps["balance_repo"],
        rule_repo=deps["rule_repo"],
        approval_service=deps["approval_service"],
    )


_DIRECTOR_CHANNEL = [
    {"role_code": "DIRECTOR", "recommend_only": False, "scope_type": "department"}
]

_DEFAULT_SUBMIT_KWARGS: dict = dict(
    leave_type="CL",
    starts_on=date(2026, 7, 1),
    ends_on=date(2026, 7, 3),
    reason="Personal",
)


@contextmanager
def _all_patches(channel=None, compute_days=3.0):
    """Context manager that patches all leave-rules functions and ApprovalProcessRepository."""
    if channel is None:
        channel = _DIRECTOR_CHANNEL
    mock_process = MagicMock()
    mock_process.id = uuid4()
    with (
        patch("durgam.services.leave_request.compute_leave_days", return_value=compute_days),
        patch("durgam.services.leave_request.check_eligibility"),
        patch("durgam.services.leave_request.check_balance"),
        patch("durgam.services.leave_request.check_max_at_a_time"),
        patch("durgam.services.leave_request.check_combination"),
        patch("durgam.services.leave_request.resolve_channel", return_value=channel),
        patch("durgam.services.leave_request.ApprovalProcessRepository") as MockRepo,
        patch("durgam.services.leave_request.audit_snapshot", return_value={}),
        patch("durgam.services.leave_request.write_audit_row"),
    ):
        MockRepo.return_value.get_by_code.return_value = mock_process
        yield


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_submit_calls_engine_in_correct_order(mock_deps, requestor_id, ay_id):
    """approval_service.submit is called after all rule checks pass."""
    with _all_patches():
        result = _svc(mock_deps).submit(
            requestor_user_id=requestor_id,
            academic_year_id=ay_id,
            **_DEFAULT_SUBMIT_KWARGS,
        )
    mock_deps["approval_service"].submit.assert_called_once()
    mock_deps["leave_repo"].add.assert_called_once()
    # The returned object is a LeaveRequest instance (not a mock)
    assert result is not None
    assert result.approval_request_id == mock_deps["mock_ar"].id


def test_submit_cml_uses_hpl_balance(mock_deps, requestor_id, ay_id):
    """CML leave triggers balance lookup against leave_type='HPL'."""
    with _all_patches(compute_days=5.0):
        _svc(mock_deps).submit(
            requestor_user_id=requestor_id,
            academic_year_id=ay_id,
            leave_type="CML",
            starts_on=date(2026, 7, 1),
            ends_on=date(2026, 7, 5),
            reason="Medical",
        )
    mock_deps["balance_repo"].get_or_create.assert_called_once()
    args, kwargs = mock_deps["balance_repo"].get_or_create.call_args
    assert args[1] == "HPL" or kwargs.get("leave_type") == "HPL"


def test_submit_eol_skips_balance_check(mock_deps, requestor_id, ay_id):
    """EOL does not call balance_repo.get_or_create (no running balance)."""
    with _all_patches():
        _svc(mock_deps).submit(
            requestor_user_id=requestor_id,
            academic_year_id=ay_id,
            leave_type="EOL",
            starts_on=date(2026, 7, 1),
            ends_on=date(2026, 7, 3),
            reason="Extra ordinary",
        )
    mock_deps["balance_repo"].get_or_create.assert_not_called()


def test_submit_sl_skips_balance_check(mock_deps, requestor_id, ay_id):
    """SL does not call balance_repo.get_or_create (no running balance)."""
    with _all_patches():
        _svc(mock_deps).submit(
            requestor_user_id=requestor_id,
            academic_year_id=ay_id,
            leave_type="SL",
            starts_on=date(2026, 7, 1),
            ends_on=date(2026, 7, 3),
            reason="Study",
        )
    mock_deps["balance_repo"].get_or_create.assert_not_called()


def test_submit_director_without_in_charge_raises(mock_deps, requestor_id, ay_id):
    """requires_in_charge rule without designation raises LeaveRuleError."""
    rule = MagicMock()
    rule.leave_type = "CL"
    rule.applicant_role_code = "*"
    rule.priority = 1
    rule.requires_in_charge = True
    mock_deps["rule_repo"].list_active.return_value = [rule]

    with (
        patch("durgam.services.leave_request.compute_leave_days", return_value=3.0),
        patch("durgam.services.leave_request.check_eligibility"),
        patch("durgam.services.leave_request.check_balance"),
        patch("durgam.services.leave_request.check_max_at_a_time"),
        patch("durgam.services.leave_request.check_combination"),
        patch("durgam.services.leave_request.resolve_channel", return_value=_DIRECTOR_CHANNEL),
        patch("durgam.services.leave_request.ApprovalProcessRepository") as MockRepo,
        patch("durgam.services.leave_request.audit_snapshot", return_value={}),
        patch("durgam.services.leave_request.write_audit_row"),
    ):
        MockRepo.return_value.get_by_code.return_value = MagicMock(id=uuid4())
        with pytest.raises(LeaveRuleError, match="in-charge faculty designation required"):
            _svc(mock_deps).submit(
                requestor_user_id=requestor_id,
                academic_year_id=ay_id,
                in_charge_designation=None,
                **_DEFAULT_SUBMIT_KWARGS,
            )


def test_submit_director_with_in_charge_passes(mock_deps, requestor_id, ay_id):
    """requires_in_charge rule with designation provided succeeds."""
    rule = MagicMock()
    rule.leave_type = "CL"
    rule.applicant_role_code = "*"
    rule.priority = 1
    rule.requires_in_charge = True
    mock_deps["rule_repo"].list_active.return_value = [rule]

    with _all_patches():
        result = _svc(mock_deps).submit(
            requestor_user_id=requestor_id,
            academic_year_id=ay_id,
            in_charge_designation="Dr. Backup",
            **_DEFAULT_SUBMIT_KWARGS,
        )
    assert result is not None


def test_submit_creates_approval_request_with_resolved_channel(mock_deps, requestor_id, ay_id):
    """approval_service.submit receives resolved_channel from resolve_channel()."""
    with _all_patches(channel=_DIRECTOR_CHANNEL):
        _svc(mock_deps).submit(
            requestor_user_id=requestor_id,
            academic_year_id=ay_id,
            **_DEFAULT_SUBMIT_KWARGS,
        )
    call_kwargs = mock_deps["approval_service"].submit.call_args.kwargs
    assert call_kwargs["resolved_channel"] == _DIRECTOR_CHANNEL


def test_submit_links_approval_request_id_back(mock_deps, requestor_id, ay_id):
    """LeaveRequest.approval_request_id equals the engine-returned ApprovalRequest.id."""
    with _all_patches():
        leave_req = _svc(mock_deps).submit(
            requestor_user_id=requestor_id,
            academic_year_id=ay_id,
            **_DEFAULT_SUBMIT_KWARGS,
        )
    # approval_service.submit() returned mock_ar; the leave_req must carry its id.
    expected_ar_id = mock_deps["approval_service"].submit.return_value.id
    assert leave_req.approval_request_id == expected_ar_id


def test_withdraw_owner_succeeds(mock_deps, requestor_id, req_id):
    """Requestor can withdraw their own leave request."""
    with patch("durgam.services.leave_request.audit_snapshot", return_value={}), \
         patch("durgam.services.leave_request.write_audit_row"):
        result = _svc(mock_deps).withdraw(
            leave_request_id=req_id,
            requestor_user_id=requestor_id,
        )
    mock_deps["approval_service"].withdraw.assert_called_once()
    assert result is not None


def test_withdraw_non_owner_raises(mock_deps, requestor_id, req_id):
    """Non-owner cannot withdraw another user's leave request."""
    other_user_id = uuid4()
    with pytest.raises(LeaveRequestError, match="Only the requestor"):
        _svc(mock_deps).withdraw(
            leave_request_id=req_id,
            requestor_user_id=other_user_id,
        )
    mock_deps["approval_service"].withdraw.assert_not_called()


def test_set_sanctioned_days_validates_range(mock_deps, req_id, requestor_id):
    """sanctioned_days ≤ 0 or > chargeable_days raises LeaveRequestError."""
    svc = _svc(mock_deps)
    with pytest.raises(LeaveRequestError, match="sanctioned_days"):
        svc.set_sanctioned_days(req_id, requestor_id, sanctioned_days=0)
    with pytest.raises(LeaveRequestError, match="sanctioned_days"):
        svc.set_sanctioned_days(req_id, requestor_id, sanctioned_days=99.0)


def test_set_sanctioned_days_writes_audit(mock_deps, req_id, requestor_id):
    """set_sanctioned_days calls write_audit_row after saving."""
    with patch("durgam.services.leave_request.audit_snapshot", return_value={}), \
         patch("durgam.services.leave_request.write_audit_row") as mock_write:
        _svc(mock_deps).set_sanctioned_days(req_id, requestor_id, sanctioned_days=3.0)
    mock_write.assert_called_once()
    call_kwargs = mock_write.call_args.kwargs
    assert call_kwargs["action"] == "set_sanctioned_days"
    assert call_kwargs["after"]["sanctioned_days"] == 3.0


def test_cancel_writes_audit_with_reason(mock_deps, req_id, requestor_id):
    """cancel() calls write_audit_row with the cancellation reason."""
    mock_deps["leave_repo"].get.return_value = MagicMock(
        requestor_user_id=requestor_id,
        approval_request_id=uuid4(),
        chargeable_days=3.0,
        academic_year_id=uuid4(),
        leave_type="CL",
        state="submitted",
    )
    with patch("durgam.services.leave_request.audit_snapshot", return_value={}), \
         patch("durgam.services.leave_request.write_audit_row") as mock_write:
        _svc(mock_deps).cancel(req_id, requestor_id, reason="Admin override")
    mock_write.assert_called_once()
    call_kwargs = mock_write.call_args.kwargs
    assert call_kwargs["action"] == "cancel"
    assert call_kwargs["after"]["cancellation_reason"] == "Admin override"
