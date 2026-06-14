"""Announcement priority engine (M9, Q3/Q4 freeze).

Priority sort order for a given viewer (hybrid strategy, Q3-c):
  1. very_important announcements WITHIN the 2-working-day window  (group 0)
  2. All others sorted by composer priority_rank ASC, scheduled_at DESC (group 1)

Within group 0: sort by priority_rank ASC, then scheduled_at DESC.
Within group 1: sort by priority_rank ASC, then scheduled_at DESC.

priority_key() returns a 3-tuple suitable for Python's sort() / sorted():
    (group: int, rank: int, neg_epoch: float)

Working-day window (Q4 freeze):
- Computed in IST (UTC+5:30).
- Excludes: Sundays; rows in the Holiday table.
- When the window straddles an AY rollover, both AYs' Holiday rows are used
  (union of non-deleted Holiday rows in any matching AY for the date range).
- important_until is stored at announcement save time (fast read; stale if a
  Holiday is added retroactively — admin recalculate action to be added in
  UI phase).

All functions are pure / stateless (no DB I/O) except compute_important_until,
which needs Holiday rows passed in by the caller.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from durgam.models.announcement import Announcement, AnnouncementComposerConfig

_IST = timezone(timedelta(hours=5, minutes=30))
_SENTINEL_RANK = 999_999  # rank when role not in config_by_role


# ---------------------------------------------------------------------------
# Working-days computation
# ---------------------------------------------------------------------------

def _count_working_days(
    start: date,
    holiday_dates: frozenset[date],
    target_days: int,
) -> date:
    """Return the date of the `target_days`-th working day AFTER `start`.

    A working day is any calendar day that is:
    - not a Sunday (weekday() == 6), AND
    - not in holiday_dates.

    `start` itself is NOT counted (the window begins the day after publication).
    Example: start=Monday, target=2, no holidays → Wednesday.
    """
    counted = 0
    current = start + timedelta(days=1)
    while counted < target_days:
        if current.weekday() != 6 and current not in holiday_dates:
            counted += 1
        if counted < target_days:
            current += timedelta(days=1)
    return current


def compute_important_until(
    scheduled_at: datetime,
    holiday_dates: frozenset[date],
    *,
    window_days: int = 2,
) -> datetime:
    """Return the end-of-day IST datetime after `window_days` working days.

    `scheduled_at` is assumed UTC-aware; converted to IST for day calculation.
    The returned datetime is end-of-day (23:59:59.999999) IST of the last
    working day in the window, converted back to UTC.
    """
    scheduled_ist = scheduled_at.astimezone(_IST)
    start_date = scheduled_ist.date()
    end_date = _count_working_days(start_date, holiday_dates, window_days)
    end_ist = datetime(
        end_date.year, end_date.month, end_date.day,
        23, 59, 59, 999_999,
        tzinfo=_IST,
    )
    return end_ist.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Priority key computation
# ---------------------------------------------------------------------------

def is_in_important_window(announcement: "Announcement", now: datetime) -> bool:
    """True if announcement is very_important and within its 2-working-day window.

    `now` must be UTC-aware. Returns False for normal-importance announcements
    or if important_until is None.
    """
    if announcement.importance != "very_important":
        return False
    if announcement.important_until is None:
        return False
    return now <= announcement.important_until


def priority_key(
    announcement: "Announcement",
    config_by_role: dict[str, "AnnouncementComposerConfig"],
    now: datetime,
) -> tuple[int, int, float]:
    """Return a sort key for one announcement.

    Lower tuple = higher position in the feed.

    Tuple components:
      [0] group:    0 if in important window, else 1
      [1] rank:     config_by_role[composer_role_code].priority_rank,
                    or _SENTINEL_RANK if role not in config
      [2] neg_epoch: -scheduled_at.timestamp()  (newer = smaller negative = higher)
    """
    group = 0 if is_in_important_window(announcement, now) else 1
    cfg = config_by_role.get(announcement.composer_role_code)
    rank = cfg.priority_rank if cfg is not None else _SENTINEL_RANK
    neg_epoch = -announcement.scheduled_at.timestamp()
    return (group, rank, neg_epoch)


def sort_for_viewer(
    announcements: list["Announcement"],
    config_by_role: dict[str, "AnnouncementComposerConfig"],
    now: datetime,
) -> list["Announcement"]:
    """Return announcements sorted by priority for the viewer's feed.

    config_by_role: maps role_code → AnnouncementComposerConfig; caller
    builds this from AnnouncementComposerConfigRepository.list_enabled_ordered().
    """
    return sorted(announcements, key=lambda a: priority_key(a, config_by_role, now))
