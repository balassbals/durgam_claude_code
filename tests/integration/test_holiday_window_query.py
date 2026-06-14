"""Integration tests for get_holiday_dates_in_window (M9 Phase 3).

5 tests covering: empty range, within-range inclusion, soft-delete exclusion,
AY-union semantics (two AYs in same window), and distinct-date deduplication
when both AYs declare the same calendar date as a holiday.
Uses db_session (rollback per test, clean DB, no seed required).
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from durgam.models.config_anchors import AcademicYear, Holiday
from durgam.services.holiday import get_holiday_dates_in_window


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ay(session) -> AcademicYear:
    now = datetime.now(UTC)
    ay = AcademicYear(
        code=f"AY{uuid4().hex[:6]}",
        starts_on=date(2026, 4, 1),
        ends_on=date(2027, 3, 31),
        is_locked=False,
        created_by=uuid4(),
        updated_by=uuid4(),
        created_at=now,
        updated_at=now,
    )
    session.add(ay)
    session.flush()
    return ay


def _make_holiday(session, ay_id, holiday_date: date, name: str = "Holiday") -> Holiday:
    now = datetime.now(UTC)
    h = Holiday(
        academic_year_id=ay_id,
        holiday_date=holiday_date,
        name=name,
        created_by=uuid4(),
        updated_by=uuid4(),
        created_at=now,
        updated_at=now,
    )
    session.add(h)
    session.flush()
    return h


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_returns_empty_when_no_holidays_in_range(db_session):
    """No Holiday rows in the window → empty frozenset."""
    ay = _make_ay(db_session)
    # Holiday exists but outside the query window
    _make_holiday(db_session, ay.id, date(2026, 1, 1), "New Year")

    result = get_holiday_dates_in_window(db_session, date(2026, 3, 1), date(2026, 3, 31))

    assert result == frozenset()


def test_returns_holiday_dates_within_range(db_session):
    """Only holidays within [window_start, window_end] are returned."""
    ay = _make_ay(db_session)
    _make_holiday(db_session, ay.id, date(2026, 4, 13), "Ugadi")       # in window
    _make_holiday(db_session, ay.id, date(2026, 4, 14), "Tamil New Year")  # in window
    _make_holiday(db_session, ay.id, date(2026, 5, 1), "Labour Day")   # outside window

    result = get_holiday_dates_in_window(db_session, date(2026, 4, 10), date(2026, 4, 20))

    assert date(2026, 4, 13) in result
    assert date(2026, 4, 14) in result
    assert date(2026, 5, 1) not in result
    assert len(result) == 2


def test_excludes_soft_deleted_holidays(db_session):
    """Soft-deleted holidays (is_deleted=True) are not returned."""
    ay = _make_ay(db_session)
    h = _make_holiday(db_session, ay.id, date(2026, 4, 13), "Ugadi")

    # Soft-delete the row directly
    h.is_deleted = True
    h.deleted_at = datetime.now(UTC)
    h.deleted_by = uuid4()
    db_session.add(h)
    db_session.flush()

    result = get_holiday_dates_in_window(db_session, date(2026, 4, 10), date(2026, 4, 20))

    assert result == frozenset()


def test_unions_holidays_across_two_academic_years(db_session):
    """Q4(a): holidays from both AYs are included when window straddles AY rollover."""
    ay1 = _make_ay(db_session)
    ay2 = _make_ay(db_session)

    _make_holiday(db_session, ay1.id, date(2026, 4, 13), "Ugadi (AY1)")
    _make_holiday(db_session, ay2.id, date(2026, 4, 15), "Vishu (AY2)")

    result = get_holiday_dates_in_window(db_session, date(2026, 4, 10), date(2026, 4, 20))

    assert date(2026, 4, 13) in result
    assert date(2026, 4, 15) in result
    assert len(result) == 2


def test_same_date_in_two_ays_returns_distinct(db_session):
    """The same calendar date declared in both AY1 and AY2 appears only once."""
    ay1 = _make_ay(db_session)
    ay2 = _make_ay(db_session)

    # Both AYs declare Christmas as a holiday
    _make_holiday(db_session, ay1.id, date(2026, 12, 25), "Christmas (AY1)")
    _make_holiday(db_session, ay2.id, date(2026, 12, 25), "Christmas (AY2)")

    result = get_holiday_dates_in_window(db_session, date(2026, 12, 20), date(2026, 12, 31))

    assert date(2026, 12, 25) in result
    assert len(result) == 1  # DISTINCT ensures no duplicates
