"""Integration tests for LeaveBalanceImportService (M8.1 E-016).

3 integration tests:
  1. Mix of new + existing rows committed → DB state correct + audit rows = len(valid_rows).
  2. Re-import identical CSV → balance values unchanged AND audit rows = 2× (one per action).
  3. Locked AY (no unlocked AY) → AcademicYearLockedError, zero DB writes.
"""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlmodel import func, select

from durgam.models.config_anchors import AcademicYear
from durgam.models.crosscutting import AuditLog
from durgam.models.identity import User
from durgam.models.leave import LeaveBalance
from durgam.services.leave_balance_import import LeaveBalanceImportService


# ── Helpers ────────────────────────────────────────────────────────────────────


def _ay(
    session,
    *,
    starts_on: date | None = None,
    ends_on: date | None = None,
    is_locked: bool = False,
) -> AcademicYear:
    today = date.today()
    ay = AcademicYear(
        code=f"AY{uuid4().hex[:4]}",
        starts_on=starts_on or today - timedelta(days=30),
        ends_on=ends_on or today + timedelta(days=30),
        is_locked=is_locked,
    )
    session.add(ay)
    session.flush()
    session.refresh(ay)
    return ay


def _user(session, *, username: str | None = None) -> User:
    uname = username or f"ilbi_{uuid4().hex[:8]}"
    u = User(
        username=uname,
        email=f"{uname}@test.local",
        password_hash="x",
        is_active=True,
    )
    session.add(u)
    session.flush()
    session.refresh(u)
    return u


def _actor(session) -> User:
    return _user(session, username=f"actor_{uuid4().hex[:8]}")


def _balance_for(session, user_id, leave_type: str, ay_id) -> LeaveBalance | None:
    return session.exec(
        select(LeaveBalance).where(
            LeaveBalance.employee_user_id == user_id,
            LeaveBalance.leave_type == leave_type,
            LeaveBalance.academic_year_id == ay_id,
            LeaveBalance.is_deleted == False,  # noqa: E712
        )
    ).first()


def _audit_import_count(session) -> int:
    return session.exec(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "import")
    ).one()


# ── Integration 1: full commit creates correct rows + audit ────────────────────


def test_commit_mix_new_and_existing(db_session) -> None:
    """Commit with new + pre-existing rows: DB state correct + audit count = len(valid_rows)."""
    _ay(db_session)
    actor = _actor(db_session)
    user1 = _user(db_session)
    user2 = _user(db_session)
    user3 = _user(db_session)

    # Pre-create a balance for user1 (simulate existing row).
    svc = LeaveBalanceImportService(db_session)
    ay = svc.resolve_active_ay()
    assert ay is not None
    existing_bal = LeaveBalance(
        id=uuid4(),
        employee_user_id=user1.id,
        leave_type="CL",
        academic_year_id=ay.id,
        opening_balance=0.0,
        credited=5.0,
        availed=1.0,
        forfeited=0.0,
        encashed=0.0,
        closing_balance=4.0,
        created_by=actor.id,
        updated_by=actor.id,
    )
    db_session.add(existing_bal)
    db_session.flush()

    csv_text = (
        "employee_username,leave_type,opening_balance,credited,availed,forfeited,encashed\n"
        f"{user1.username},CL,0.0,10.0,3.0,0.0,0.0\n"
        f"{user2.username},CL,0.0,12.0,4.0,0.0,0.0\n"
        f"{user3.username},EL,5.0,15.0,6.0,0.0,0.0\n"
    )

    validation = svc.validate(csv_text)
    assert len(validation.valid_rows) == 3
    assert len(validation.invalid_rows) == 0

    result = svc.commit(validation.valid_rows, actor_id=actor.id)

    assert result.created == 2  # user2 and user3 are new
    assert result.updated == 1  # user1 existed
    assert result.audit_rows_written == 3

    # Verify DB state for each user.
    bal1 = _balance_for(db_session, user1.id, "CL", ay.id)
    assert bal1 is not None
    assert bal1.credited == 10.0
    assert bal1.availed == 3.0
    assert bal1.closing_balance == 7.0  # 0 + 10 - 3 - 0 - 0

    bal2 = _balance_for(db_session, user2.id, "CL", ay.id)
    assert bal2 is not None
    assert bal2.credited == 12.0
    assert bal2.closing_balance == 8.0  # 0 + 12 - 4

    bal3 = _balance_for(db_session, user3.id, "EL", ay.id)
    assert bal3 is not None
    assert bal3.opening_balance == 5.0
    assert bal3.closing_balance == 14.0  # 5 + 15 - 6

    # Audit rows: one per row committed.
    assert _audit_import_count(db_session) == 3


