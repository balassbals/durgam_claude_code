"""IST display formatting helper (M9 Phase 10.2).

India Standard Time is UTC+5:30 (Asia/Kolkata).
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

_IST = ZoneInfo("Asia/Kolkata")
_UTC = ZoneInfo("UTC")


def format_ist(dt: datetime | None) -> str:
    """Format a datetime in IST as e.g. '14 Jun 2026, 9:23 AM IST'.

    If dt is None returns '—'. If dt is naive, assumes UTC.
    """
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_UTC)
    return dt.astimezone(_IST).strftime("%-d %b %Y, %-I:%M %p IST")
