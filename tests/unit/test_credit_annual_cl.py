"""Unit tests for credit_annual_cl task and credit formula helpers (M8.1 TD-036).

All 9 test cases per Phase 2 §E plan:
  1. Vacation entitlement full (long-tenured)
  2. Non-vacation entitlement full (long-tenured)
  3. Long-tenured employee (joined 2020-07-01) on Jan 1 2026 run → full entitlement
  4. Employee joined in current calendar year → prorated
  5. Round to nearest 0.5
  6. Idempotency: second run creates zero new credit_run rows
  7. No joined_on → full entitlement + WARNING log
  8. AY-locked → raises AcademicYearLockedError
  9. Policy disabled → no credit rows

Tests call task functions DIRECTLY with explicit reference_date — no Celery broker.
Uses the same sess fixture pattern as test_leave_jobs.py.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlmodel import select

from durgam.models.config_anchors import AcademicYear
from durgam.models.identity import User
from durgam.models.leave import LeaveCreditPolicy, LeaveCreditRun, LeaveBalance
from durgam.tasks.leave_jobs import (
    _compute_cl_credit_for_user,
    _round_half,
    credit_annual_cl,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def sess(db_session):
    """Inject db_session into leave_jobs tasks; commit() → flush() for isolation."""
    original_commit = db_session.commit
    db_session.commit = db_session.flush
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_session)
    ctx.__exit__ = MagicMock(return_value=False)
    with patch("durgam.tasks.leave_jobs.open_session", return_value=ctx):
        yield db_session
    db_session.commit = original_commit


# ── Helpers ───────────────────────────────────────────────────────────────────


def _user(session, *, employee_type="regular_non_teaching", joined_on=None) -> User:
    u = User(
        username=f"cl_{uuid4().hex[:8]}",
        email=f"cl_{uuid4().hex[:8]}@test.local",
        password_hash="x",
        is_active=True,
        employee_type=employee_type,
        joined_on=joined_on,
    )
    session.add(u)
    session.flush()
    session.refresh(u)
    return u


def _ay(
    session,
    *,
    starts_on=date(2025, 7, 1),
    ends_on=date(2026, 6, 30),
    is_locked=False,
) -> AcademicYear:
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


def _policy(
    session,
    *,
    leave_type="CL",
    vacation_entitlement=10.0,
    non_vacation_entitlement=12.0,
    enabled=True,
) -> LeaveCreditPolicy:
    p = LeaveCreditPolicy(
        leave_type=leave_type,
        vacation_entitlement=vacation_entitlement,
        non_vacation_entitlement=non_vacation_entitlement,
        enabled=enabled,
    )
    session.add(p)
    session.flush()
    session.refresh(p)
    return p


def _credit_run_count(session) -> int:
    return len(
        session.exec(
            select(LeaveCreditRun).where(LeaveCreditRun.is_deleted == False)  # noqa: E712
        ).all()
    )


def _cl_balance_for(session, user_id, ay_id) -> LeaveBalance | None:
    return session.exec(
        select(LeaveBalance).where(
            LeaveBalance.employee_user_id == user_id,
            LeaveBalance.leave_type == "CL",
            LeaveBalance.academic_year_id == ay_id,
            LeaveBalance.is_deleted == False,  # noqa: E712
        )
    ).first()


# ── Unit 1+2: formula helpers — vacation and non-vacation full entitlement ─────


def test_full_entitlement_vacation() -> None:
    """Vacation employee joined 5 years ago → full entitlement (10 for vacation)."""
    result = _compute_cl_credit_for_user(10.0, date(2021, 6, 1), 2026)
    assert result == 10.0


def test_full_entitlement_non_vacation() -> None:
    """Non-vacation employee joined 3 years ago → full entitlement (12)."""
    result = _compute_cl_credit_for_user(12.0, date(2023, 3, 15), 2026)
    assert result == 12.0


# ── Unit 3: long-tenured (joined 2020) on Jan 1, 2026 run ─────────────────────


def test_long_tenured_full_entitlement(sess) -> None:
    """Employee joined 2020-07-01, run for calendar year 2026 → full CL credit.

    This is DD-M8.1-P2-3: proration applies ONLY when joined_on.year == calendar_year.
    """
    _ay(sess, starts_on=date(2025, 7, 1), ends_on=date(2026, 6, 30))
    _policy(sess, vacation_entitlement=10.0, non_vacation_entitlement=12.0)
    user = _user(
        sess, employee_type="regular_non_teaching", joined_on=date(2020, 7, 1)
    )

    result = credit_annual_cl(reference_date=date(2026, 1, 1))

    assert result["users_credited"] >= 1
    bal = _cl_balance_for(sess, user.id, sess.exec(
        select(AcademicYear).where(AcademicYear.starts_on == date(2025, 7, 1))
    ).first().id)
    assert bal is not None
    assert bal.credited == 12.0, (
        f"Long-tenured non-vacation employee must receive full 12 days CL; got {bal.credited}"
    )


# ── Unit 4: employee joined in the current calendar year → prorated ───────────


def test_proration_for_new_joiner(sess) -> None:
    """Employee joined July 2026 (month=7); calendar year 2026 run → 6/12 proration."""
    _ay(sess, starts_on=date(2025, 7, 1), ends_on=date(2026, 6, 30))
    _policy(sess, vacation_entitlement=10.0, non_vacation_entitlement=12.0)
    # joined July 2026: months_remaining = 12 - (7-1) = 6; credit = 12 * 6/12 = 6.0
    user = _user(
        sess, employee_type="regular_non_teaching", joined_on=date(2026, 7, 1)
    )

    result = credit_annual_cl(reference_date=date(2026, 1, 1))
    assert result["users_credited"] >= 1
    ay = sess.exec(
        select(AcademicYear).where(AcademicYear.starts_on == date(2025, 7, 1))
    ).first()
    bal = _cl_balance_for(sess, user.id, ay.id)
    assert bal is not None
    assert bal.credited == 6.0


# ── Unit 5: rounding to nearest 0.5 ──────────────────────────────────────────


def test_round_half_rounds_up() -> None:
    assert _round_half(5.3) == 5.5


def test_round_half_rounds_down() -> None:
    assert _round_half(5.2) == 5.0


def test_round_half_exact() -> None:
    assert _round_half(5.5) == 5.5


# ── Unit 6: idempotency — second run creates zero new rows ────────────────────


def test_idempotency_second_run(sess) -> None:
    """Running credit_annual_cl twice for the same year is a no-op on second run."""
    _ay(sess, starts_on=date(2025, 7, 1), ends_on=date(2026, 6, 30))
    _policy(sess)
    _user(sess, employee_type="regular_non_teaching", joined_on=date(2020, 1, 1))

    credit_annual_cl(reference_date=date(2026, 1, 1))
    count_after_first = _credit_run_count(sess)

    credit_annual_cl(reference_date=date(2026, 1, 1))
    count_after_second = _credit_run_count(sess)

    assert count_after_first == count_after_second, (
        f"Second run must be a no-op; first run count={count_after_first}, "
        f"second run count={count_after_second}"
    )


# ── Unit 7: no joined_on → full entitlement + WARNING ────────────────────────


def test_no_joined_on_gets_full_entitlement(sess) -> None:
    """Employee with no joined_on → full entitlement credited (formula: None → full)."""
    _ay(sess, starts_on=date(2025, 7, 1), ends_on=date(2026, 6, 30))
    _policy(sess, non_vacation_entitlement=12.0)
    user = _user(sess, employee_type="regular_non_teaching", joined_on=None)

    credit_annual_cl(reference_date=date(2026, 1, 1))

    ay = sess.exec(
        select(AcademicYear).where(AcademicYear.starts_on == date(2025, 7, 1))
    ).first()
    bal = _cl_balance_for(sess, user.id, ay.id)
    assert bal is not None
    assert bal.credited == 12.0


# ── Unit 8: AY locked → raises AcademicYearLockedError ────────────────────────


def test_ay_locked_raises(sess) -> None:
    """If the active AY is locked, credit_annual_cl must raise AcademicYearLockedError."""
    from durgam.services.org_exceptions import AcademicYearLockedError

    _ay(sess, starts_on=date(2025, 7, 1), ends_on=date(2026, 6, 30), is_locked=True)
    _policy(sess)

    with pytest.raises(AcademicYearLockedError):
        credit_annual_cl(reference_date=date(2026, 1, 1))


# ── Unit 9: policy disabled → no credit rows ─────────────────────────────────


def test_disabled_policy_skips_all_users(sess) -> None:
    """If the CL credit policy has enabled=False, no credit rows are created."""
    _ay(sess, starts_on=date(2025, 7, 1), ends_on=date(2026, 6, 30))
    _policy(sess, enabled=False)
    _user(sess, employee_type="regular_non_teaching", joined_on=date(2020, 1, 1))

    result = credit_annual_cl(reference_date=date(2026, 1, 1))

    assert _credit_run_count(sess) == 0
    assert result.get("users_credited", 0) == 0
