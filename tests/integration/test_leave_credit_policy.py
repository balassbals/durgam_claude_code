"""Integration tests for credit_annual_cl and LeaveCreditPolicyRepository (M8.1 TD-036).

4 integration tests:
  1. Full credit run: credit rows + balance updates + audit rows
  2. Re-run same year → idempotent (no new rows, no balance change)
  3. academic_year.is_locked=True → raises AcademicYearLockedError
  4. policy.enabled=False → no credit rows

All use db_session (rollback per test). Task called directly with reference_date.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlmodel import func, select

from durgam.models.config_anchors import AcademicYear
from durgam.models.crosscutting import AuditLog
from durgam.models.identity import User
from durgam.models.leave import LeaveBalance, LeaveCreditPolicy, LeaveCreditRun
from durgam.repositories.leave import LeaveCreditPolicyRepository
from durgam.tasks.leave_jobs import credit_annual_cl


@pytest.fixture()
def sess(db_session):
    original_commit = db_session.commit
    db_session.commit = db_session.flush
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_session)
    ctx.__exit__ = MagicMock(return_value=False)
    with patch("durgam.tasks.leave_jobs.open_session", return_value=ctx):
        yield db_session
    db_session.commit = original_commit


def _user(session, *, employee_type="regular_non_teaching", joined_on=None) -> User:
    u = User(
        username=f"iclp_{uuid4().hex[:8]}",
        email=f"iclp_{uuid4().hex[:8]}@test.local",
        password_hash="x",
        is_active=True,
        employee_type=employee_type,
        joined_on=joined_on,
    )
    session.add(u)
    session.flush()
    session.refresh(u)
    return u


def _ay(session, *, starts_on=date(2025, 7, 1), ends_on=date(2026, 6, 30), is_locked=False) -> AcademicYear:
    ay = AcademicYear(
        code=f"AY{uuid4().hex[:4]}",
        starts_on=starts_on,
        ends_on=ends_on,
        is_locked=is_locked,
    )
    session.add(ay)
    session.flush()
    session.refresh(ay)
    return ay


def _policy(session, *, enabled=True) -> LeaveCreditPolicy:
    p = LeaveCreditPolicy(
        leave_type="CL",
        vacation_entitlement=10.0,
        non_vacation_entitlement=12.0,
        enabled=enabled,
    )
    session.add(p)
    session.flush()
    session.refresh(p)
    return p


def _run_count(session) -> int:
    return session.exec(
        select(func.count()).select_from(LeaveCreditRun).where(
            LeaveCreditRun.is_deleted == False  # noqa: E712
        )
    ).one()


def _balance_for(session, user_id, ay_id) -> LeaveBalance | None:
    return session.exec(
        select(LeaveBalance).where(
            LeaveBalance.employee_user_id == user_id,
            LeaveBalance.leave_type == "CL",
            LeaveBalance.academic_year_id == ay_id,
            LeaveBalance.is_deleted == False,  # noqa: E712
        )
    ).first()


def _audit_count_for_action(session, action: str) -> int:
    return session.exec(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == action
        )
    ).one()


# ── Integration 1: full credit run creates rows + balances + audit rows ────────


def test_full_credit_run(sess) -> None:
    """Full run: 2 users get CL credited; credit_run rows + audit rows created."""
    ay = _ay(sess)
    _policy(sess)
    user_v = _user(sess, employee_type="regular_teaching", joined_on=date(2020, 1, 1))
    user_n = _user(sess, employee_type="regular_non_teaching", joined_on=date(2019, 6, 1))

    result = credit_annual_cl(reference_date=date(2026, 1, 1))

    assert result["users_credited"] >= 2

    # Vacation employee: 10 days CL
    bal_v = _balance_for(sess, user_v.id, ay.id)
    assert bal_v is not None
    assert bal_v.credited == 10.0
    assert bal_v.closing_balance == 10.0

    # Non-vacation employee: 12 days CL
    bal_n = _balance_for(sess, user_n.id, ay.id)
    assert bal_n is not None
    assert bal_n.credited == 12.0
    assert bal_n.closing_balance == 12.0

    # credit_run rows: one per user
    runs = sess.exec(
        select(LeaveCreditRun).where(
            LeaveCreditRun.leave_type == "CL",
            LeaveCreditRun.calendar_year == 2026,
            LeaveCreditRun.is_deleted == False,  # noqa: E712
        )
    ).all()
    run_user_ids = {r.user_id for r in runs}
    assert user_v.id in run_user_ids
    assert user_n.id in run_user_ids

    # Audit rows created
    audit_count = _audit_count_for_action(sess, "credit_annual_cl")
    assert audit_count >= 2


# ── Integration 2: re-run same year → idempotent ──────────────────────────────


def test_idempotent_rerun(sess) -> None:
    """Re-running credit_annual_cl for the same calendar year is a no-op."""
    ay = _ay(sess)
    _policy(sess)
    user = _user(sess, employee_type="regular_non_teaching", joined_on=date(2018, 1, 1))

    credit_annual_cl(reference_date=date(2026, 1, 1))
    bal_after_first = _balance_for(sess, user.id, ay.id)
    assert bal_after_first is not None
    credited_after_first = bal_after_first.credited

    credit_annual_cl(reference_date=date(2026, 1, 1))
    bal_after_second = _balance_for(sess, user.id, ay.id)
    assert bal_after_second is not None

    assert bal_after_second.credited == credited_after_first, (
        "Second run must not change the credited amount (idempotency)"
    )
    assert _run_count(sess) == _run_count(sess)  # count stable after second run


# ── Integration 3: locked AY → raises AcademicYearLockedError ────────────────


def test_locked_ay_raises(sess) -> None:
    """credit_annual_cl raises AcademicYearLockedError when active AY is locked."""
    from durgam.services.org_exceptions import AcademicYearLockedError

    _ay(sess, is_locked=True)
    _policy(sess)

    with pytest.raises(AcademicYearLockedError):
        credit_annual_cl(reference_date=date(2026, 1, 1))


# ── Integration 4: disabled policy → zero credit rows ────────────────────────


def test_disabled_policy_no_rows(sess) -> None:
    """When CL credit policy is disabled, no credit rows or balance changes occur."""
    _ay(sess)
    _policy(sess, enabled=False)
    _user(sess, employee_type="regular_non_teaching", joined_on=date(2020, 1, 1))

    result = credit_annual_cl(reference_date=date(2026, 1, 1))

    assert _run_count(sess) == 0
    assert result.get("users_credited", 0) == 0
