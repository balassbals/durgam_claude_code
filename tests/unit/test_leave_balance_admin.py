"""Unit tests for LeaveBalanceRepository.admin_update_balance (M8.1 E-022).

5 tests:
  1. Edit balance recomputes closing_balance correctly.
  2. Negative closing_balance raises LeaveBalanceValidationError.
  3. Forbidden field raises LeaveBalanceValidationError.
  4. AY-locked raises AcademicYearLockedError.
  5. audit_snapshot called before and after mutation; caller can write audit row.
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, call, patch
from uuid import uuid4

import pytest

from durgam.repositories.leave import LeaveBalanceRepository, LeaveBalanceValidationError
from durgam.services.org_exceptions import AcademicYearLockedError


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _mock_balance(
    *,
    opening_balance: float = 10.0,
    credited: float = 2.0,
    availed: float = 3.0,
    forfeited: float = 0.0,
    encashed: float = 0.0,
    ay_locked: bool = False,
) -> MagicMock:
    bal = MagicMock()
    bal.id = uuid4()
    bal.opening_balance = opening_balance
    bal.credited = credited
    bal.availed = availed
    bal.forfeited = forfeited
    bal.encashed = encashed
    bal.closing_balance = opening_balance + credited - availed - forfeited - encashed
    bal.academic_year_id = uuid4()
    # _check_ay_locked uses session.get(AcademicYear, ay_id)
    ay = MagicMock()
    ay.is_locked = ay_locked
    return bal, ay


def _repo(balance, ay) -> tuple[LeaveBalanceRepository, MagicMock]:
    session = MagicMock()
    session.get.side_effect = lambda model, id_: balance if "LeaveBalance" in str(model) else ay
    session.exec.return_value.first.return_value = ay
    repo = LeaveBalanceRepository(session)
    return repo, session


class TestAdminUpdateBalance:

    def test_closing_recomputed_correctly(self) -> None:
        """After updating availed, closing_balance = opening + credited - availed - forfeited - encashed."""
        bal, ay = _mock_balance(opening_balance=10.0, credited=5.0, availed=3.0)
        repo, session = _repo(bal, ay)

        with patch("durgam.repositories.leave.audit_snapshot", return_value={}):
            result_bal, before, after = repo.admin_update_balance(
                balance_id=bal.id,
                fields={"availed": 4.0},
                actor_id=uuid4(),
            )

        assert bal.availed == 4.0
        # closing = 10 + 5 - 4 - 0 - 0 = 11.0
        assert bal.closing_balance == 11.0

    def test_negative_closing_raises(self) -> None:
        """availed > opening + credited → closing < 0 → LeaveBalanceValidationError."""
        bal, ay = _mock_balance(opening_balance=5.0, credited=0.0, availed=0.0)
        repo, session = _repo(bal, ay)

        with patch("durgam.repositories.leave.audit_snapshot", return_value={}):
            with pytest.raises(LeaveBalanceValidationError, match="Negative closing balance"):
                repo.admin_update_balance(
                    balance_id=bal.id,
                    fields={"availed": 10.0},
                    actor_id=uuid4(),
                )

    def test_forbidden_field_raises(self) -> None:
        """Passing a non-editable field (e.g. leave_type) raises LeaveBalanceValidationError."""
        bal, ay = _mock_balance()
        repo, session = _repo(bal, ay)

        with pytest.raises(LeaveBalanceValidationError, match="Forbidden field: leave_type"):
            repo.admin_update_balance(
                balance_id=bal.id,
                fields={"leave_type": "EL"},
                actor_id=uuid4(),
            )

    def test_locked_ay_raises(self) -> None:
        """AY-locked balance raises AcademicYearLockedError before any mutation."""
        bal, ay = _mock_balance(ay_locked=True)
        repo, session = _repo(bal, ay)

        with pytest.raises(AcademicYearLockedError):
            repo.admin_update_balance(
                balance_id=bal.id,
                fields={"credited": 1.0},
                actor_id=uuid4(),
            )

    def test_audit_snapshots_captured(self) -> None:
        """audit_snapshot is called twice (before + after) so caller can produce a diff."""
        bal, ay = _mock_balance(opening_balance=8.0, credited=2.0, availed=1.0)
        repo, session = _repo(bal, ay)

        snap_results = [{"before": True}, {"after": True}]
        with patch(
            "durgam.repositories.leave.audit_snapshot", side_effect=snap_results
        ) as mock_snap:
            result_bal, before_snap, after_snap = repo.admin_update_balance(
                balance_id=bal.id,
                fields={"credited": 3.0},
                actor_id=uuid4(),
            )

        assert mock_snap.call_count == 2
        assert before_snap == {"before": True}
        assert after_snap == {"after": True}
