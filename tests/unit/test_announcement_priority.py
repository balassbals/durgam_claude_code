"""Unit tests for announcement priority engine (M9).

8 tests covering: is_in_important_window, priority_key grouping and ranking,
sort_for_viewer ordering, compute_important_until working-days logic.
All pure/stateless — no DB required.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from durgam.services.announcement_priority import (
    _SENTINEL_RANK,
    _count_working_days,
    compute_important_until,
    is_in_important_window,
    priority_key,
    sort_for_viewer,
)

_IST = timezone(timedelta(hours=5, minutes=30))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ann(
    *,
    importance: str = "normal",
    composer_role_code: str = "FACULTY",
    scheduled_at: datetime | None = None,
    important_until: datetime | None = None,
) -> MagicMock:
    ann = MagicMock()
    ann.importance = importance
    ann.composer_role_code = composer_role_code
    ann.scheduled_at = scheduled_at or datetime.now(UTC)
    ann.important_until = important_until
    return ann


def _make_cfg(priority_rank: int) -> MagicMock:
    cfg = MagicMock()
    cfg.priority_rank = priority_rank
    return cfg


# ---------------------------------------------------------------------------
# is_in_important_window
# ---------------------------------------------------------------------------

def test_normal_importance_is_never_in_window():
    now = datetime.now(UTC)
    ann = _make_ann(importance="normal", important_until=now + timedelta(hours=1))
    assert is_in_important_window(ann, now) is False


def test_very_important_within_window():
    now = datetime.now(UTC)
    ann = _make_ann(importance="very_important", important_until=now + timedelta(hours=12))
    assert is_in_important_window(ann, now) is True


def test_very_important_window_expired():
    now = datetime.now(UTC)
    ann = _make_ann(importance="very_important", important_until=now - timedelta(seconds=1))
    assert is_in_important_window(ann, now) is False


def test_very_important_no_important_until():
    """important_until=None means window was never computed — return False."""
    ann = _make_ann(importance="very_important", important_until=None)
    assert is_in_important_window(ann, datetime.now(UTC)) is False


# ---------------------------------------------------------------------------
# priority_key and sort_for_viewer
# ---------------------------------------------------------------------------

def test_priority_key_important_in_window_sorts_first():
    now = datetime.now(UTC)
    ann_important = _make_ann(
        importance="very_important",
        important_until=now + timedelta(days=1),
        composer_role_code="FACULTY",
    )
    ann_normal = _make_ann(importance="normal", composer_role_code="FACULTY")

    cfg = _make_cfg(10)
    config_by_role = {"FACULTY": cfg}

    key_important = priority_key(ann_important, config_by_role, now)
    key_normal = priority_key(ann_normal, config_by_role, now)

    assert key_important < key_normal  # important group 0 < normal group 1


def test_priority_key_unknown_role_uses_sentinel():
    now = datetime.now(UTC)
    ann = _make_ann(composer_role_code="UNKNOWN_ROLE")
    key = priority_key(ann, {}, now)
    assert key[1] == _SENTINEL_RANK


def test_sort_for_viewer_ordering():
    """Lower rank + in-window sorts before higher rank + normal."""
    now = datetime.now(UTC)
    t0 = now - timedelta(minutes=30)
    t1 = now - timedelta(minutes=10)

    ann_vc_important = _make_ann(
        importance="very_important",
        composer_role_code="VC",
        scheduled_at=t0,
        important_until=now + timedelta(days=1),
    )
    ann_registrar_important = _make_ann(
        importance="very_important",
        composer_role_code="REGISTRAR",
        scheduled_at=t1,
        important_until=now + timedelta(days=1),
    )
    ann_faculty_normal = _make_ann(
        importance="normal",
        composer_role_code="FACULTY",
        scheduled_at=t1,
    )

    config = {
        "VC": _make_cfg(10),
        "REGISTRAR": _make_cfg(30),
        "FACULTY": _make_cfg(170),
    }
    sorted_anns = sort_for_viewer(
        [ann_faculty_normal, ann_registrar_important, ann_vc_important],
        config,
        now,
    )

    # VC important (group 0, rank 10) should be first
    assert sorted_anns[0] is ann_vc_important
    # REGISTRAR important (group 0, rank 30) second
    assert sorted_anns[1] is ann_registrar_important
    # FACULTY normal (group 1) last
    assert sorted_anns[2] is ann_faculty_normal


# ---------------------------------------------------------------------------
# compute_important_until
# ---------------------------------------------------------------------------

def test_compute_important_until_two_working_days_no_holidays():
    """2 working days from Monday = Wednesday (no holidays)."""
    # Monday 2026-01-05 09:00 IST
    scheduled = datetime(2026, 1, 5, 3, 30, 0, tzinfo=UTC)  # 09:00 IST
    result = compute_important_until(scheduled, frozenset())

    # End of Wednesday 2026-01-07 in IST
    expected_ist = datetime(2026, 1, 7, 23, 59, 59, 999_999, tzinfo=_IST)
    expected_utc = expected_ist.astimezone(UTC)
    assert abs((result - expected_utc).total_seconds()) < 1


def test_compute_important_until_skips_sunday():
    """2 working days starting Friday: Friday (day 1) → Monday (day 2, skip Sunday)."""
    # Friday 2026-01-09
    scheduled = datetime(2026, 1, 9, 3, 30, 0, tzinfo=UTC)  # 09:00 IST
    result = compute_important_until(scheduled, frozenset())

    # End of Monday 2026-01-12 in IST (Saturday is day 1; Sunday skipped; Monday is day 2)
    # Wait: Friday is weekday 4. Saturday is weekday 5 (day 1). Sunday weekday 6 (skip). Monday weekday 0 (day 2).
    expected_ist = datetime(2026, 1, 12, 23, 59, 59, 999_999, tzinfo=_IST)
    expected_utc = expected_ist.astimezone(UTC)
    assert abs((result - expected_utc).total_seconds()) < 1


def test_count_working_days_holiday_skipped():
    """Holiday in the window extends it by one day."""
    start = date(2026, 1, 5)  # Monday (start is day 0 — not counted)
    holiday_set = frozenset({date(2026, 1, 6)})  # Tuesday is a holiday
    end = _count_working_days(start, holiday_set, 2)
    # Tue skipped (holiday), Wed (day 1), Thu (day 2)
    assert end == date(2026, 1, 8)


# ---------------------------------------------------------------------------
# compute_important_until — edge cases (Phase 3)
# ---------------------------------------------------------------------------

def test_compute_important_until_multiple_holidays_extend_window():
    """Three consecutive holidays (Tue/Wed/Thu) push the 2-day window to Sat."""
    # Mon 2026-01-05 09:00 IST
    scheduled = datetime(2026, 1, 5, 3, 30, 0, tzinfo=UTC)
    holidays = frozenset({date(2026, 1, 6), date(2026, 1, 7), date(2026, 1, 8)})
    result = compute_important_until(scheduled, holidays)

    # Fri Jan 9 (day 1), Sat Jan 10 (day 2)
    expected_ist = datetime(2026, 1, 10, 23, 59, 59, 999_999, tzinfo=_IST)
    expected_utc = expected_ist.astimezone(UTC)
    assert abs((result - expected_utc).total_seconds()) < 1


def test_compute_important_until_holiday_on_sunday_no_double_skip():
    """A holiday on Sunday has no effect — Sunday is already excluded."""
    # Sat 2026-01-10 09:00 IST
    scheduled = datetime(2026, 1, 10, 3, 30, 0, tzinfo=UTC)
    # Sunday Jan 11 is a declared holiday — but it is already skipped as Sunday
    holidays_with_sunday = frozenset({date(2026, 1, 11)})
    holidays_empty = frozenset()

    result_with = compute_important_until(scheduled, holidays_with_sunday)
    result_without = compute_important_until(scheduled, holidays_empty)

    # Both should give end of Tue Jan 13: Sat→Mon(day1)→Tue(day2)
    expected_ist = datetime(2026, 1, 13, 23, 59, 59, 999_999, tzinfo=_IST)
    expected_utc = expected_ist.astimezone(UTC)
    assert abs((result_with - expected_utc).total_seconds()) < 1
    assert abs((result_without - expected_utc).total_seconds()) < 1


def test_compute_important_until_ist_midnight_boundary():
    """UTC 2026-01-04T18:30 is IST midnight Jan 5 — start_date must be Jan 5, not Jan 4."""
    # Exactly midnight IST on Monday 2026-01-05
    scheduled = datetime(2026, 1, 4, 18, 30, 0, tzinfo=UTC)
    result = compute_important_until(scheduled, frozenset())

    # Same start_date as a 09:00 IST Jan 5 announcement → end of Wed Jan 7
    expected_ist = datetime(2026, 1, 7, 23, 59, 59, 999_999, tzinfo=_IST)
    expected_utc = expected_ist.astimezone(UTC)
    assert abs((result - expected_utc).total_seconds()) < 1


def test_compute_important_until_window_crosses_month_boundary():
    """2-day window crossing Jan→Feb (or month end) is computed correctly."""
    # Wed 2026-01-28 09:00 IST
    scheduled = datetime(2026, 1, 28, 3, 30, 0, tzinfo=UTC)
    result = compute_important_until(scheduled, frozenset())

    # Thu Jan 29 (day 1), Fri Jan 30 (day 2)
    expected_ist = datetime(2026, 1, 30, 23, 59, 59, 999_999, tzinfo=_IST)
    expected_utc = expected_ist.astimezone(UTC)
    assert abs((result - expected_utc).total_seconds()) < 1


def test_compute_important_until_window_crosses_year_boundary():
    """2-day window spanning Dec 31 → Jan 1 is computed correctly."""
    # Wed 2026-12-30 09:00 IST
    scheduled = datetime(2026, 12, 30, 3, 30, 0, tzinfo=UTC)
    result = compute_important_until(scheduled, frozenset())

    # Thu Dec 31 (day 1), Fri 2027-01-01 (day 2)
    expected_ist = datetime(2027, 1, 1, 23, 59, 59, 999_999, tzinfo=_IST)
    expected_utc = expected_ist.astimezone(UTC)
    assert abs((result - expected_utc).total_seconds()) < 1


def test_compute_important_until_returns_utc_aware_datetime():
    """Result must be UTC-aware (tzinfo not None and utcoffset == 0)."""
    scheduled = datetime(2026, 1, 5, 3, 30, 0, tzinfo=UTC)
    result = compute_important_until(scheduled, frozenset())

    assert result.tzinfo is not None
    assert result.utcoffset() == timedelta(0)


def test_compute_important_until_custom_window_days():
    """window_days=5 from Mon Jan 5 lands on Sat Jan 10."""
    # Mon 2026-01-05 09:00 IST
    scheduled = datetime(2026, 1, 5, 3, 30, 0, tzinfo=UTC)
    result = compute_important_until(scheduled, frozenset(), window_days=5)

    # Tue(1) Wed(2) Thu(3) Fri(4) Sat(5) → end of Sat Jan 10
    expected_ist = datetime(2026, 1, 10, 23, 59, 59, 999_999, tzinfo=_IST)
    expected_utc = expected_ist.astimezone(UTC)
    assert abs((result - expected_utc).total_seconds()) < 1


def test_compute_important_until_holidays_outside_window_ignored():
    """Holidays beyond the expected window end do not affect the result."""
    # Mon 2026-01-05 — default window_days=2 → end of Wed Jan 7 without holidays
    scheduled = datetime(2026, 1, 5, 3, 30, 0, tzinfo=UTC)
    # Holidays on Thu Jan 8 and Fri Jan 9 — past the already-established window
    holidays = frozenset({date(2026, 1, 8), date(2026, 1, 9)})
    result = compute_important_until(scheduled, holidays)

    # Should still be end of Wed Jan 7
    expected_ist = datetime(2026, 1, 7, 23, 59, 59, 999_999, tzinfo=_IST)
    expected_utc = expected_ist.astimezone(UTC)
    assert abs((result - expected_utc).total_seconds()) < 1


def test_count_working_days_all_holidays_extends_indefinitely():
    """10 consecutive holidays (Jan 6–15) push the 2-day window to Sat Jan 17."""
    start = date(2026, 1, 5)  # Monday
    holiday_set = frozenset(date(2026, 1, d) for d in range(6, 16))  # Jan 6–15
    end = _count_working_days(start, holiday_set, 2)
    # Jan 6–10 holiday (Tue–Sat), Jan 11 skipped (Sun),
    # Jan 12–15 holiday (Mon–Thu), Jan 16 (Fri) day 1, Jan 17 (Sat) day 2
    assert end == date(2026, 1, 17)
