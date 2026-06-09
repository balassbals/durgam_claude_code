"""Unit tests for leave Celery jobs (M8 Phase 6).

All tests use the `sess` fixture: db_session injected into the task via a patched
open_session, with session.commit() mapped to session.flush() to preserve test isolation
(the outer connection transaction is rolled back on teardown as usual).

Tests call task functions DIRECTLY with an explicit reference_date — no Celery broker needed.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlmodel import select

from durgam.models.config_anchors import AcademicYear
from durgam.models.crosscutting import AuditLog
from durgam.models.identity import User
from durgam.models.leave import (
    LateAttendanceMarker,
    LeaveBalance,
    LeaveRequest,
)
from durgam.tasks.leave_jobs import (
    check_overstay,
    credit_periodic_el_hpl,
    forfeit_late_cl,
    lapse_unavailed_cl,
)


# ── Shared fixture ─────────────────────────────────────────────────────────────


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


# ── Shared DB helpers ──────────────────────────────────────────────────────────


def _user(session, *, employee_type="regular_non_teaching", joined_on=None) -> User:
    u = User(
        username=f"lj_{uuid4().hex[:8]}",
        email=f"lj_{uuid4().hex[:8]}@test.local",
        password_hash="x",
        is_active=True,
        employee_type=employee_type,
        joined_on=joined_on,
    )
    session.add(u)
    session.flush()
    session.refresh(u)
    return u


def _ay(session, *, starts_on=date(2026, 6, 1), ends_on=date(2027, 5, 31)) -> AcademicYear:
    ay = AcademicYear(
        code=f"AY{uuid4().hex[:4]}",
        starts_on=starts_on,
        ends_on=ends_on,
        is_locked=False,
    )
    session.add(ay)
    session.flush()
    session.refresh(ay)
    return ay


def _balance(
    session,
    user_id,
    ay_id,
    leave_type: str,
    *,
    closing_balance: float = 10.0,
    opening_balance: float = 10.0,
    forfeited: float = 0.0,
    credited: float = 0.0,
    forfeiture_applied_for: list[str] | None = None,
) -> LeaveBalance:
    b = LeaveBalance(
        employee_user_id=user_id,
        leave_type=leave_type,
        academic_year_id=ay_id,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        forfeited=forfeited,
        credited=credited,
        forfeiture_applied_for=forfeiture_applied_for or [],
    )
    session.add(b)
    session.flush()
    session.refresh(b)
    return b


def _marker(session, user_id, occurred_on: date, recorded_by=None) -> LateAttendanceMarker:
    m = LateAttendanceMarker(
        employee_user_id=user_id,
        occurred_on=occurred_on,
        recorded_by=recorded_by or user_id,
    )
    session.add(m)
    session.flush()
    return m


def _leave_request(
    session,
    requestor_id,
    ay_id,
    *,
    state: str = "approved",
    ends_on: date = date(2026, 6, 1),
    overstay_flagged: bool = False,
    approval_request_id=None,
) -> LeaveRequest:
    from datetime import UTC, datetime

    from durgam.models.crosscutting import ApprovalProcess, ApprovalRequest

    # Minimal approval process + request to satisfy FK
    proc = ApprovalProcess(
        code=f"LP{uuid4().hex[:6]}",
        title="Leave",
        requestor_role_codes=[],
        channel_role_codes=None,
        requires_upward_attachments=False,
        max_upward_attachments=0,
        requires_downward_attachments=False,
        max_downward_attachments=0,
        is_finance=False,
    )
    session.add(proc)
    session.flush()
    session.refresh(proc)

    now = datetime.now(UTC)
    ar = ApprovalRequest(
        process_id=proc.id,
        requestor_user_id=requestor_id,
        title="Test Leave Request",
        state=state,
        payload_json={},
        created_at=now,
        updated_at=now,
    )
    session.add(ar)
    session.flush()
    session.refresh(ar)

    lr = LeaveRequest(
        requestor_user_id=requestor_id,
        academic_year_id=ay_id,
        leave_type="CL",
        starts_on=ends_on - timedelta(days=2),
        ends_on=ends_on,
        chargeable_days=3.0,
        reason="test",
        state=state,
        overstay_flagged=overstay_flagged,
        approval_request_id=ar.id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(lr)
    session.flush()
    session.refresh(lr)
    return lr


# ── forfeit_late_cl ────────────────────────────────────────────────────────────


class TestForfeitLateCl:

    def test_forfeit_3_markers_debits_1_day(self, sess):
        ay = _ay(sess)
        user = _user(sess)
        for d in [date(2026, 6, 1), date(2026, 6, 15), date(2026, 6, 22)]:
            _marker(sess, user.id, d)
        bal = _balance(sess, user.id, ay.id, "CL", closing_balance=10.0)

        result = forfeit_late_cl(reference_date=date(2026, 7, 1))

        assert result["employees_forfeited"] == 1
        assert result["period"] == "2026-06"
        assert result["errors"] == []

        sess.refresh(bal)
        assert bal.forfeited == 1.0
        assert bal.closing_balance == 9.0

    def test_forfeit_2_markers_does_not_debit(self, sess):
        ay = _ay(sess)
        user = _user(sess)
        for d in [date(2026, 6, 1), date(2026, 6, 15)]:
            _marker(sess, user.id, d)
        bal = _balance(sess, user.id, ay.id, "CL", closing_balance=10.0)

        result = forfeit_late_cl(reference_date=date(2026, 7, 1))

        assert result["employees_forfeited"] == 0
        sess.refresh(bal)
        assert bal.forfeited == 0.0
        assert bal.closing_balance == 10.0

    def test_forfeit_idempotent_same_period(self, sess):
        ay = _ay(sess)
        user = _user(sess)
        for d in [date(2026, 6, 1), date(2026, 6, 15), date(2026, 6, 22)]:
            _marker(sess, user.id, d)
        bal = _balance(sess, user.id, ay.id, "CL", closing_balance=10.0)

        # First call
        r1 = forfeit_late_cl(reference_date=date(2026, 7, 1))
        assert r1["employees_forfeited"] == 1

        # Second call — same period
        r2 = forfeit_late_cl(reference_date=date(2026, 7, 1))
        assert r2["employees_forfeited"] == 0
        assert r2["employees_skipped_idempotent"] == 1

        sess.refresh(bal)
        assert bal.forfeited == 1.0  # NOT 2.0
        assert bal.forfeiture_applied_for.count("2026-06") == 1

    def test_forfeit_writes_audit_row(self, sess):
        ay = _ay(sess)
        user = _user(sess)
        for d in [date(2026, 6, 1), date(2026, 6, 10), date(2026, 6, 20)]:
            _marker(sess, user.id, d)
        bal = _balance(sess, user.id, ay.id, "CL")

        forfeit_late_cl(reference_date=date(2026, 7, 1))

        audit_row = sess.exec(
            select(AuditLog).where(
                AuditLog.action == "forfeit_cl",
                AuditLog.resource == "leave_balance",
                AuditLog.resource_id == str(bal.id),
            )
        ).first()
        assert audit_row is not None
        assert audit_row.actor_user_id is None  # system action


# ── lapse_unavailed_cl ─────────────────────────────────────────────────────────


class TestLapseUnavailedCl:

    def test_lapse_zeros_positive_balance(self, sess):
        ay = _ay(sess, starts_on=date(2026, 1, 1), ends_on=date(2026, 12, 31))
        user = _user(sess)
        bal = _balance(
            sess, user.id, ay.id, "CL",
            closing_balance=5.0,
            opening_balance=5.0,
        )

        result = lapse_unavailed_cl(reference_date=date(2026, 12, 31))

        assert result["employees_lapsed"] == 1
        assert result["total_days_lapsed"] == 5.0
        sess.refresh(bal)
        assert bal.closing_balance == 0.0
        assert bal.forfeited == 5.0

    def test_lapse_zero_balance_noop(self, sess):
        ay = _ay(sess, starts_on=date(2026, 1, 1), ends_on=date(2026, 12, 31))
        user = _user(sess)
        _balance(sess, user.id, ay.id, "CL", closing_balance=0.0, opening_balance=0.0)

        result = lapse_unavailed_cl(reference_date=date(2026, 12, 31))

        assert result["employees_lapsed"] == 0

        audit_count = len(
            sess.exec(
                select(AuditLog).where(AuditLog.action == "lapse_cl")
            ).all()
        )
        assert audit_count == 0

    def test_lapse_writes_audit_per_employee(self, sess):
        ay = _ay(sess, starts_on=date(2026, 1, 1), ends_on=date(2026, 12, 31))
        u1 = _user(sess)
        u2 = _user(sess)
        bal1 = _balance(sess, u1.id, ay.id, "CL", closing_balance=3.0, opening_balance=3.0)
        bal2 = _balance(sess, u2.id, ay.id, "CL", closing_balance=7.0, opening_balance=7.0)

        result = lapse_unavailed_cl(reference_date=date(2026, 12, 31))

        assert result["employees_lapsed"] == 2
        assert result["total_days_lapsed"] == 10.0

        audit_rows = sess.exec(
            select(AuditLog).where(AuditLog.action == "lapse_cl")
        ).all()
        audited_ids = {r.resource_id for r in audit_rows}
        assert str(bal1.id) in audited_ids
        assert str(bal2.id) in audited_ids


# ── credit_periodic_el_hpl ─────────────────────────────────────────────────────


class TestCreditPeriodicElHpl:

    def test_credit_non_vacation_employee_el(self, sess):
        # 6 months service → 6 × 2.5 = 15.0 EL
        joined = date(2026, 1, 1)
        ref = date(2026, 7, 1)
        ay = _ay(sess)
        user = _user(sess, employee_type="regular_non_teaching", joined_on=joined)
        _balance(
            sess, user.id, ay.id, "EL",
            closing_balance=0.0, opening_balance=0.0,
        )

        result = credit_periodic_el_hpl(reference_date=ref)

        assert result["el_credits"] == 1
        assert result["errors"] == []

        bal = sess.exec(
            select(LeaveBalance).where(
                LeaveBalance.employee_user_id == user.id,
                LeaveBalance.leave_type == "EL",
            )
        ).first()
        assert bal is not None
        assert bal.closing_balance == pytest.approx(15.0, abs=0.6)

    def test_credit_vacation_employee_uses_actual_service_only(self, sess):
        """Vacation employee gets component (a) only: days_since / 30. See TD-035."""
        assert "TD-035" in credit_periodic_el_hpl.__doc__

        joined = date(2026, 1, 1)
        ref = date(2026, 7, 1)
        days_since = (ref - joined).days  # 181
        expected_credit = days_since / 30.0

        ay = _ay(sess)
        user = _user(sess, employee_type="regular_teaching", joined_on=joined)
        _balance(
            sess, user.id, ay.id, "EL",
            closing_balance=0.0, opening_balance=0.0,
        )

        credit_periodic_el_hpl(reference_date=ref)

        bal = sess.exec(
            select(LeaveBalance).where(
                LeaveBalance.employee_user_id == user.id,
                LeaveBalance.leave_type == "EL",
            )
        ).first()
        assert bal is not None
        assert bal.closing_balance == pytest.approx(expected_credit, abs=0.1)

    def test_credit_caps_at_300_el(self, sess):
        joined = date(2020, 1, 1)
        ref = date(2026, 7, 1)
        ay = _ay(sess)
        user = _user(sess, employee_type="regular_non_teaching", joined_on=joined)
        # Balance already at 295 — only 5 days of headroom
        _balance(
            sess, user.id, ay.id, "EL",
            closing_balance=295.0, opening_balance=295.0,
        )

        credit_periodic_el_hpl(reference_date=ref)

        bal = sess.exec(
            select(LeaveBalance).where(
                LeaveBalance.employee_user_id == user.id,
                LeaveBalance.leave_type == "EL",
            )
        ).first()
        assert bal is not None
        assert bal.closing_balance == pytest.approx(300.0, abs=0.01)

    def test_credit_idempotent_same_period(self, sess):
        joined = date(2026, 1, 1)
        ref = date(2026, 7, 1)
        ay = _ay(sess)
        user = _user(sess, employee_type="regular_non_teaching", joined_on=joined)
        _balance(
            sess, user.id, ay.id, "EL",
            closing_balance=0.0, opening_balance=0.0,
        )

        # First call
        r1 = credit_periodic_el_hpl(reference_date=ref)
        assert r1["el_credits"] == 1

        bal_after_first = sess.exec(
            select(LeaveBalance).where(
                LeaveBalance.employee_user_id == user.id,
                LeaveBalance.leave_type == "EL",
            )
        ).first()
        balance_after_first = bal_after_first.closing_balance

        # Second call — same period (last_credited_at is now in H2 2026)
        r2 = credit_periodic_el_hpl(reference_date=ref)
        assert r2["el_credits"] == 0  # skipped

        sess.refresh(bal_after_first)
        assert bal_after_first.closing_balance == balance_after_first  # unchanged

    def test_credit_hpl_increments_at_5_over_3(self, sess):
        # 6 months → 6 × (5/3) = 10.0 HPL
        joined = date(2026, 1, 1)
        ref = date(2026, 7, 1)
        ay = _ay(sess)
        user = _user(sess, employee_type="regular_non_teaching", joined_on=joined)
        _balance(
            sess, user.id, ay.id, "HPL",
            closing_balance=0.0, opening_balance=0.0,
        )

        result = credit_periodic_el_hpl(reference_date=ref)

        assert result["hpl_credits"] == 1

        bal = sess.exec(
            select(LeaveBalance).where(
                LeaveBalance.employee_user_id == user.id,
                LeaveBalance.leave_type == "HPL",
            )
        ).first()
        assert bal is not None
        # 6 months × (5/3) = 10.0; allow ±0.5 for rounding
        assert bal.closing_balance == pytest.approx(10.0, abs=0.6)


# ── check_overstay ─────────────────────────────────────────────────────────────


class TestCheckOverstay:

    def test_overstay_flags_expired_approved(self, sess):
        ay = _ay(sess)
        user = _user(sess)
        ref = date(2026, 7, 1)
        ends_on = ref - timedelta(days=1)  # yesterday
        lr = _leave_request(
            sess, user.id, ay.id,
            state="approved",
            ends_on=ends_on,
            overstay_flagged=False,
        )

        result = check_overstay(reference_date=ref)

        assert result["flagged"] == 1
        assert result["errors"] == []

        sess.refresh(lr)
        assert lr.overstay_flagged is True

    def test_overstay_does_not_re_flag(self, sess):
        ay = _ay(sess)
        user = _user(sess)
        ref = date(2026, 7, 1)
        ends_on = ref - timedelta(days=1)
        lr = _leave_request(
            sess, user.id, ay.id,
            state="approved",
            ends_on=ends_on,
            overstay_flagged=True,  # already flagged
        )

        result = check_overstay(reference_date=ref)

        assert result["flagged"] == 0

        audit_count = len(
            sess.exec(
                select(AuditLog).where(
                    AuditLog.action == "flag_overstay",
                    AuditLog.resource_id == str(lr.id),
                )
            ).all()
        )
        assert audit_count == 0

    def test_overstay_ignores_non_approved(self, sess):
        ay = _ay(sess)
        user = _user(sess)
        ref = date(2026, 7, 1)
        ends_on = ref - timedelta(days=1)
        _leave_request(
            sess, user.id, ay.id,
            state="submitted",  # not approved
            ends_on=ends_on,
            overstay_flagged=False,
        )

        result = check_overstay(reference_date=ref)

        assert result["flagged"] == 0