# ── Integration 2: re-import identical CSV → balances unchanged, audit grows ───


def test_reimport_identical_csv(db_session) -> None:
    """Re-importing identical CSV: balances unchanged AND audit rows = 2×len(valid_rows).

    DD-M8.1-P3-3: Audit rows written on every commit invocation, even idempotent ones.
    """
    _ay(db_session)
    actor = _actor(db_session)
    user1 = _user(db_session)
    user2 = _user(db_session)

    csv_text = (
        "employee_username,leave_type,opening_balance,credited,availed,forfeited,encashed\n"
        f"{user1.username},CL,0.0,10.0,3.0,0.0,0.0\n"
        f"{user2.username},EL,5.0,15.0,6.0,0.0,0.0\n"
    )

    svc = LeaveBalanceImportService(db_session)
    validation = svc.validate(csv_text)
    assert len(validation.valid_rows) == 2

    # First commit.
    result1 = svc.commit(validation.valid_rows, actor_id=actor.id)
    assert result1.created == 2
    assert _audit_import_count(db_session) == 2

    ay = svc.resolve_active_ay()
    assert ay is not None
    bal1_after_first = _balance_for(db_session, user1.id, "CL", ay.id)
    assert bal1_after_first is not None
    closing_after_first = bal1_after_first.closing_balance

    # Second commit — same valid_rows.
    result2 = svc.commit(validation.valid_rows, actor_id=actor.id)
    assert result2.updated == 2  # both rows existed → updated
    assert result2.created == 0

    # Balance values must be identical.
    bal1_after_second = _balance_for(db_session, user1.id, "CL", ay.id)
    assert bal1_after_second is not None
    assert bal1_after_second.closing_balance == closing_after_first

    # Audit rows must have grown by len(valid_rows) = 2.
    assert _audit_import_count(db_session) == 4  # 2 (first run) + 2 (second run)


# ── Integration 3: locked AY → AcademicYearLockedError, zero writes ────────────


def test_commit_locked_ay_raises(db_session) -> None:
    """All AYs locked: commit raises AcademicYearLockedError with zero DB writes."""
    from durgam.services.org_exceptions import AcademicYearLockedError

    _ay(db_session, is_locked=True)
    actor = _actor(db_session)
    user1 = _user(db_session)

    csv_text = (
        "employee_username,leave_type,opening_balance,credited,availed,forfeited,encashed\n"
        f"{user1.username},CL,0.0,10.0,3.0,0.0,0.0\n"
    )

    svc = LeaveBalanceImportService(db_session)
    # validate() doesn't need an unlocked AY; it just parses and looks up users.
    validation = svc.validate(csv_text)
    assert len(validation.valid_rows) == 1

    with pytest.raises(AcademicYearLockedError):
        svc.commit(validation.valid_rows, actor_id=actor.id)

    # No balance rows or audit rows written.
    bal_count = db_session.exec(
        select(func.count()).select_from(LeaveBalance).where(
            LeaveBalance.employee_user_id == user1.id,
        )
    ).one()
    assert bal_count == 0
    assert _audit_import_count(db_session) == 0
