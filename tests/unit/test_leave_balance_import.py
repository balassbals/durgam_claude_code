"""Unit tests for LeaveBalanceImportService (M8.1 E-016).

10 tests:
  (a) CSV parser — 4 tests
  (b) Row validation — 5 tests
  (c) resolve_active_ay — 1 test covering straddle, fallback, and no-unlocked scenarios
"""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest

from durgam.models.config_anchors import AcademicYear
from durgam.models.identity import User
from durgam.services.leave_balance_import import (
    CSVFormatError,
    LeaveBalanceImportService,
    _parse_csv,
)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _ay(
    session,
    *,
    starts_on: date,
    ends_on: date,
    is_locked: bool = False,
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


def _user(session, username: str) -> User:
    u = User(
        username=username,
        email=f"{username}@test.local",
        password_hash="x",
        is_active=True,
    )
    session.add(u)
    session.flush()
    session.refresh(u)
    return u


def _one_row_csv(username: str = "testuser", leave_type: str = "CL") -> str:
    return (
        "employee_username,leave_type,opening_balance,credited,availed,forfeited,encashed\n"
        f"{username},{leave_type},0.0,10.0,3.0,0.0,0.0\n"
    )


# ── (a) CSV parser tests — no DB ───────────────────────────────────────────────


def test_parse_valid_7_cols() -> None:
    """Valid 7-column CSV parses into dicts with correct keys and stripped values."""
    csv_text = (
        "employee_username,leave_type,opening_balance,credited,availed,forfeited,encashed\n"
        "user1,CL,0.0,10.0,3.0,0.0,0.0\n"
        "user2, EL, 5.0, 15.0, 6.0, 1.0, 0.0\n"
    )
    rows = _parse_csv(csv_text)
    assert len(rows) == 2
    assert rows[0]["employee_username"] == "user1"
    assert rows[0]["leave_type"] == "CL"
    assert rows[0]["opening_balance"] == "0.0"
    # Whitespace stripped
    assert rows[1]["employee_username"] == "user2"
    assert rows[1]["credited"] == "15.0"


def test_parse_missing_column() -> None:
    """CSV with fewer than 7 columns raises CSVFormatError."""
    csv_text = "employee_username,leave_type,opening_balance,credited,availed,forfeited\nuser1,CL,0,10,3,0\n"
    with pytest.raises(CSVFormatError, match="Missing CSV columns"):
        _parse_csv(csv_text)


def test_parse_extra_column() -> None:
    """CSV with more than 7 columns raises CSVFormatError."""
    csv_text = (
        "employee_username,leave_type,opening_balance,credited,availed,forfeited,encashed,extra\n"
        "user1,CL,0,10,3,0,0,X\n"
    )
    with pytest.raises(CSVFormatError, match="Extra CSV columns"):
        _parse_csv(csv_text)


def test_parse_empty_csv() -> None:
    """Empty string (and whitespace-only string) raises CSVFormatError."""
    with pytest.raises(CSVFormatError, match="Empty CSV"):
        _parse_csv("")
    with pytest.raises(CSVFormatError, match="Empty CSV"):
        _parse_csv("   \n  \n")


# ── (b) Row validation tests ───────────────────────────────────────────────────


def test_validate_unknown_username(db_session) -> None:
    """Row with a username not in the DB becomes an invalid row with a clear reason."""
    _ay(db_session, starts_on=date.today() - timedelta(30), ends_on=date.today() + timedelta(30))
    svc = LeaveBalanceImportService(db_session)
    result = svc.validate(_one_row_csv(username="no_such_user_xyz"))
    assert len(result.valid_rows) == 0
    assert len(result.invalid_rows) == 1
    assert "unknown employee_username" in result.invalid_rows[0].error_reason


def test_validate_unknown_leave_type() -> None:
    """Row with an invalid leave_type becomes an invalid row (no DB access needed)."""
    # This doesn't even need a db_session because leave_type check is first.
    csv_text = _one_row_csv(leave_type="XX")
    # Instantiate service with a None-equivalent session (never touched for this path)
    from unittest.mock import MagicMock
    svc = LeaveBalanceImportService(MagicMock())
    result = svc.validate(csv_text)
    assert len(result.valid_rows) == 0
    assert len(result.invalid_rows) == 1
    assert "unknown leave_type" in result.invalid_rows[0].error_reason


def test_validate_negative_balance() -> None:
    """Row with a negative numeric field becomes invalid (no DB access needed)."""
    csv_text = (
        "employee_username,leave_type,opening_balance,credited,availed,forfeited,encashed\n"
        "user1,CL,-1.0,10.0,3.0,0.0,0.0\n"
    )
    from unittest.mock import MagicMock
    svc = LeaveBalanceImportService(MagicMock())
    result = svc.validate(csv_text)
    assert len(result.invalid_rows) == 1
    assert "negative value" in result.invalid_rows[0].error_reason


def test_validate_non_numeric() -> None:
    """Row with a non-numeric balance field becomes invalid (no DB access needed)."""
    csv_text = (
        "employee_username,leave_type,opening_balance,credited,availed,forfeited,encashed\n"
        "user1,CL,abc,10.0,3.0,0.0,0.0\n"
    )
    from unittest.mock import MagicMock
    svc = LeaveBalanceImportService(MagicMock())
    result = svc.validate(csv_text)
    assert len(result.invalid_rows) == 1
    assert "non-numeric value" in result.invalid_rows[0].error_reason


def test_validate_negative_closing() -> None:
    """Row where closing = opening + credited - availed - forfeited - encashed < 0 is invalid."""
    # All individual fields ≥ 0, but availed > opening + credited → negative closing.
    csv_text = (
        "employee_username,leave_type,opening_balance,credited,availed,forfeited,encashed\n"
        "user1,CL,0.0,5.0,10.0,0.0,0.0\n"
    )
    from unittest.mock import MagicMock
    svc = LeaveBalanceImportService(MagicMock())
    result = svc.validate(csv_text)
    assert len(result.invalid_rows) == 1
    assert "negative closing balance" in result.invalid_rows[0].error_reason


# ── (c) resolve_active_ay ─────────────────────────────────────────────────────


def test_resolve_active_ay_scenarios(db_session) -> None:
    """Covers no-unlocked (None), fallback (past AY), and straddle (today)."""
    svc = LeaveBalanceImportService(db_session)
    today = date.today()

    # Scenario 1: no AYs at all → None
    result = svc.resolve_active_ay()
    assert result is None

    # Scenario 2: only past unlocked AY (fallback path)
    past_ay = _ay(
        db_session,
        starts_on=today - timedelta(days=400),
        ends_on=today - timedelta(days=40),
        is_locked=False,
    )
    result = svc.resolve_active_ay()
    assert result is not None
    assert result.id == past_ay.id

    # Scenario 3: add a straddling AY — should take priority over the past one
    today_ay = _ay(
        db_session,
        starts_on=today - timedelta(days=30),
        ends_on=today + timedelta(days=30),
        is_locked=False,
    )
    result = svc.resolve_active_ay()
    assert result is not None
    assert result.id == today_ay.id
