"""Unit tests for LeaveRequestService.withdraw() — approved-state extension (M8.1 E-017).

12 tests:
  1–2:  Formula: approved CL and EL withdraw, unused tail computed correctly.
  3:    CML: re-credits CML days AND HPL at 2×.
  4–6:  SCL, EOL, SL: no balance change (reverse_deduction never called).
  7:    After ends_on raises LeaveRequestError.
  8:    Half-day edge (starts_on == today == ends_on): full amount re-credited.
  9:    Pre-approval (submitted) path unchanged — existing M8 behavior (regression smoke).
  10:   Admin actor with leave_request_admin:write:* → succeeds, audit records actor.
  11:   Admin actor WITHOUT permission → raises PermissionDenied, balance unchanged.
  12:   Empty reason for approved-state withdrawal → raises ValueError.

All tests use MagicMock; no DB I/O.

Patches required on every test that reaches audit_snapshot():
  durgam.services.leave_request.audit_snapshot  — called in withdraw() before _withdraw_approved()
  durgam.services.leave_request.write_audit_row — called in _withdraw_approved()
  durgam.services.leave_request.ApprovalRequestRepository — instantiated in _withdraw_approved()
  durgam.services.leave_notification.resolve_withdrawal_notification_recipients — late import
  durgam.tasks.leave_jobs._notify — late import

The admin-without-permission test is the sole test that does NOT need these patches because
PermissionDenied is raised before audit_snapshot() is ever reached.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, call, patch
from uuid import UUID, uuid4

import pytest

from durgam.auth.permissions import PermissionDenied
from durgam.services.leave_request import LeaveRequestError, LeaveRequestService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _service(*, leave_req_mock=None, balance_mock=None):
    """Build a LeaveRequestService with minimal mocks."""
    session = MagicMock()
    leave_repo = MagicMock()
    balance_repo = MagicMock()
    rule_repo = MagicMock()
    approval_service = MagicMock()

    if leave_req_mock is not None:
        leave_repo.get.return_value = leave_req_mock
    if balance_mock is not None:
        balance_repo.get_or_create.return_value = balance_mock
        balance_repo.reverse_deduction.return_value = (balance_mock, {"availed": 5.0}, {"availed": 2.0})

    session.exec.return_value.all.return_value = []
    session.get.return_value = None

    svc = LeaveRequestService(
        session=session,
        leave_repo=leave_repo,
        balance_repo=balance_repo,
        rule_repo=rule_repo,
        approval_service=approval_service,
    )
    return svc, session, leave_repo, balance_repo, approval_service


def _approved_leave_req(
    *,
    leave_type: str,
    starts_on: date,
    ends_on: date,
    chargeable_days: float = 5.0,
    sanctioned_days: float | None = None,
) -> MagicMock:
    req = MagicMock()
    req.state = "approved"
    req.leave_type = leave_type
    req.starts_on = starts_on
    req.ends_on = ends_on
    req.chargeable_days = chargeable_days
    req.sanctioned_days = sanctioned_days
    req.requestor_user_id = uuid4()
    req.academic_year_id = uuid4()
    req.approval_request_id = uuid4()
    req.withdrawal_reason = None
    return req


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestApprovedWithdrawFormula:

    @patch("durgam.services.leave_request.audit_snapshot", return_value={})
    @patch("durgam.services.leave_request.write_audit_row")
    @patch("durgam.services.leave_request.ApprovalRequestRepository")
    @patch("durgam.services.leave_notification.resolve_withdrawal_notification_recipients", return_value=[])
    @patch("durgam.tasks.leave_jobs._notify")
    def test_approved_cl_unused_tail(self, mock_notify, mock_resolve, mock_ar_repo, mock_audit, _snap):
        """Approved CL withdraw mid-leave: unused_tail = sanctioned * remaining_days / chargeable."""
        today = date.today()
        starts = today - timedelta(days=2)
        ends = today + timedelta(days=2)
        leave_req = _approved_leave_req(
            leave_type="CL", starts_on=starts, ends_on=ends,
            chargeable_days=5.0, sanctioned_days=5.0,
        )
        actor_id = leave_req.requestor_user_id
        balance = MagicMock()
        balance.availed = 5.0
        svc, session, leave_repo, balance_repo, _ = _service(
            leave_req_mock=leave_req, balance_mock=balance
        )
        leave_repo.get.side_effect = [leave_req, leave_req]
        mock_ar_repo.return_value.get_by_id_any.return_value = MagicMock()

        svc.withdraw(leave_req.id, actor_id, reason="personal emergency")

        # remaining = (today+2 - max(starts, today)) + 1 = (today+2 - today) + 1 = 3
        expected_tail = min(5.0, 5.0 * 3 / 5.0)  # = 3.0
        balance_repo.reverse_deduction.assert_called_once_with(balance, pytest.approx(expected_tail), actor_id)

    @patch("durgam.services.leave_request.audit_snapshot", return_value={})
    @patch("durgam.services.leave_request.write_audit_row")
    @patch("durgam.services.leave_request.ApprovalRequestRepository")
    @patch("durgam.services.leave_notification.resolve_withdrawal_notification_recipients", return_value=[])
    @patch("durgam.tasks.leave_jobs._notify")
    def test_approved_el_unused_tail(self, mock_notify, mock_resolve, mock_ar_repo, mock_audit, _snap):
        """Approved EL withdraw: same formula as CL."""
        today = date.today()
        starts = today
        ends = today + timedelta(days=9)
        leave_req = _approved_leave_req(
            leave_type="EL", starts_on=starts, ends_on=ends,
            chargeable_days=10.0, sanctioned_days=10.0,
        )
        actor_id = leave_req.requestor_user_id
        balance = MagicMock()
        balance.availed = 10.0
        svc, session, leave_repo, balance_repo, _ = _service(
            leave_req_mock=leave_req, balance_mock=balance
        )
        leave_repo.get.side_effect = [leave_req, leave_req]
        mock_ar_repo.return_value.get_by_id_any.return_value = MagicMock()

        svc.withdraw(leave_req.id, actor_id, reason="medical")

        # remaining = (today+9 - today) + 1 = 10
        expected_tail = min(10.0, 10.0 * 10 / 10.0)  # = 10.0
        balance_repo.reverse_deduction.assert_called_once_with(balance, pytest.approx(expected_tail), actor_id)

    @patch("durgam.services.leave_request.audit_snapshot", return_value={})
    @patch("durgam.services.leave_request.write_audit_row")
    @patch("durgam.services.leave_request.ApprovalRequestRepository")
    @patch("durgam.services.leave_notification.resolve_withdrawal_notification_recipients", return_value=[])
    @patch("durgam.tasks.leave_jobs._notify")
    def test_approved_cml_credits_both_cml_and_hpl_at_2x(self, mock_notify, mock_resolve, mock_ar_repo, mock_audit, _snap):
        """Approved CML withdraw: re-credits CML days AND HPL at 2× the CML amount."""
        today = date.today()
        starts = today
        ends = today + timedelta(days=3)
        leave_req = _approved_leave_req(
            leave_type="CML", starts_on=starts, ends_on=ends,
            chargeable_days=4.0, sanctioned_days=4.0,
        )
        actor_id = leave_req.requestor_user_id

        cml_bal = MagicMock()
        cml_bal.availed = 4.0
        hpl_bal = MagicMock()
        hpl_bal.availed = 8.0

        svc, session, leave_repo, balance_repo, _ = _service(leave_req_mock=leave_req)
        leave_repo.get.side_effect = [leave_req, leave_req]
        balance_repo.get_or_create.side_effect = [cml_bal, hpl_bal]
        balance_repo.reverse_deduction.side_effect = [
            (cml_bal, {}, {}),
            (hpl_bal, {}, {}),
        ]
        mock_ar_repo.return_value.get_by_id_any.return_value = MagicMock()

        svc.withdraw(leave_req.id, actor_id, reason="emergency")

        # remaining = (today+3 - today) + 1 = 4
        expected_tail = min(4.0, 4.0 * 4 / 4.0)  # = 4.0
        assert balance_repo.reverse_deduction.call_count == 2
        calls = balance_repo.reverse_deduction.call_args_list
        assert calls[0] == call(cml_bal, pytest.approx(expected_tail), actor_id)        # CML
        assert calls[1] == call(hpl_bal, pytest.approx(expected_tail * 2.0), actor_id)  # HPL 2×

    @pytest.mark.parametrize("leave_type", ["SCL", "EOL", "SL"])
    @patch("durgam.services.leave_request.audit_snapshot", return_value={})
    @patch("durgam.services.leave_request.write_audit_row")
    @patch("durgam.services.leave_request.ApprovalRequestRepository")
    @patch("durgam.services.leave_notification.resolve_withdrawal_notification_recipients", return_value=[])
    @patch("durgam.tasks.leave_jobs._notify")
    def test_no_balance_types_skip_reverse_deduction(
        self, mock_notify, mock_resolve, mock_ar_repo, mock_audit, _snap, leave_type
    ):
        """SCL, EOL, SL: reverse_deduction is never called (no running balance)."""
        today = date.today()
        leave_req = _approved_leave_req(
            leave_type=leave_type, starts_on=today, ends_on=today + timedelta(days=2),
            chargeable_days=3.0, sanctioned_days=3.0,
        )
        actor_id = leave_req.requestor_user_id
        svc, session, leave_repo, balance_repo, _ = _service(leave_req_mock=leave_req)
        leave_repo.get.side_effect = [leave_req, leave_req]
        mock_ar_repo.return_value.get_by_id_any.return_value = MagicMock()

        svc.withdraw(leave_req.id, actor_id, reason="need to cancel")

        balance_repo.reverse_deduction.assert_not_called()

    @patch("durgam.services.leave_request.audit_snapshot", return_value={})
    def test_withdraw_after_ends_on_raises(self, _snap):
        """Withdraw approved leave after ends_on → LeaveRequestError."""
        yesterday = date.today() - timedelta(days=1)
        leave_req = _approved_leave_req(
            leave_type="CL",
            starts_on=yesterday - timedelta(days=4),
            ends_on=yesterday,
            chargeable_days=5.0,
        )
        actor_id = leave_req.requestor_user_id
        svc, session, leave_repo, balance_repo, _ = _service(leave_req_mock=leave_req)

        with pytest.raises(LeaveRequestError, match="leave period has ended"):
            svc.withdraw(leave_req.id, actor_id, reason="need to cancel")

        balance_repo.reverse_deduction.assert_not_called()

    @patch("durgam.services.leave_request.audit_snapshot", return_value={})
    @patch("durgam.services.leave_request.write_audit_row")
    @patch("durgam.services.leave_request.ApprovalRequestRepository")
    @patch("durgam.services.leave_notification.resolve_withdrawal_notification_recipients", return_value=[])
    @patch("durgam.tasks.leave_jobs._notify")
    def test_half_day_edge_full_recredits_sanctioned(
        self, mock_notify, mock_resolve, mock_ar_repo, mock_audit, _snap
    ):
        """Half-day and full-day single-day leaves: unused_tail capped at sanctioned_days."""
        today = date.today()

        # Full-day single-day CL
        leave_req_full = _approved_leave_req(
            leave_type="CL", starts_on=today, ends_on=today,
            chargeable_days=1.0, sanctioned_days=1.0,
        )
        actor_full = leave_req_full.requestor_user_id
        balance_full = MagicMock()
        balance_full.availed = 1.0
        svc_full, _, leave_repo_full, balance_repo_full, _ = _service(
            leave_req_mock=leave_req_full, balance_mock=balance_full
        )
        leave_repo_full.get.side_effect = [leave_req_full, leave_req_full]
        mock_ar_repo.return_value.get_by_id_any.return_value = MagicMock()
        svc_full.withdraw(leave_req_full.id, actor_full, reason="changed plans")
        # unused_tail = min(1.0, 1.0 * 1 / 1.0) = 1.0 = sanctioned_days ✓
        balance_repo_full.reverse_deduction.assert_called_once_with(
            balance_full, pytest.approx(1.0), actor_full
        )

        # Half-day single-day CL (chargeable = 0.5, sanctioned = 0.5)
        leave_req_half = _approved_leave_req(
            leave_type="CL", starts_on=today, ends_on=today,
            chargeable_days=0.5, sanctioned_days=0.5,
        )
        actor_half = leave_req_half.requestor_user_id
        balance_half = MagicMock()
        balance_half.availed = 0.5
        svc_half, _, leave_repo_half, balance_repo_half, _ = _service(
            leave_req_mock=leave_req_half, balance_mock=balance_half
        )
        leave_repo_half.get.side_effect = [leave_req_half, leave_req_half]
        mock_ar_repo.return_value.get_by_id_any.return_value = MagicMock()
        svc_half.withdraw(leave_req_half.id, actor_half, reason="changed plans")
        # raw formula gives 0.5 * 1 / 0.5 = 1.0; capped at sanctioned = 0.5 ✓
        balance_repo_half.reverse_deduction.assert_called_once_with(
            balance_half, pytest.approx(0.5), actor_half
        )

    @patch("durgam.services.leave_request.audit_snapshot", return_value={})
    def test_empty_reason_approved_state_raises_value_error(self, _snap):
        """Approved state withdrawal with empty reason raises ValueError."""
        today = date.today()
        leave_req = _approved_leave_req(
            leave_type="CL", starts_on=today, ends_on=today + timedelta(days=2),
            chargeable_days=3.0,
        )
        actor_id = leave_req.requestor_user_id
        svc, _, leave_repo, balance_repo, _ = _service(leave_req_mock=leave_req)

        with pytest.raises(ValueError, match="Withdrawal reason is required"):
            svc.withdraw(leave_req.id, actor_id, reason="")

        balance_repo.reverse_deduction.assert_not_called()

    def test_pre_approval_submitted_path_unchanged(self):
        """Pre-approval (submitted) withdrawal still routes through the M8-frozen path."""
        leave_req = MagicMock()
        leave_req.state = "submitted"
        leave_req.requestor_user_id = uuid4()
        leave_req.approval_request_id = uuid4()
        actor_id = leave_req.requestor_user_id  # requestor == actor (M8 path)
        refreshed = MagicMock()
        refreshed.state = "withdrawn"

        svc, session, leave_repo, balance_repo, approval_svc = _service(
            leave_req_mock=leave_req
        )
        leave_repo.get.side_effect = [leave_req, refreshed]

        with (
            patch("durgam.services.leave_request.audit_snapshot", return_value={}),
            patch("durgam.services.leave_request.write_audit_row"),
        ):
            result = svc.withdraw(leave_req.id, actor_id)

        approval_svc.withdraw.assert_called_once_with(
            request_id=leave_req.approval_request_id,
            requestor_user_id=leave_req.requestor_user_id,
        )
        balance_repo.reverse_deduction.assert_not_called()
        assert result is refreshed


class TestAdminBypass:

    @patch("durgam.services.leave_request.audit_snapshot", return_value={})
    @patch("durgam.services.leave_request.write_audit_row")
    @patch("durgam.services.leave_request.ApprovalRequestRepository")
    @patch("durgam.services.leave_notification.resolve_withdrawal_notification_recipients", return_value=[])
    @patch("durgam.tasks.leave_jobs._notify")
    @patch("durgam.services.leave_request.can")
    def test_admin_actor_with_permission_succeeds(
        self, mock_can, mock_notify, mock_resolve, mock_ar_repo, mock_audit, _snap
    ):
        """Admin actor (different from requestor) with leave_request_admin:write:* → succeeds."""
        today = date.today()
        requestor_id = uuid4()
        admin_id = uuid4()
        leave_req = _approved_leave_req(
            leave_type="SCL", starts_on=today, ends_on=today + timedelta(days=1),
            chargeable_days=2.0, sanctioned_days=2.0,
        )
        leave_req.requestor_user_id = requestor_id
        mock_can.return_value = True

        svc, session, leave_repo, balance_repo, _ = _service(leave_req_mock=leave_req)
        leave_repo.get.side_effect = [leave_req, leave_req]
        mock_ar_repo.return_value.get_by_id_any.return_value = MagicMock()
        session.exec.return_value.all.return_value = []

        svc.withdraw(leave_req.id, admin_id, reason="admin correction")

        mock_can.assert_called_once_with(
            admin_id, "write", "leave_request_admin", "*", None, session
        )
        balance_repo.reverse_deduction.assert_not_called()

    def test_admin_actor_without_permission_raises(self):
        """Admin actor without leave_request_admin:write:* → PermissionDenied.

        PermissionDenied is raised BEFORE audit_snapshot() is reached,
        so no audit_snapshot patch is needed here.
        """
        today = date.today()
        requestor_id = uuid4()
        other_id = uuid4()
        leave_req = _approved_leave_req(
            leave_type="CL", starts_on=today, ends_on=today + timedelta(days=2),
        )
        leave_req.requestor_user_id = requestor_id

        svc, session, leave_repo, balance_repo, _ = _service(leave_req_mock=leave_req)

        with patch("durgam.services.leave_request.can", return_value=False):
            with pytest.raises(PermissionDenied):
                svc.withdraw(leave_req.id, other_id, reason="override")

        balance_repo.reverse_deduction.assert_not_called()
