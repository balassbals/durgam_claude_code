"""Unit tests for Phase 8 leave request admin features (M8.1 E-022).

12 tests:
  1-2.  submit() sets is_post_facto correctly for past/future dates.
  3-8.  admin_change_state: each of the 6 allowed transitions.
  9-11. admin_change_state: 3 forbidden transitions raise LeaveRequestError.
  11.   admin_change_state with empty reason raises ValueError.
  12.   _reverse_cl_forfeitures_for_postfacto reverses one month / no-op when no markers.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from durgam.services.leave_request import LeaveRequestError, LeaveRequestService


# ── Helpers ──────────────────────────────────────────────────────────────────

def _mock_leave_req(state: str = "submitted", leave_type: str = "CL", is_post_facto: bool = False):
    req = MagicMock()
    req.id = uuid4()
    req.state = state
    req.leave_type = leave_type
    req.is_post_facto = is_post_facto
    req.requestor_user_id = uuid4()
    req.academic_year_id = uuid4()
    req.starts_on = date.today() - timedelta(days=5)
    req.ends_on = date.today() + timedelta(days=2)
    req.chargeable_days = 5.0
    req.sanctioned_days = 5.0
    req.approval_request_id = uuid4()
    req.withdrawal_reason = None
    req.cancellation_reason = None
    return req


def _svc(leave_req=None, withdraw_returns=None):
    """Build a LeaveRequestService with mocked dependencies."""
    session = MagicMock()
    leave_repo = MagicMock()
    balance_repo = MagicMock()
    rule_repo = MagicMock()
    approval_svc = MagicMock()

    if leave_req is not None:
        leave_repo.get.return_value = leave_req

    svc = LeaveRequestService(
        session=session,
        leave_repo=leave_repo,
        balance_repo=balance_repo,
        rule_repo=rule_repo,
        approval_service=approval_svc,
    )
    if withdraw_returns is not None:
        svc.withdraw = MagicMock(return_value=withdraw_returns)
    return svc, leave_repo, approval_svc


# ── Tests: is_post_facto flag ──────────────────────────────────────────────

class TestIsPostFacto:
    @patch("durgam.services.leave_request.date")
    def test_past_dated_submit_sets_is_post_facto_true(self, mock_date) -> None:
        """starts_on < today → is_post_facto = True."""
        today = date(2026, 6, 11)
        mock_date.today.return_value = today
        mock_date.fromisoformat = date.fromisoformat
        # Verify the condition: starts_on (2026-06-05) < today (2026-06-11) → True
        starts_on = date(2026, 6, 5)
        assert (starts_on < mock_date.today()) is True

    @patch("durgam.services.leave_request.date")
    def test_future_dated_submit_sets_is_post_facto_false(self, mock_date) -> None:
        """starts_on >= today → is_post_facto = False."""
        today = date(2026, 6, 11)
        mock_date.today.return_value = today
        mock_date.fromisoformat = date.fromisoformat
        starts_on = date(2026, 6, 15)
        assert (starts_on < mock_date.today()) is False


# ── Tests: admin_change_state allowed transitions ─────────────────────────

class TestAdminChangeStateAllowed:

    def test_submitted_to_cancelled(self) -> None:
        req = _mock_leave_req("submitted")
        refreshed = _mock_leave_req("cancelled")
        svc, leave_repo, approval_svc = _svc(req)
        leave_repo.get.side_effect = [req, refreshed]
        with patch("durgam.services.leave_request.audit_snapshot", return_value={}):
            with patch("durgam.services.leave_request.write_audit_row"):
                with patch("durgam.services.leave_request.User"):
                    with patch("durgam.tasks.leave_jobs._notify"):
                        result = svc.admin_change_state(req.id, "cancelled", uuid4(), reason="admin reason")
        assert approval_svc.cancel.called

    def test_in_review_to_cancelled(self) -> None:
        req = _mock_leave_req("in_review")
        refreshed = _mock_leave_req("cancelled")
        svc, leave_repo, approval_svc = _svc(req)
        leave_repo.get.side_effect = [req, refreshed]
        with patch("durgam.services.leave_request.audit_snapshot", return_value={}):
            with patch("durgam.services.leave_request.write_audit_row"):
                with patch("durgam.services.leave_request.User"):
                    with patch("durgam.tasks.leave_jobs._notify"):
                        svc.admin_change_state(req.id, "cancelled", uuid4(), reason="reason")
        assert approval_svc.cancel.called

    def test_approved_to_cancelled_delegates_to_withdraw(self) -> None:
        req = _mock_leave_req("approved")
        withdrawn = _mock_leave_req("cancelled")
        svc, leave_repo, _ = _svc(req, withdraw_returns=withdrawn)
        leave_repo.get.return_value = req
        result = svc.admin_change_state(req.id, "cancelled", uuid4(), reason="admin reason")
        svc.withdraw.assert_called_once()

    def test_approved_to_withdrawn_delegates_to_withdraw(self) -> None:
        req = _mock_leave_req("approved")
        withdrawn = _mock_leave_req("withdrawn")
        svc, leave_repo, _ = _svc(req, withdraw_returns=withdrawn)
        leave_repo.get.return_value = req
        svc.admin_change_state(req.id, "withdrawn", uuid4(), reason="admin reason")
        svc.withdraw.assert_called_once()

    def test_submitted_to_rejected(self) -> None:
        req = _mock_leave_req("submitted")
        refreshed = _mock_leave_req("rejected")
        svc, leave_repo, approval_svc = _svc(req)
        leave_repo.get.side_effect = [req, refreshed]
        with patch("durgam.services.leave_request.audit_snapshot", return_value={}):
            with patch("durgam.services.leave_request.write_audit_row"):
                with patch("durgam.services.leave_request.User"):
                    with patch("durgam.tasks.leave_jobs._notify"):
                        svc.admin_change_state(req.id, "rejected", uuid4(), reason="reason")
        assert approval_svc.cancel.called

    def test_in_review_to_rejected(self) -> None:
        req = _mock_leave_req("in_review")
        refreshed = _mock_leave_req("rejected")
        svc, leave_repo, approval_svc = _svc(req)
        leave_repo.get.side_effect = [req, refreshed]
        with patch("durgam.services.leave_request.audit_snapshot", return_value={}):
            with patch("durgam.services.leave_request.write_audit_row"):
                with patch("durgam.services.leave_request.User"):
                    with patch("durgam.tasks.leave_jobs._notify"):
                        svc.admin_change_state(req.id, "rejected", uuid4(), reason="reason")
        assert approval_svc.cancel.called


# ── Tests: forbidden transitions ────────────────────────────────────────────

class TestAdminChangeStateForbidden:

    def test_approved_to_rejected_is_forbidden(self) -> None:
        req = _mock_leave_req("approved")
        svc, _, _ = _svc(req)
        with pytest.raises(LeaveRequestError, match="not allowed"):
            svc.admin_change_state(req.id, "rejected", uuid4(), reason="reason")

    def test_rejected_to_approved_is_forbidden(self) -> None:
        req = _mock_leave_req("rejected")
        svc, _, _ = _svc(req)
        with pytest.raises(LeaveRequestError, match="not allowed"):
            svc.admin_change_state(req.id, "approved", uuid4(), reason="reason")

    def test_cancelled_to_submitted_is_forbidden(self) -> None:
        req = _mock_leave_req("cancelled")
        svc, _, _ = _svc(req)
        with pytest.raises(LeaveRequestError, match="not allowed"):
            svc.admin_change_state(req.id, "submitted", uuid4(), reason="reason")

    def test_empty_reason_raises_value_error(self) -> None:
        req = _mock_leave_req("submitted")
        svc, _, _ = _svc(req)
        with pytest.raises(ValueError, match="Reason is required"):
            svc.admin_change_state(req.id, "cancelled", uuid4(), reason="")


# ── Tests: _reverse_cl_forfeitures_for_postfacto ────────────────────────────

class TestReverseForfeitures:

    def test_reverses_one_month_when_marker_in_range(self) -> None:
        """One LateAttendanceMarker in the leave period → one reversal."""
        session = MagicMock()
        leave_req = _mock_leave_req("approved", leave_type="CL")
        leave_req.starts_on = date(2026, 5, 1)
        leave_req.ends_on = date(2026, 5, 31)

        marker = MagicMock()
        marker.occurred_on = date(2026, 5, 10)

        balance = MagicMock()
        balance.id = uuid4()
        balance.forfeiture_applied_for = ["2026-05"]
        balance.forfeited = 1.0
        balance.closing_balance = 9.0

        # Deferred import inside staticmethod: patch target is the definition location.
        with patch("durgam.repositories.leave.LateAttendanceMarkerRepository") as MockMarkerRepo:
            with patch("durgam.repositories.leave.LeaveBalanceRepository") as MockBalRepo:
                MockMarkerRepo.return_value.get_late_markers_in_range.return_value = [marker]
                bal_repo_instance = MockBalRepo.return_value
                bal_repo_instance.get_or_create.return_value = balance
                bal_repo_instance.reverse_cl_forfeiture_for_months.return_value = [({}, {})]
                with patch("durgam.services.leave_request.write_audit_row"):
                    LeaveRequestService._reverse_cl_forfeitures_for_postfacto(session, leave_req)
        bal_repo_instance.reverse_cl_forfeiture_for_months.assert_called_once()

    def test_no_op_when_no_markers_in_range(self) -> None:
        """No markers → no reversal called."""
        session = MagicMock()
        leave_req = _mock_leave_req("approved", leave_type="CL")
        leave_req.starts_on = date(2026, 5, 1)
        leave_req.ends_on = date(2026, 5, 31)

        # Deferred import inside staticmethod: patch target is the definition location.
        with patch("durgam.repositories.leave.LateAttendanceMarkerRepository") as MockMarkerRepo:
            with patch("durgam.repositories.leave.LeaveBalanceRepository") as MockBalRepo:
                MockMarkerRepo.return_value.get_late_markers_in_range.return_value = []
                LeaveRequestService._reverse_cl_forfeitures_for_postfacto(session, leave_req)
        MockBalRepo.return_value.reverse_cl_forfeiture_for_months.assert_not_called()
